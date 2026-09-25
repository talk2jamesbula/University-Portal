from django.test import TestCase

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

from ..models import Enrollment, ResultAction

R = Enrollment.ResultStatus


class ResultsWorkflowTests(TestCase):
    def setUp(self):
        self.semester = make_semester()
        self.department = make_department()
        self.faculty = self.department.faculty
        self.lecturer = make_staff(roles=["lecturer"], department=self.department)
        self.hod = make_staff(roles=[("hod", self.department)])
        self.dean = make_staff(roles=[("dean", self.faculty)])
        self.exam_officer = make_staff(roles=["exam_officer"])
        other_department = make_department()
        self.other_hod = make_staff(roles=[("hod", other_department)])
        self.offering = make_offering(
            make_course(self.department, code="CSC201"), self.semester, lecturer=self.lecturer
        )
        programme = make_programme(self.department)
        self.students = [make_student(programme=programme) for _ in range(3)]
        self.enrollments = [
            Enrollment.objects.create(student=s, offering=self.offering, status=Enrollment.Status.REGISTERED)
            for s in self.students
        ]
        self.url = f"/api/academics/result-sheets/{self.offering.pk}/"

    def enter_all(self, client=None):
        scores = [{"enrollment": e.pk, "ca_score": "25", "exam_score": "50.5"} for e in self.enrollments]
        return (client or client_for(self.lecturer)).patch(self.url, {"scores": scores}, format="json")

    def act(self, user, action, note=""):
        return client_for(user).post(f"{self.url}{action}/", {"note": note}, format="json")

    def statuses(self):
        return set(Enrollment.objects.filter(offering=self.offering).values_list("result_status", flat=True))

    def test_lecturer_enters_scores_as_draft(self):
        response = self.enter_all()
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["status"], R.DRAFT)
        self.assertEqual(response.data["actions"], ["edit", "submit"])
        self.assertEqual(str(response.data["rows"][0]["total_score"]), "75.5")
        self.assertEqual(response.data["rows"][0]["grade"], "A")

    def test_scores_are_range_checked(self):
        response = client_for(self.lecturer).patch(
            self.url, {"scores": [{"enrollment": self.enrollments[0].pk, "ca_score": "31"}]}, format="json"
        )
        self.assertEqual(response.status_code, 400)

    def test_only_the_lecturer_enters_scores(self):
        self.assertEqual(self.enter_all(client_for(self.hod)).status_code, 403)
        self.assertEqual(self.enter_all(client_for(self.other_hod)).status_code, 403)  # can't even see it

    def test_submit_needs_every_score(self):
        client_for(self.lecturer).patch(
            self.url, {"scores": [{"enrollment": self.enrollments[0].pk, "ca_score": "20"}]}, format="json"
        )
        response = self.act(self.lecturer, "submit")
        self.assertEqual(response.status_code, 400)
        self.assertIn("3 still incomplete", str(response.data))

    def test_full_workflow_to_publication(self):
        self.enter_all()
        self.assertEqual(self.act(self.lecturer, "submit").status_code, 200)
        self.assertEqual(self.statuses(), {R.SUBMITTED})
        self.assertTrue(Notification.objects.filter(user=self.hod, title__contains="awaiting your approval").exists())
        self.assertFalse(Notification.objects.filter(user=self.other_hod).exists())

        # Scores are frozen once submitted.
        self.assertEqual(self.enter_all().status_code, 400)
        # Only the right reviewer at each stage.
        self.assertEqual(self.act(self.dean, "approve").status_code, 403)
        self.assertEqual(self.act(self.other_hod, "approve").status_code, 403)

        self.assertEqual(self.act(self.hod, "approve").status_code, 200)
        self.assertEqual(self.statuses(), {R.DEPARTMENT_APPROVED})
        self.assertTrue(Notification.objects.filter(user=self.dean).exists())

        self.assertEqual(self.act(self.dean, "approve").status_code, 200)
        self.assertEqual(self.statuses(), {R.FACULTY_APPROVED})
        self.assertTrue(
            Notification.objects.filter(user=self.exam_officer, title__contains="ready to publish").exists()
        )

        response = self.act(self.exam_officer, "approve")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.statuses(), {R.PUBLISHED})
        self.assertEqual(response.data["actions"], [])
        student = self.students[0]
        self.assertTrue(Notification.objects.filter(user=student, category=Notification.Category.RESULTS).exists())
        results = client_for(student).get("/api/academics/results/").data
        self.assertEqual(results["semesters"][0]["courses"][0]["grade"], "A")
        self.assertEqual(
            list(ResultAction.objects.order_by("at").values_list("action", flat=True)),
            ["submit", "approve_department", "approve_faculty", "publish"],
        )

    def test_return_sends_results_back_with_a_note(self):
        self.enter_all()
        self.act(self.lecturer, "submit")
        self.assertEqual(self.act(self.hod, "return").status_code, 400)  # a note is required
        response = self.act(self.hod, "return", "CA for the second student looks wrong.")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.statuses(), {R.DRAFT})
        self.assertTrue(Notification.objects.filter(user=self.lecturer, title__contains="returned").exists())
        self.assertEqual(self.enter_all().status_code, 200)  # editable again
        self.assertEqual(response.data["history"][0]["note"], "CA for the second student looks wrong.")

    def test_hod_cannot_approve_a_course_they_teach(self):
        self.offering.lecturer = self.hod
        self.offering.save()
        self.enter_all(client_for(self.hod))
        self.act(self.hod, "submit")
        self.assertEqual(self.act(self.hod, "approve").status_code, 403)

    def test_sheet_list_shows_what_each_person_can_do(self):
        self.enter_all()
        self.act(self.lecturer, "submit")
        rows = client_for(self.hod).get("/api/academics/result-sheets/", {"status": "mine"}).data["rows"]
        self.assertEqual([r["code"] for r in rows], ["CSC201"])
        self.assertEqual(rows[0]["actions"], ["approve", "return"])
        self.assertEqual(rows[0]["complete"], 3)
        self.assertEqual(client_for(self.other_hod).get("/api/academics/result-sheets/").data["rows"], [])
        # The Exams Office (university-wide) sees every course, but has nothing to do yet.
        rows = client_for(self.exam_officer).get("/api/academics/result-sheets/").data["rows"]
        self.assertEqual(rows[0]["actions"], [])
        self.assertEqual(client_for(self.students[0]).get(self.url).status_code, 403)
