from decimal import Decimal

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.academics.grading import academic_standing, degree_class, grade_for, weighted_average
from apps.academics.models import Course, CourseOffering, Enrollment
from apps.accounts.models import StudentProfile
from apps.core.models import AuditLog, Notification
from apps.core.testing import (
    add_to_curriculum,
    client_for,
    make_admin,
    make_course,
    make_offering,
    make_programme,
    make_semester,
    make_staff,
    make_student,
)

PUBLISHED = Enrollment.ResultStatus.PUBLISHED


class GradingTests(TestCase):
    def test_nuc_scale(self):
        for total, expected in [
            (100, ("A", 5)),
            (70, ("A", 5)),
            (69.9, ("B", 4)),
            (60, ("B", 4)),
            (50, ("C", 3)),
            (45, ("D", 2)),
            (40, ("E", 1)),
            (39.9, ("F", 0)),
            (0, ("F", 0)),
        ]:
            self.assertEqual(grade_for(total), expected, total)

    def test_weighted_average_and_classes(self):
        gpa, units, passed = weighted_average([(3, 5), (2, 3), (3, 0)])
        self.assertEqual((gpa, units, passed), (Decimal("2.63"), 8, 5))
        self.assertEqual(degree_class(Decimal("4.50")), "First Class")
        self.assertEqual(degree_class(Decimal("3.49")), "Second Class (Lower Division)")
        self.assertEqual(academic_standing(Decimal("0.99")), "Academic probation")
        self.assertEqual(weighted_average([]), (None, 0, 0))


