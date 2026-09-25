from datetime import time, timedelta
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from apps.academics.models import Enrollment
from apps.attendance.models import AttendanceRecord, AttendanceSession
from apps.core.models import Notification
from apps.core.testing import (
    client_for,
    make_course,
    make_department,
    make_offering,
    make_programme,
    make_semester,
    make_staff,
    make_student,
)
from apps.finance.models import Charge

from .. import services
from ..models import Attempt, Candidate, Exam, Venue


class ExamTestCase(TestCase):
    def setUp(self):
        today = timezone.localdate()
        self.semester = make_semester(start_date=today - timedelta(days=60), end_date=today + timedelta(days=30))
        self.department = make_department()
        self.lecturer = make_staff(roles=["lecturer"], department=self.department)
        self.officer = make_staff(roles=["exam_officer"])
        self.course = make_course(self.department, code="CSC201", title="Data Structures")
        self.offering = make_offering(self.course, self.semester, lecturer=self.lecturer)
        programme = make_programme(self.department)
        self.students = [make_student(programme=programme) for _ in range(3)]
        for student in self.students:
            self.register(student, self.offering)
        self.hall = Venue.objects.create(code="H1", name="Hall 1", capacity=2)
        self.annex = Venue.objects.create(code="H2", name="Hall 2", capacity=10)
        self.lab = Venue.objects.create(code="CBT", name="CBT Centre", capacity=50, is_cbt_centre=True)

    def register(self, student, offering):
        Enrollment.objects.create(student=student, offering=offering, status=Enrollment.Status.REGISTERED)

    def make_exam(self, offering=None, *, venues=(), published=False, **kw):
        exam = Exam.objects.create(
            offering=offering or self.offering,
            date=kw.pop("date", timezone.localdate() + timedelta(days=7)),
            start_time=kw.pop("start_time", time(9)),
            **kw,
        )
        exam.venues.set(venues)
        if published:
            services.publish([exam], self.officer)
            exam.refresh_from_db()
        return exam

    def record_attendance(self, offering, attended, absent):
        """One closed class with the given students present and absent."""
        session = AttendanceSession.objects.create(
            offering=offering,
            date=timezone.localdate() - timedelta(days=AttendanceSession.objects.count() + 1),
            start_time=time(8),
            status=AttendanceSession.Status.CLOSED,
        )
        for student in attended:
            AttendanceRecord.objects.create(session=session, student=student, status="present", method="lecturer")
        for student in absent:
            AttendanceRecord.objects.create(session=session, student=student, status="absent", method="system")


class EligibilityTests(ExamTestCase):
    def test_attendance_and_fees_rules(self):
        exam = self.make_exam()
        good, truant, debtor = self.students
        for _ in range(4):
            self.record_attendance(self.offering, [good, debtor], [truant])
        Charge.objects.create(
            student=debtor, description="Tuition", amount=5000, due_date=timezone.localdate() - timedelta(days=1)
        )
        rows = {r["student"]: r for r in services.roster(exam)}
        self.assertTrue(rows[good]["eligible"])
        self.assertFalse(rows[truant]["eligible"])
        self.assertIn("Attendance is 0%", rows[truant]["reasons"][0])
        self.assertFalse(rows[debtor]["eligible"])
        self.assertIn("₦5,000.00", rows[debtor]["reasons"][0])

    def test_no_classes_recorded_does_not_block(self):
        self.assertTrue(services.eligibility(self.students[0], self.make_exam())["eligible"])

    def test_waiver_lets_a_student_sit_and_is_audited(self):
        exam = self.make_exam()
        truant = self.students[1]
        self.record_attendance(self.offering, [], [truant])
        client = client_for(self.officer)
        url = f"/api/exams/timetable/{exam.pk}/waive/"
        self.assertEqual(client.post(url, {"student": truant.pk, "waived": True}, format="json").status_code, 400)
        response = client.post(url, {"student": truant.pk, "waived": True, "reason": "Medical report"}, format="json")
        self.assertEqual(response.status_code, 200)
        status = services.eligibility(truant, exam)
        self.assertTrue(status["eligible"])
        self.assertTrue(status["waived"])
        self.assertEqual(client_for(self.lecturer).post(url, {"student": truant.pk, "waived": False}).status_code, 403)


