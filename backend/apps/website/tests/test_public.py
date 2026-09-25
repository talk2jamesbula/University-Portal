import tempfile
from datetime import timedelta
from io import BytesIO
from unittest import mock

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient
from rest_framework.throttling import ScopedRateThrottle

from apps.campus.models import Announcement, Event
from apps.core.testing import (
    add_to_curriculum,
    client_for,
    make_course,
    make_department,
    make_programme,
    make_staff,
    make_student,
)
from apps.website.models import ContactMessage


class PublicApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.programme = make_programme(name="Computer Science")
        make_student(programme=cls.programme)
        core = make_course(department=cls.programme.department, code="CSC101", units=3, level=100)
        elective = make_course(department=cls.programme.department, code="CSC205", units=2, level=200)
        second = make_course(department=cls.programme.department, code="CSC102", units=3, level=100, semester_number=2)
        add_to_curriculum(cls.programme, core, second)
        add_to_curriculum(cls.programme, elective, compulsory=False)
        cls.public = Announcement.objects.create(title="Convocation", body="Open to all. " * 30, is_public=True)
        cls.private = Announcement.objects.create(title="Senate meeting", body="Staff only.")
        soon = timezone.now() + timedelta(days=3)
        Event.objects.create(title="Open day", starts_at=soon)
        Event.objects.create(title="Internal retreat", starts_at=soon, is_public=False)

    def setUp(self):
        self.client = APIClient()  # no credentials: everything here must work signed out

    def test_overview(self):
        data = self.client.get("/api/public/overview/").data
        self.assertEqual((data["stats"]["programmes"], data["stats"]["students"]), (1, 1))
        self.assertEqual([n["title"] for n in data["news"]], ["Convocation"])
        self.assertEqual([e["title"] for e in data["events"]], ["Open day"])
        self.assertTrue(data["news"][0]["summary"].endswith("…"))

    def test_private_news_is_never_exposed(self):
        titles = [n["title"] for n in self.client.get("/api/public/news/").data["results"]]
        self.assertEqual(titles, ["Convocation"])
        self.assertEqual(self.client.get(f"/api/public/news/{self.private.id}/").status_code, 404)
        self.assertEqual(self.client.get(f"/api/public/news/{self.public.id}/").status_code, 200)

    def test_faculties_and_programme_curriculum(self):
        faculties = self.client.get("/api/public/faculties/").data
        programme = faculties[0]["departments"][0]["programmes"][0]
        self.assertEqual(programme["title"], "B.Sc. Computer Science")
        detail = self.client.get(f"/api/public/programmes/{self.programme.code.lower()}/").data
        levels = {row["level"]: row for row in detail["curriculum"]}
        first_year = {s["name"]: s for s in levels[100]["semesters"]}
        self.assertEqual(first_year["First Semester"]["units"], 3)
        self.assertEqual([c["code"] for c in first_year["Second Semester"]["courses"]], ["CSC102"])
        self.assertFalse(levels[200]["semesters"][0]["courses"][0]["is_compulsory"])
        self.assertEqual(self.client.get("/api/public/programmes/NOPE/").status_code, 404)


# DRF reads throttle rates when it's imported, so patch the rate table rather than settings.
@mock.patch.object(ScopedRateThrottle, "THROTTLE_RATES", {"contact": "2/hour"})
class ContactTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()

    def send(self, **extra):
        body = {
            "name": "Ada Obi",
            "email": "ada@example.com",
            "topic": "admissions",
            "subject": "Entry requirements",
            "message": "What are the requirements for Computer Science?",
            **extra,
        }
        return self.client.post("/api/public/contact/", body)

    def test_contact_form(self):
        self.assertEqual(self.send().status_code, 201)
        message = ContactMessage.objects.get()
        self.assertEqual((message.topic, message.ip_address), ("admissions", "127.0.0.1"))
        self.assertEqual(self.send(email="not-an-email").status_code, 400)

    def test_honeypot_and_short_messages(self):
        self.assertEqual(self.send(website="http://spam.example").status_code, 400)
        self.assertIn("a little more", str(self.send(message="hi").data))
        self.assertEqual(ContactMessage.objects.count(), 0)

    def test_rate_limited(self):
        self.send()
        self.send()
        self.assertEqual(self.send().status_code, 429)


class LeadershipTests(TestCase):
    def test_leadership_from_role_appointments(self):
        department = make_department(name="Computer Science")
        make_staff(roles=["registrar"], first_name="Folasade", last_name="Adeyemi", title="Mrs.")
        make_staff(roles=["vc"], first_name="Aminu", last_name="Bello", title="Prof.")
        make_staff(roles=[("dean", department.faculty)], first_name="Ngozi", last_name="Eze")
        make_staff(roles=[("hod", department), "lecturer"], first_name="Ada", last_name="Obi")
        make_staff(roles=["lecturer"], first_name="Not", last_name="Listed")
        data = APIClient().get("/api/public/leadership/").data
        self.assertEqual(
            [p["name"] for p in data["principal_officers"]], ["Prof. Aminu Bello", "Mrs. Folasade Adeyemi"]
        )
        self.assertEqual(data["deans"][0]["role"], f"Dean, {department.faculty.name}")
        self.assertEqual(data["heads_of_department"][0]["role"], "Head, Department of Computer Science")
        names = str(data)
        self.assertNotIn("Not Listed", names)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class StaffPhotoTests(TestCase):
    def test_registry_uploads_staff_photo_shown_on_website(self):
        registrar = make_staff(roles=["registrar"])
        vc = make_staff(roles=["vc"])
        buf = BytesIO()
        Image.new("RGB", (600, 400), "navy").save(buf, "JPEG")
        photo = SimpleUploadedFile("vc.jpg", buf.getvalue())
        url = f"/api/users/{vc.id}/avatar/"
        self.assertEqual(client_for(make_staff(roles=["lecturer"])).post(url, {"avatar": photo}).status_code, 403)
        photo.seek(0)
        res = client_for(registrar).post(url, {"avatar": photo}, format="multipart")
        self.assertEqual(res.status_code, 200, res.data)
        officers = APIClient().get("/api/public/leadership/").data["principal_officers"]
        vc_row = next(p for p in officers if p["role"] == "Vice Chancellor")
        self.assertTrue(vc_row["photo_url"].startswith("/media/avatars/"))
        self.assertEqual(client_for(registrar).delete(url).data["avatar_url"], None)