@override_settings(MIN_UNITS_PER_SEMESTER=5, MAX_UNITS_PER_SEMESTER=9)
class RegistrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.programme = make_programme()
        cls.semester = make_semester()
        cls.lecturer = make_staff("lect", roles=["lecturer"])
        cls.core = make_course(code="CSC201", units=3, level=200)
        cls.elective = make_course(code="CSC205", units=2, level=200)
        cls.lower = make_course(code="MTH101", units=3, level=100)
        cls.higher = make_course(code="CSC301", units=3, level=300)
        cls.second_sem = make_course(code="CSC202", units=3, level=200, semester_number=2)
        cls.outside = make_course(code="ACC201", units=3, level=200)
        add_to_curriculum(cls.programme, cls.core, cls.lower, cls.higher, cls.second_sem)
        add_to_curriculum(cls.programme, cls.elective, compulsory=False)
        cls.o_core = make_offering(cls.core, cls.semester, days="MON", hour=8, lecturer=cls.lecturer)
        cls.o_elective = make_offering(cls.elective, cls.semester, days="TUE", hour=8)
        cls.o_lower = make_offering(cls.lower, cls.semester, days="WED", hour=8)
        cls.o_higher = make_offering(cls.higher, cls.semester, days="THU", hour=8)
        cls.o_outside = make_offering(cls.outside, cls.semester, days="FRI", hour=8)
        cls.student = make_student("stu", programme=cls.programme, level=200)

    def reg(self, offering, action="add", user=None):
        return client_for(user or self.student).post(
            "/api/academics/registration/", {"offering": offering.id, "action": action}
        )

    def overview(self):
        return client_for(self.student).get("/api/academics/registration/").data

    def test_available_courses_follow_curriculum_and_level(self):
        rows = {r["code"]: r for r in self.overview()["available"]}
        self.assertEqual(set(rows), {"CSC201", "CSC205", "MTH101"})  # no 300L, other semester or other programme
        self.assertTrue(rows["CSC201"]["is_compulsory"])
        self.assertFalse(rows["CSC205"]["is_compulsory"])

    def test_register_drop_and_state(self):
        self.assertEqual(self.overview()["state"], "not_started")
        self.assertEqual(self.reg(self.o_core).status_code, 201)
        self.assertEqual(self.overview()["state"], "incomplete")  # 3 units < minimum 5
        self.reg(self.o_elective)
        data = self.overview()
        self.assertEqual((data["state"], data["units"]), ("complete", 5))
        self.assertEqual(self.reg(self.o_elective, "drop").data["status"], "dropped")
        self.assertEqual(self.overview()["units"], 3)
        self.assertEqual(self.reg(self.o_elective).status_code, 201)  # re-register after drop

    def test_rules(self):
        self.assertIn("isn't available", str(self.reg(self.o_outside).data))
        self.assertIn("isn't available", str(self.reg(self.o_higher).data))
        self.reg(self.o_core)
        self.assertIn("already registered", str(self.reg(self.o_core).data))
        clash = make_offering(make_course(level=200), self.semester, days="MON", hour=8)
        add_to_curriculum(self.programme, clash.course)
        self.assertIn("clashes", str(self.reg(clash).data))
        self.reg(self.o_elective)
        self.reg(self.o_lower)  # 8 units now
        big = make_offering(make_course(level=200, units=2), self.semester, days="FRI", hour=14)
        add_to_curriculum(self.programme, big.course)
        self.assertIn("9-unit limit", str(self.reg(big).data))

    def test_capacity(self):
        full = make_offering(make_course(level=200), self.semester, days="FRI", hour=10, capacity=1)
        add_to_curriculum(self.programme, full.course)
        other = make_student(programme=self.programme, level=200)
        self.assertEqual(self.reg(full, user=other).status_code, 201)
        self.assertIn("full", str(self.reg(full).data))

    def test_closed_registration_and_status(self):
        self.semester.registration_open = False
        self.semester.save()
        self.assertIn("closed", str(self.reg(self.o_core).data))
        self.semester.registration_open = True
        self.semester.save()
        self.student.student_profile.status = StudentProfile.Status.SUSPENDED
        self.student.student_profile.save()
        self.assertIn("suspended", str(self.reg(self.o_core).data))

    def test_carryover_and_passed_courses(self):
        past = make_semester("2025/2026", 1, is_current=False, registration_open=False)
        failed_offering = make_offering(self.lower, past)
        Enrollment.objects.create(
            student=self.student, offering=failed_offering, ca_score=10, exam_score=20, result_status=PUBLISHED
        )
        passed_offering = make_offering(self.core, past)
        Enrollment.objects.create(
            student=self.student, offering=passed_offering, ca_score=25, exam_score=50, result_status=PUBLISHED
        )
        rows = {r["code"]: r for r in self.overview()["available"]}
        self.assertNotIn("CSC201", rows)  # already passed
        self.assertTrue(rows["MTH101"]["is_carryover"])
        self.assertEqual(list(rows)[0], "MTH101")  # carry-overs listed first
        self.assertTrue(self.reg(self.o_lower).data["is_carryover"])

    def test_cannot_drop_after_scores(self):
        self.reg(self.o_core)
        Enrollment.objects.filter(student=self.student).update(result_status=Enrollment.ResultStatus.DRAFT)
        self.assertIn("Scores have already been entered", str(self.reg(self.o_core, "drop").data))

    def test_only_students(self):
        self.assertEqual(self.reg(self.o_core, user=self.lecturer).status_code, 403)
        self.assertEqual(APIClient().get("/api/academics/registration/").status_code, 401)

    def test_opening_registration_notifies_students(self):
        self.semester.registration_open = False
        self.semester.save()
        registrar = make_staff(roles=["registrar"])
        res = client_for(registrar).patch(f"/api/academics/semesters/{self.semester.id}/", {"registration_open": True})
        self.assertEqual(res.status_code, 200)
        note = Notification.objects.get(user=self.student)
        self.assertIn("now open", note.title)
        self.assertEqual(note.link, "/portal/registration")


class ResultsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.programme = make_programme()
        cls.student = make_student(programme=cls.programme, level=200)
        first = make_semester("2025/2026", 1, is_current=False)
        second = make_semester("2025/2026", 2, is_current=False)
        a = make_offering(make_course(units=3), first)
        b = make_offering(make_course(units=2), first)
        c = make_offering(make_course(units=3, semester_number=2), second)
        hidden = make_offering(make_course(units=3, semester_number=2), second)
        Enrollment.objects.create(
            student=cls.student, offering=a, ca_score=25, exam_score=50, result_status=PUBLISHED
        )  # 75 A
        Enrollment.objects.create(
            student=cls.student, offering=b, ca_score=15, exam_score=37, result_status=PUBLISHED
        )  # 52 C
        Enrollment.objects.create(
            student=cls.student, offering=c, ca_score=10, exam_score=25, result_status=PUBLISHED
        )  # 35 F
        Enrollment.objects.create(
            student=cls.student,
            offering=hidden,
            ca_score=30,
            exam_score=70,
            result_status=Enrollment.ResultStatus.FACULTY_APPROVED,
        )  # not yet published

    def test_results_gpa_cgpa(self):
        data = client_for(self.student).get("/api/academics/results/").data
        by_name = {s["semester"]["name"]: s for s in data["semesters"]}
        first = by_name["First Semester 2025/2026"]
        self.assertEqual(Decimal(str(first["gpa"])), Decimal("4.20"))  # (3*5 + 2*3) / 5
        self.assertEqual([c["grade"] for c in first["courses"]], sorted([c["grade"] for c in first["courses"]]))
        second = by_name["Second Semester 2025/2026"]
        self.assertEqual(len(second["courses"]), 1)  # unpublished result hidden
        self.assertEqual(second["courses"][0]["grade"], "F")
        self.assertEqual(Decimal(str(data["cgpa"])), Decimal("2.63"))  # 21 points / 8 units
        self.assertEqual((data["units_taken"], data["units_passed"]), (8, 5))
        self.assertEqual(data["degree_class"], "Second Class (Lower Division)")


class AccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.semester = make_semester()
        cls.programme = make_programme()
        cls.lecturer = make_staff(roles=["lecturer"])
        cls.other_lecturer = make_staff(roles=["lecturer"])
        cls.hod = make_staff(roles=[("hod", cls.programme.department)])
        cls.offering = make_offering(make_course(), cls.semester, lecturer=cls.lecturer)
        cls.student = make_student(programme=cls.programme)
        add_to_curriculum(cls.programme, cls.offering.course)

    def test_roster_access(self):
        client_for(self.student).post("/api/academics/registration/", {"offering": self.offering.id})
        url = f"/api/academics/offerings/{self.offering.id}/roster/"
        self.assertEqual(APIClient().get(url).status_code, 401)
        self.assertEqual(client_for(self.other_lecturer).get(url).status_code, 403)
        self.assertEqual(client_for(self.student).get(url).status_code, 403)
        rows = client_for(self.lecturer).get(url).data
        self.assertEqual([r["matric_number"] for r in rows], [self.student.university_id])
        self.assertEqual(client_for(self.hod).get(url).status_code, 200)

    def test_structure_is_read_only_without_permission(self):
        payload = {"code": "NEW", "name": "New Faculty"}
        self.assertEqual(client_for(self.lecturer).post("/api/academics/faculties/", payload).status_code, 403)
        self.assertEqual(
            client_for(make_staff(roles=["registrar"])).post("/api/academics/faculties/", payload).status_code, 201
        )
        self.assertEqual(client_for(self.student).get("/api/academics/programmes/").status_code, 200)

    def test_scoped_roles(self):
        departments, faculties = self.hod.permission_scope("results.approve_department")
        self.assertEqual((departments, faculties), ({self.programme.department_id}, set()))
        self.assertIsNone(make_staff(roles=["registrar"]).permission_scope("attendance.view"))
        self.assertEqual(self.lecturer.permission_scope("attendance.view"), (set(), set()))
        self.assertFalse(self.hod.has_permission("finance.manage"))
        self.assertTrue(make_admin().has_permission("finance.manage", "audit.view"))

    def test_dashboards(self):
        client_for(self.student).post("/api/academics/registration/", {"offering": self.offering.id})
        student = client_for(self.student).get("/api/academics/dashboard/").data
        self.assertEqual(student["profile"]["matric_number"], self.student.university_id)
        self.assertEqual(student["registration"]["units"], 3)
        lecturer = client_for(self.lecturer).get("/api/academics/dashboard/").data
        self.assertEqual((lecturer["stats"]["courses_teaching"], lecturer["stats"]["total_students"]), (1, 1))
        self.assertEqual(lecturer["stats"]["pending_results"], 1)
        admin = client_for(make_admin()).get("/api/academics/dashboard/").data
        self.assertIn("students", admin["stats"])


class CourseManagementTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.registrar = make_staff(roles=["registrar"])
        cls.lecturer = make_staff(roles=["lecturer"])
        cls.programme = make_programme()
        cls.other_programme = make_programme(department=cls.programme.department)
        cls.first = make_semester()
        cls.second = make_semester(number=2, is_current=False)

    def payload(self, **extra):
        return {
            "code": "csc 207",
            "title": "Web Programming",
            "units": 3,
            "level": 200,
            "semester_number": 1,
            "department": self.programme.department.id,
            **extra,
        }

    def create(self, user=None, **extra):
        return client_for(user or self.registrar).post("/api/academics/courses/", self.payload(**extra), format="json")

    def test_permissions(self):
        self.assertEqual(self.create(self.lecturer).status_code, 403)
        self.assertEqual(self.create(make_student()).status_code, 403)
        self.assertEqual(self.create(make_admin()).status_code, 201)

    def test_code_is_normalised_and_unique(self):
        res = self.create()
        self.assertEqual((res.status_code, res.data["code"]), (201, "CSC207"))
        self.assertIn("CSC207 already exists in the catalogue", str(self.create(code="CSC207").data))
        self.assertIn("already exists in the catalogue", str(self.create(code="csc207").data))
        self.assertIn("CSC207", str(self.create(code="7CSC").data))  # format hint

    def test_create_with_curriculum_and_offering(self):
        res = self.create(
            curriculum=[
                {"programme": self.programme.id, "is_compulsory": True},
                {"programme": self.other_programme.id, "is_compulsory": False},
            ],
            offering={
                "semester": self.first.id,
                "lecturer": self.lecturer.id,
                "capacity": 80,
                "days": "WED,MON",
                "start_time": "10:00",
                "end_time": "12:00",
                "venue": "LT 2",
            },
        )
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual((res.data["programme_count"], res.data["offering_count"]), (2, 1))
        offering = CourseOffering.objects.get(course__code="CSC207")
        self.assertEqual((offering.days, offering.lecturer, offering.capacity), ("MON,WED", self.lecturer, 80))
        self.assertTrue(AuditLog.objects.filter(action="course.create").exists())

        # A student of the programme can now register it.
        student = make_student(programme=self.programme, level=200)
        rows = client_for(student).get("/api/academics/registration/").data["available"]
        self.assertEqual([(r["code"], r["is_compulsory"]) for r in rows], [("CSC207", True)])

    def test_all_or_nothing(self):
        bad_offering = {"semester": self.second.id}  # a First Semester course in the Second Semester
        res = self.create(curriculum=[{"programme": self.programme.id}], offering=bad_offering)
        self.assertIn("First Semester course", str(res.data))
        self.assertFalse(Course.objects.filter(code="CSC207").exists())
        res = self.create(offering={"semester": self.first.id, "lecturer": make_student().id})
        self.assertIn("isn't a lecturer", str(res.data))
        res = self.create(offering={"semester": self.first.id, "days": "MON"})
        self.assertIn("days and times together", str(res.data))
        res = self.create(curriculum=[{"programme": self.programme.id}, {"programme": self.programme.id}])
        self.assertIn("only be listed once", str(res.data))
        self.assertFalse(Course.objects.filter(code="CSC207").exists())

    def test_delete_in_use_is_refused_cleanly(self):
        course_id = self.create(offering={"semester": self.first.id}).data["id"]
        res = client_for(self.registrar).delete(f"/api/academics/courses/{course_id}/")
        self.assertEqual(res.status_code, 400)
        self.assertIn("still in use", str(res.data))
        unused = self.create(code="CSC299").data["id"]
        self.assertEqual(client_for(self.registrar).delete(f"/api/academics/courses/{unused}/").status_code, 204)

    def test_offering_semester_must_match_course(self):
        course = make_course(semester_number=1)
        res = client_for(self.registrar).post(
            "/api/academics/offerings/", {"course": course.id, "semester": self.second.id}
        )
        self.assertIn("First Semester course", str(res.data))

    def test_lecturer_list(self):
        make_staff(roles=["bursar"])
        names = [row["id"] for row in client_for(self.registrar).get("/api/academics/lecturers/").data]
        self.assertEqual(names, [self.lecturer.id])
        self.assertEqual(client_for(self.lecturer).get("/api/academics/lecturers/").status_code, 403)