class SeatingTests(ExamTestCase):
    def test_seats_fill_venues_in_order_and_stay_put(self):
        exam = self.make_exam(venues=[self.hall, self.annex])
        self.assertEqual(services.allocate_seats(exam), 3)
        seats = sorted(exam.candidates.values_list("venue__code", "seat_number"))
        self.assertEqual(seats, [("H1", 1), ("H1", 2), ("H2", 1)])
        before = dict(exam.candidates.values_list("student_id", "seat_number"))
        late = make_student(programme=self.students[0].student_profile.programme)
        self.register(late, self.offering)
        self.assertEqual(services.allocate_seats(exam), 1)  # only the newcomer
        after = dict(exam.candidates.values_list("student_id", "seat_number"))
        self.assertEqual({k: after[k] for k in before}, before)

    def test_not_enough_seats(self):
        exam = self.make_exam(venues=[self.hall])
        with self.assertRaisesMessage(Exception, "3 students need seats"):
            services.allocate_seats(exam)

    def test_shared_hall_seats_do_not_collide(self):
        first = self.make_exam(venues=[self.annex])
        services.allocate_seats(first)
        other = make_offering(make_course(self.department), self.semester)
        outsider = make_student()
        self.register(outsider, other)
        second = self.make_exam(other, venues=[self.annex], start_time=time(10))  # overlaps 09:00–11:00
        services.allocate_seats(second)
        self.assertEqual(second.candidates.get().seat_number, 4)


class TimetableTests(ExamTestCase):
    def test_problems_report_student_clashes_and_small_venues(self):
        other = make_offering(make_course(self.department, code="CSC205"), self.semester)
        self.register(self.students[0], other)
        self.make_exam(venues=[self.hall])
        self.make_exam(other, start_time=time(10))
        response = client_for(self.officer).get("/api/exams/timetable/problems/", {"semester": self.semester.pk})
        messages = [p["message"] for p in response.data]
        self.assertTrue(any("CSC201 and CSC205 overlap" in m and "1 student take" in m for m in messages))
        self.assertTrue(any("CSC201: 3 students but its venues seat only 2" in m for m in messages))
        self.assertTrue(any("CSC205 has no venue" in m for m in messages))
        self.assertEqual(response.data[0]["level"], "error")

    def test_only_the_exams_office_schedules(self):
        payload = {
            "offering": self.offering.pk,
            "date": str(timezone.localdate() + timedelta(days=5)),
            "start_time": "09:00",
            "venues": [self.annex.pk],
        }
        self.assertEqual(client_for(self.lecturer).post("/api/exams/timetable/", payload).status_code, 403)
        response = client_for(self.officer).post("/api/exams/timetable/", payload)
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["status"], "draft")
        # A second exam for the same course is refused.
        self.assertEqual(client_for(self.officer).post("/api/exams/timetable/", payload).status_code, 400)

    def test_publish_seats_everyone_and_tells_each_student_once(self):
        other = make_offering(make_course(self.department), self.semester)
        self.register(self.students[0], other)
        self.make_exam(venues=[self.annex])
        self.make_exam(other, venues=[self.annex], date=timezone.localdate() + timedelta(days=8))
        response = client_for(self.officer).post(
            "/api/exams/timetable/publish/", {"semester": self.semester.pk}, format="json"
        )
        self.assertEqual(response.data, {"published": 2, "students": 3})
        self.assertEqual(Candidate.objects.filter(venue__isnull=False).count(), 4)
        self.assertEqual(Notification.objects.filter(user=self.students[0], category="exams").count(), 1)

    def test_moving_a_published_exam_tells_candidates(self):
        exam = self.make_exam(venues=[self.annex], published=True)
        Notification.objects.all().delete()
        new_date = str(exam.date + timedelta(days=1))
        response = client_for(self.officer).patch(f"/api/exams/timetable/{exam.pk}/", {"date": new_date})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(Notification.objects.filter(title__contains="Change to your CSC201").count(), 3)

    def test_lecturer_sees_only_their_exams(self):
        self.make_exam()
        self.make_exam(make_offering(make_course(self.department), self.semester))
        data = client_for(self.lecturer).get("/api/exams/timetable/", {"semester": self.semester.pk}).data
        self.assertEqual([e["code"] for e in data], ["CSC201"])
        self.assertEqual(len(client_for(self.officer).get("/api/exams/timetable/").data), 2)


