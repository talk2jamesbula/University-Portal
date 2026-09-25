from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.academics.models import Enrollment
from apps.accounts.models import StudentProfile
from apps.admissions.models import AdmissionCycle, Application
from apps.attendance.models import AttendanceRecord, AttendanceSession
from apps.core.testing import (
    client_for,
    make_course,
    make_department,
    make_faculty,
    make_offering,
    make_programme,
    make_semester,
    make_staff,
    make_student,
)
from apps.finance.models import Charge, Payment

User = get_user_model()
URL = "/api/reports/analytics/"


class AnalyticsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.semester = make_semester()
        cls.science = make_faculty(name="Science")
        cls.arts = make_faculty(name="Arts")
        csc = make_department(cls.science, name="Computer Science")
        eng = make_department(cls.arts, name="English")
        cls.csc_prog = make_programme(csc, name="Computer Science")
        cls.eng_prog = make_programme(eng, name="English")
        cls.a = make_student(programme=cls.csc_prog, level=100)
        cls.b = make_student(programme=cls.csc_prog, level=200)
        cls.c = make_student(programme=cls.eng_prog, level=100)
        StudentProfile.objects.filter(user=cls.c).update(status=StudentProfile.Status.SUSPENDED)

        course = make_course(csc, units=3)
        offering = make_offering(course, cls.semester)
        for student, ca, exam in ((cls.a, 25, 55), (cls.b, 10, 20)):  # A (80) and F (30)
            Enrollment.objects.create(
                student=student,
                offering=offering,
                ca_score=ca,
                exam_score=exam,
                result_status=Enrollment.ResultStatus.PUBLISHED,
            )
        session = AttendanceSession.objects.create(
            offering=offering,
            date=timezone.localdate(),
            start_time=offering.start_time,
            status=AttendanceSession.Status.CLOSED,
        )
        AttendanceRecord.objects.create(session=session, student=cls.a, status="present")
        AttendanceRecord.objects.create(session=session, student=cls.b, status="absent")

        Charge.objects.create(student=cls.a, description="Tuition", amount=1000, due_date=timezone.localdate())
        Charge.objects.create(student=cls.c, description="Tuition", amount=500, due_date=timezone.localdate())
        Payment.objects.create(student=cls.a, amount=Decimal("600"), method=Payment.Method.PAYSTACK)

        today = timezone.localdate()
        cycle = AdmissionCycle.objects.create(
            session="2026/2027", opens_on=today - timedelta(days=5), closes_on=today + timedelta(days=5)
        )
        applicant = User.objects.create_user("app@example.com", password="x", role=User.Role.APPLICANT)
        Application.objects.create(
            cycle=cycle,
            applicant=applicant,
            programme=cls.csc_prog,
            status=Application.Status.ADMITTED,
            submitted_at=timezone.now(),
        )

        cls.vc = make_staff("vc", roles=["vc"])
        cls.dean = make_staff("dean", roles=[("dean", cls.science)])
        cls.lecturer = make_staff("lect", roles=["lecturer"])

    def test_university_wide_figures(self):
        data = client_for(self.vc).get(URL).data
        self.assertEqual(data["scope"], "Whole university")
        self.assertEqual(data["students"]["total"], 2)  # the suspended student isn't counted as in school
        self.assertIn({"key": "suspended", "label": "Suspended", "value": 1}, data["students"]["by_status"])
        self.assertEqual(data["registration"]["registered"], 2)
        academics = data["academics"]
        self.assertEqual(academics["grade_distribution"][0], {"label": "A", "value": 1})
        self.assertEqual(academics["grade_distribution"][-1], {"label": "F", "value": 1})
        self.assertEqual(academics["pass_rate"], 50.0)
        self.assertEqual(academics["gpa_by_department"], [{"label": "Computer Science", "value": 2.5}])
        self.assertEqual(data["attendance"]["overall"], 50.0)
        finance = data["finance"]
        self.assertEqual((finance["charged"], finance["paid"], finance["collection_rate"]), (1500.0, 600.0, 40.0))
        self.assertEqual(len(finance["monthly"]), 12)
        self.assertEqual(finance["monthly"][-1]["value"], 600.0)
        self.assertEqual(data["admissions"]["funnel"][0], {"label": "Started", "value": 1})
        self.assertEqual(data["admissions"]["funnel"][3], {"label": "Offered", "value": 1})

    def test_dean_sees_only_their_faculty_and_no_fees(self):
        data = client_for(self.dean).get(URL).data
        self.assertEqual(data["scope"], "Science")
        self.assertEqual(data["students"]["total"], 2)
        self.assertEqual([r["label"] for r in data["students"]["by_faculty"]], ["Science"])
        self.assertIsNone(data["finance"])

    def test_needs_reports_permission(self):
        self.assertEqual(client_for(self.lecturer).get(URL).status_code, 403)
        self.assertEqual(client_for(self.a).get(URL).status_code, 403)