class CardAndCheckInTests(ExamTestCase):
    def test_student_timetable_and_card(self):
        self.make_exam(venues=[self.annex], published=True)
        student = self.students[0]
        data = client_for(student).get("/api/exams/me/").data
        self.assertTrue(data["card_available"])
        self.assertEqual(data["exams"][0]["venue"], "Hall 2")
        self.assertEqual(data["exams"][0]["seat_number"], 1)
        response = client_for(student).get("/api/exams/me/card/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_no_card_when_not_eligible(self):
        self.make_exam(venues=[self.annex], published=True)
        self.record_attendance(self.offering, [], [self.students[0]])
        self.assertEqual(client_for(self.students[0]).get("/api/exams/me/card/").status_code, 400)

    def test_draft_exams_are_hidden_from_students(self):
        self.make_exam(venues=[self.annex])
        self.assertEqual(client_for(self.students[0]).get("/api/exams/me/").data["exams"], [])

    def test_invigilator_verifies_card_and_checks_in_on_the_day(self):
        exam = self.make_exam(venues=[self.annex], published=True, date=timezone.localdate())
        student = self.students[0]
        token = services.card_token(student, self.semester)
        client = client_for(self.lecturer)  # lecturers invigilate
        data = client.get("/api/exams/verify/", {"code": token}).data
        self.assertEqual(data["student"]["matric_number"], student.university_id)
        self.assertTrue(data["exams"][0]["is_today"])
        self.assertEqual(client.get("/api/exams/verify/", {"code": token[:-3] + "abc"}).status_code, 400)
        self.assertEqual(client_for(student).get("/api/exams/verify/", {"code": token}).status_code, 403)

        response = client.post("/api/exams/verify/check-in/", {"exam": exam.pk, "student": student.pk})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["seat_number"], 1)
        again = client.post("/api/exams/verify/check-in/", {"exam": exam.pk, "student": student.pk})
        self.assertEqual(again.status_code, 200)
        self.assertFalse(again.data["created"])

    def test_check_in_refused_when_ineligible_or_not_today(self):
        exam = self.make_exam(venues=[self.annex], published=True, date=timezone.localdate())
        self.record_attendance(self.offering, [], [self.students[1]])
        client = client_for(self.officer)
        response = client.post("/api/exams/verify/check-in/", {"exam": exam.pk, "student": self.students[1].pk})
        self.assertEqual(response.status_code, 400)
        self.assertIn("may not sit", str(response.data))
        later = self.make_exam(make_offering(make_course(self.department), self.semester), published=False)
        self.register(self.students[0], later.offering)
        later.venues.set([self.annex])
        services.publish([later], self.officer)
        response = client.post("/api/exams/verify/check-in/", {"exam": later.pk, "student": self.students[0].pk})
        self.assertIn("isn't today", str(response.data))


class CbtTests(ExamTestCase):
    def setUp(self):
        super().setUp()
        self.exam = self.make_exam(venues=[self.lab], mode=Exam.Mode.CBT, duration_minutes=30)
        self.lecturer_client = client_for(self.lecturer)
        for n in range(4):
            response = self.add_question(f"Question {n + 1}?", correct=n % 2)
            self.assertEqual(response.status_code, 201, response.data)
        services.publish([self.exam], self.officer)
        # The questions are set; now let the exam have started five minutes ago.
        start = timezone.localtime() - timedelta(minutes=5)
        self.exam.date, self.exam.start_time = start.date(), start.time().replace(microsecond=0)
        self.exam.save()
        self.student = self.students[0]
        self.client_ = client_for(self.student)

    def add_question(self, text, correct=0, marks=1):
        choices = [{"text": f"Option {i}", "is_correct": i == correct} for i in range(3)]
        return self.lecturer_client.post(
            f"/api/exams/timetable/{self.exam.pk}/questions/",
            {"text": text, "marks": marks, "choices": choices},
            format="json",
        )

    def start(self):
        return self.client_.post(f"/api/exams/timetable/{self.exam.pk}/start/")

    def correct_choice(self, question_id):
        return self.exam.questions.get(pk=question_id).choices.get(is_correct=True).pk

    def test_question_rules(self):
        bad = self.lecturer_client.post(
            f"/api/exams/timetable/{self.exam.pk}/questions/",
            {"text": "Two answers?", "choices": [{"text": "a", "is_correct": True}, {"text": "b", "is_correct": True}]},
            format="json",
        )
        self.assertEqual(bad.status_code, 400)
        other = make_staff(roles=["lecturer"])
        self.assertEqual(client_for(other).get(f"/api/exams/timetable/{self.exam.pk}/questions/").status_code, 404)
        self.assertEqual(
            client_for(self.officer).get(f"/api/exams/timetable/{self.exam.pk}/questions/").status_code, 403
        )

    def test_paper_is_shuffled_and_hides_answers(self):
        self.exam.questions_per_candidate = 3
        self.exam.save()
        response = self.start()
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(len(response.data["questions"]), 3)
        self.assertNotIn("is_correct", str(response.data))
        attempt = Attempt.objects.get()
        self.assertEqual(attempt.max_score, 3)
        # Starting again resumes the same paper.
        self.assertEqual(self.start().data["id"], attempt.pk)
        # The questions are now locked.
        self.assertEqual(self.add_question("Late addition?").status_code, 400)

    def test_answers_autosave_and_submission_marks_the_paper(self):
        paper = self.start().data
        attempt_url = f"/api/exams/attempts/{paper['id']}/"
        right, wrong = paper["questions"][0], paper["questions"][1]
        self.client_.put(f"{attempt_url}answer/", {"question": right["id"], "choice": self.correct_choice(right["id"])})
        wrong_choice = next(c["id"] for c in wrong["choices"] if c["id"] != self.correct_choice(wrong["id"]))
        self.client_.put(f"{attempt_url}answer/", {"question": wrong["id"], "choice": wrong_choice})
        self.assertEqual(self.client_.get(attempt_url).data["questions"][0]["answer"], self.correct_choice(right["id"]))
        foreign = self.client_.put(f"{attempt_url}answer/", {"question": right["id"], "choice": wrong_choice})
        self.assertEqual(foreign.status_code, 400)

        submitted = self.client_.post(f"{attempt_url}submit/").data
        self.assertEqual(submitted["status"], "submitted")
        self.assertNotIn("questions", submitted)
        self.assertEqual(Attempt.objects.get().score, 1)
        again = self.client_.put(f"{attempt_url}answer/", {"question": right["id"], "choice": None}, format="json")
        self.assertEqual(again.status_code, 400)
        self.assertIn("already submitted", str(self.start().data))

    def test_time_runs_out_on_the_server(self):
        paper = self.start().data
        later = timezone.now() + timedelta(minutes=31)
        with mock.patch("django.utils.timezone.now", return_value=later):
            response = self.client_.put(
                f"/api/exams/attempts/{paper['id']}/answer/",
                {"question": paper["questions"][0]["id"], "choice": None},
                format="json",
            )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Attempt.objects.get().status, Attempt.Status.TIMED_OUT)

    def test_entry_closes_after_the_late_entry_window(self):
        later = timezone.now() + timedelta(minutes=40)
        with mock.patch("django.utils.timezone.now", return_value=later):
            response = self.start()
        self.assertEqual(response.status_code, 400)
        self.assertIn("closed", str(response.data))

    def test_ineligible_students_cannot_start(self):
        self.record_attendance(self.offering, [], [self.student])
        self.assertEqual(self.start().status_code, 400)

    def test_leaving_the_page_is_logged_and_flagged(self):
        paper = self.start().data
        for _ in range(3):
            response = self.client_.post(f"/api/exams/attempts/{paper['id']}/event/", {"kind": "left_page"})
        self.assertEqual(response.data["focus_losses"], 3)
        rows = self.lecturer_client.get(f"/api/exams/timetable/{self.exam.pk}/attempts/").data
        self.assertTrue(rows[0]["flagged"])

    def test_other_students_cannot_open_an_attempt(self):
        paper = self.start().data
        self.assertEqual(client_for(self.students[1]).get(f"/api/exams/attempts/{paper['id']}/").status_code, 404)

    def test_release_scores_to_the_result_sheet(self):
        paper = self.start().data
        for q in paper["questions"]:
            self.client_.put(
                f"/api/exams/attempts/{paper['id']}/answer/",
                {"question": q["id"], "choice": self.correct_choice(q["id"])},
            )
        url = f"/api/exams/timetable/{self.exam.pk}/release-scores/"
        self.assertIn("still writing", str(self.lecturer_client.post(url).data))
        self.client_.post(f"/api/exams/attempts/{paper['id']}/submit/")
        response = self.lecturer_client.post(url)
        self.assertEqual(response.data, {"released": 1, "absent": 2})
        enrollment = Enrollment.objects.get(student=self.student, offering=self.offering)
        self.assertEqual(enrollment.exam_score, 70)
        self.assertEqual(enrollment.result_status, Enrollment.ResultStatus.DRAFT)
