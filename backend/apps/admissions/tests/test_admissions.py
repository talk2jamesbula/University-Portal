import hashlib
import hmac
import json
import shutil
import tempfile
from datetime import date, timedelta
from io import BytesIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from openpyxl import load_workbook
from rest_framework.test import APIClient
from rest_framework.throttling import ScopedRateThrottle

from apps.core.models import AuditLog, Notification
from apps.core.testing import client_for, make_department, make_programme, make_staff

from .. import payments
from ..models import AdmissionCycle, Application, ApplicationDocument, ApplicationEvent, ApplicationPayment

User = get_user_model()
MEDIA = tempfile.mkdtemp()
PDF = b"%PDF-1.4\n%fake certificate\n"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
KEY = "sk_test_admissions"
S = Application.Status

OLEVEL = [
    {"exam": "WAEC", "year": 2025, "subject": s, "grade": g}
    for s, g in [
        ("English Language", "B3"),
        ("Mathematics", "C4"),
        ("Physics", "B2"),
        ("Chemistry", "C5"),
        ("Biology", "C6"),
        ("Economics", "A1"),
    ]
]
PERSONAL = {
    "gender": "female",
    "date_of_birth": "2007-03-14",
    "state_of_origin": "Enugu",
    "lga": "Nsukka",
    "address": "12 Okpara Avenue, Enugu",
    "phone": "08031234567",
    "next_of_kin_name": "Mrs. Ngozi Eze",
    "next_of_kin_phone": "08037654321",
}


def upload(content=PDF, name="file.pdf"):
    return SimpleUploadedFile(name, content, content_type="application/octet-stream")


@override_settings(
    MEDIA_ROOT=MEDIA,
    PAYSTACK_SECRET_KEY=KEY,
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class AdmissionsTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        today = timezone.localdate()
        cls.cycle = AdmissionCycle.objects.create(
            session="2026/2027",
            application_fee=10000,
            opens_on=today - timedelta(days=30),
            closes_on=today + timedelta(days=30),
            min_utme_score=180,
            acceptance_deadline=today + timedelta(days=60),
            resumption_date=today + timedelta(days=90),
        )
        department = make_department()
        cls.programme = make_programme(department, name="Computer Science")
        cls.second = make_programme(department, name="Mathematics")
        cls.officer = make_staff("officer", roles=["admission_officer"])
        cls.lecturer = make_staff("lect", roles=["lecturer"])

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def setUp(self):
        cache.clear()
        self.applicant = User.objects.create_user(
            "ada@example.com", email="ada@example.com", password="x", role=User.Role.APPLICANT, first_name="Ada"
        )
        self.client = client_for(self.applicant)

    def start(self):
        response = self.client.post("/api/admissions/me/")
        self.assertEqual(response.status_code, 201, response.data)
        return Application.objects.get(applicant=self.applicant)

    def complete(self, pay=True):
        """A draft that is ready to submit."""
        application = self.start()
        response = self.client.patch(
            "/api/admissions/me/",
            {
                **PERSONAL,
                "programme": self.programme.pk,
                "second_choice": self.second.pk,
                "jamb_reg_number": "20261234ab",
                "utme_score": 256,
                "olevel_results": OLEVEL,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        for kind in ApplicationDocument.REQUIRED:
            content = PNG if kind == ApplicationDocument.Kind.PASSPORT else PDF
            r = self.client.post(
                "/api/admissions/me/documents/", {"kind": kind, "file": upload(content)}, format="multipart"
            )
            self.assertEqual(r.status_code, 201, r.data)
        if pay:
            self.pay()
        return application

    def pay(self):
        """Start a Paystack checkout, then Paystack confirms the charge (as its webhook or verify would)."""
        checkout = {"authorization_url": "https://checkout.paystack.com/x"}
        with mock.patch("apps.finance.paystack._request", return_value=checkout):
            response = self.client.post("/api/admissions/me/pay/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["authorization_url"], "https://checkout.paystack.com/x")
        charge = {"amount": 1_000_000, "currency": "NGN", "channel": "card"}
        payments.record_success(response.data["payment"]["reference"], charge)

    def submitted(self):
        self.complete()
        self.assertEqual(self.client.post("/api/admissions/me/submit/").status_code, 200)
        return Application.objects.get(applicant=self.applicant)

    def officer_post(self, url, data=None):
        return client_for(self.officer).post(url, data or {}, format="json")


class SignupTests(AdmissionsTestCase):
    def test_signup_creates_an_applicant_and_signs_in(self):
        response = APIClient().post(
            "/api/admissions/register/",
            {
                "first_name": "Tunde",
                "last_name": "Bakare",
                "email": "Tunde@Example.com",
                "phone": "08012345678",
                "password": "Str0ng-pass!",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        user = User.objects.get(email="tunde@example.com")
        self.assertEqual((user.username, user.role), ("tunde@example.com", User.Role.APPLICANT))
        me = APIClient(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}").get("/api/auth/me/")
        self.assertEqual(me.data["role"], "applicant")
        self.assertTrue(AuditLog.objects.filter(action="admissions.account_created").exists())
        # And they can sign in with their email address.
        login = APIClient().post("/api/auth/token/", {"username": "tunde@example.com", "password": "Str0ng-pass!"})
        self.assertEqual(login.status_code, 200)

    def test_duplicate_email_and_weak_password(self):
        payload = {
            "first_name": "A",
            "last_name": "B",
            "email": "ada@example.com",
            "phone": "08012345678",
            "password": "password",
        }
        response = APIClient().post("/api/admissions/register/", payload, format="json")
        self.assertIn("already exists", str(response.data["email"]))
        response = APIClient().post("/api/admissions/register/", {**payload, "email": "new@example.com"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("password", str(response.data).lower())

    @mock.patch.object(ScopedRateThrottle, "THROTTLE_RATES", {"apply": "2/hour"})
    def test_signup_is_rate_limited(self):
        client = APIClient()
        codes = [client.post("/api/admissions/register/", {}, format="json").status_code for _ in range(3)]
        self.assertEqual(codes, [400, 400, 429])

    def test_public_cycle(self):
        data = APIClient().get("/api/admissions/cycle/").data["cycle"]
        self.assertEqual((data["session"], data["is_open"]), ("2026/2027", True))


class ApplicantTests(AdmissionsTestCase):
    def test_start_once_per_cycle(self):
        application = self.start()
        self.assertEqual(application.number, f"BU/APP/2627/{application.pk:05d}")
        self.assertEqual(self.client.post("/api/admissions/me/").status_code, 400)
        data = self.client.get("/api/admissions/me/").data
        self.assertEqual(data["application"]["status"], "draft")
        self.assertEqual([c["done"] for c in data["checklist"]], [False] * 5)

    def test_cannot_start_when_closed(self):
        AdmissionCycle.objects.update(closes_on=timezone.localdate() - timedelta(days=1))
        self.assertIn("not open", str(self.client.post("/api/admissions/me/").data))

    def test_field_validation(self):
        self.start()
        response = self.client.patch(
            "/api/admissions/me/",
            {
                "jamb_reg_number": "12345",
                "nin": "123",
                "date_of_birth": str(date.today()),
                "olevel_results": [OLEVEL[0], OLEVEL[0]],
            },
            format="json",
        )
        self.assertEqual(set(response.data), {"jamb_reg_number", "nin", "date_of_birth", "olevel_results"})

    def test_olevel_requirements(self):
        self.start()
        weak = [{**r, "grade": "D7"} if r["subject"] == "Mathematics" else r for r in OLEVEL]
        data = self.client.patch("/api/admissions/me/", {"olevel_results": weak}, format="json").data
        academic = next(c for c in data["checklist"] if c["key"] == "academic")
        self.assertIn("A credit pass in Mathematics is required.", academic["problems"])

    def test_documents_are_checked_by_content(self):
        self.start()
        fake = self.client.post(
            "/api/admissions/me/documents/",
            {"kind": "olevel", "file": upload(b"MZ executable", "result.pdf")},
            format="multipart",
        )
        self.assertIn("PDF, JPG or PNG", str(fake.data))
        passport_pdf = self.client.post(
            "/api/admissions/me/documents/", {"kind": "passport", "file": upload()}, format="multipart"
        )
        self.assertIn("JPG or PNG image", str(passport_pdf.data))
        # Uploading the same kind again replaces it.
        self.client.post(
            "/api/admissions/me/documents/", {"kind": "olevel", "file": upload(name="a.pdf")}, format="multipart"
        )
        self.client.post(
            "/api/admissions/me/documents/", {"kind": "olevel", "file": upload(PNG, "b.png")}, format="multipart"
        )
        self.assertEqual(list(ApplicationDocument.objects.values_list("original_filename", flat=True)), ["b.png"])

    def test_document_files_are_private(self):
        self.start()
        self.client.post("/api/admissions/me/documents/", {"kind": "olevel", "file": upload()}, format="multipart")
        document = ApplicationDocument.objects.get()
        url = f"/api/admissions/documents/{document.pk}/file/"
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(client_for(self.officer).get(url).status_code, 200)
        stranger = User.objects.create_user("x@example.com", password="x", role=User.Role.APPLICANT)
        self.assertEqual(client_for(stranger).get(url).status_code, 404)
        self.assertEqual(client_for(self.lecturer).get(url).status_code, 404)

    def test_submit_requires_a_complete_paid_application(self):
        self.complete(pay=False)
        response = self.client.post("/api/admissions/me/submit/")
        self.assertEqual(response.status_code, 400)
        self.assertIn("Pay the application fee.", response.data["problems"])

    def test_paystack_payment_submit_and_receipt(self):
        self.complete()
        payment = ApplicationPayment.objects.get()
        self.assertEqual((payment.status, payment.gateway, payment.amount), ("success", "paystack", 10000))
        self.assertIn("already paid", str(self.client.post("/api/admissions/me/pay/").data))
        receipt = self.client.get("/api/admissions/me/receipt/")
        self.assertTrue(receipt.content.startswith(b"%PDF"))

        with self.captureOnCommitCallbacks(execute=True):  # emails go out after the commit
            response = self.client.post("/api/admissions/me/submit/")
        self.assertEqual(response.data["application"]["status"], "submitted")
        application = Application.objects.get()
        self.assertIsNotNone(application.submitted_at)
        self.assertTrue(Notification.objects.filter(user=self.applicant, title="Application submitted").exists())
        self.assertTrue(any("Application submitted" in m.subject for m in mail.outbox))
        self.assertTrue(AuditLog.objects.filter(action="admissions.submitted", target_id=str(application.pk)).exists())
        # Locked after submission
        self.assertEqual(self.client.patch("/api/admissions/me/", {"lga": "Udi"}, format="json").status_code, 400)
        blocked = self.client.post(
            "/api/admissions/me/documents/", {"kind": "olevel", "file": upload()}, format="multipart"
        )
        self.assertIn("can't be changed", str(blocked.data))
        timeline = [e["to_status"] for e in response.data["timeline"]]
        self.assertEqual(timeline[0], "draft")
        self.assertEqual(timeline[-1], "submitted")

    @override_settings(PAYSTACK_SECRET_KEY="", DEBUG=True)
    def test_no_payment_without_paystack(self):
        self.complete(pay=False)
        response = self.client.post("/api/admissions/me/pay/")
        self.assertIn("not available", str(response.data))
        self.assertFalse(ApplicationPayment.objects.exists())
        self.assertIsNone(self.client.get("/api/admissions/me/").data["gateway"])

    def test_cannot_submit_after_closing(self):
        self.complete()
        AdmissionCycle.objects.update(closes_on=timezone.localdate() - timedelta(days=1))
        self.assertIn("closed", str(self.client.post("/api/admissions/me/submit/").data))

    def test_utme_cut_off(self):
        self.complete()
        data = self.client.patch("/api/admissions/me/", {"utme_score": 150}, format="json").data
        academic = next(c for c in data["checklist"] if c["key"] == "academic")
        self.assertIn("The minimum UTME score for this admission is 180.", academic["problems"])

    def test_staff_cannot_use_applicant_endpoints(self):
        self.assertEqual(client_for(self.officer).get("/api/admissions/me/").status_code, 403)
        self.assertEqual(self.client.get("/api/admissions/applications/").status_code, 403)
        self.assertEqual(client_for(self.lecturer).get("/api/admissions/applications/").status_code, 403)


@override_settings(PAYSTACK_SECRET_KEY=KEY)
class PaystackTests(AdmissionsTestCase):
    def initialize(self):
        with mock.patch(
            "apps.finance.paystack._request", return_value={"authorization_url": "https://checkout.paystack.com/x"}
        ) as req:
            response = self.client.post("/api/admissions/me/pay/")
        self.assertEqual(response.data["authorization_url"], "https://checkout.paystack.com/x")
        body = req.call_args.kwargs["json"]
        self.assertEqual((body["amount"], body["email"]), (1_000_000, "ada@example.com"))
        return ApplicationPayment.objects.get(reference=response.data["payment"]["reference"])

    def test_verify_records_payment(self):
        self.complete(pay=False)
        payment = self.initialize()
        self.assertTrue(payment.reference.startswith("APP-"))
        charge = {"status": "success", "amount": 1_000_000, "currency": "NGN", "channel": "card"}
        with mock.patch("apps.finance.paystack._request", return_value=charge):
            response = self.client.post(
                "/api/admissions/me/pay/verify/", {"reference": payment.reference}, format="json"
            )
        self.assertEqual(response.data["status"], "success")
        self.assertTrue(Application.objects.get().fee_paid)

    def test_amount_mismatch_and_double_payment(self):
        self.complete(pay=False)
        first, second, third = self.initialize(), self.initialize(), self.initialize()
        payments.record_success(first.reference, {"amount": 100, "currency": "NGN"})
        first.refresh_from_db()
        self.assertEqual(first.status, "failed")
        payments.record_success(second.reference, {"amount": 1_000_000, "currency": "NGN"})
        payments.record_success(third.reference, {"amount": 1_000_000, "currency": "NGN"})
        third.refresh_from_db()
        self.assertEqual(third.status, "failed")
        self.assertIn("Duplicate", third.gateway_response)
        self.assertEqual(ApplicationPayment.objects.filter(status="success").count(), 1)

    def test_shared_webhook_routes_application_fees(self):
        self.complete(pay=False)
        payment = self.initialize()
        body = json.dumps(
            {
                "event": "charge.success",
                "data": {"reference": payment.reference, "amount": 1_000_000, "currency": "NGN"},
            }
        ).encode()
        bad = APIClient().post(
            "/api/finance/paystack/webhook/", body, content_type="application/json", HTTP_X_PAYSTACK_SIGNATURE="nope"
        )
        self.assertEqual(bad.status_code, 401)
        signature = hmac.new(KEY.encode(), body, hashlib.sha512).hexdigest()
        ok = APIClient().post(
            "/api/finance/paystack/webhook/", body, content_type="application/json", HTTP_X_PAYSTACK_SIGNATURE=signature
        )
        self.assertEqual(ok.status_code, 200)
        payment.refresh_from_db()
        self.assertEqual(payment.status, "success")


class OfficerWorkflowTests(AdmissionsTestCase):
    def setUp(self):
        super().setUp()
        self.application = self.submitted()
        self.base = f"/api/admissions/applications/{self.application.pk}/"

    def verify_all(self):
        for document in self.application.documents.all():
            r = self.officer_post(f"/api/admissions/documents/{document.pk}/review/", {"verified": True})
            self.assertEqual(r.status_code, 200, r.data)

    def status(self):
        self.application.refresh_from_db()
        return self.application.status

    def test_full_workflow_to_acceptance(self):
        self.assertEqual(self.officer_post(self.base + "start-review/").data["application"]["status"], "under_review")
        self.assertIn("Verify these documents first", str(self.officer_post(self.base + "to-screening/").data))
        self.verify_all()
        detail = self.officer_post(self.base + "to-screening/").data
        self.assertEqual(detail["application"]["status"], "screening")
        self.assertIn("record_screening", detail["actions"])
        self.assertNotIn("approve", detail["actions"])
        self.assertIn(
            "Record the screening", str(self.officer_post(self.base + "decide/", {"decision": "approve"}).data)
        )

        detail = self.officer_post(self.base + "screening/", {"score": "72.5", "remarks": "Good interview"}).data
        self.assertEqual(detail["application"]["aggregate_score"], 68.25)  # 256/8 + 72.5/2
        detail = self.officer_post(self.base + "decide/", {"decision": "approve", "programme": self.second.pk}).data
        self.assertEqual(detail["application"]["status"], "approved")
        self.assertEqual(detail["application"]["admitted_programme"], self.second.pk)

        detail = self.officer_post(self.base + "issue-letter/").data
        self.assertEqual(detail["application"]["status"], "admitted")
        self.assertEqual(detail["application"]["letter_number"], f"BU/ADM/2627/{self.application.pk:05d}")
        self.assertTrue(
            Notification.objects.filter(user=self.applicant, title="Offer of provisional admission").exists()
        )

        letter = self.client.get("/api/admissions/me/letter/")
        self.assertEqual(letter["Content-Type"], "application/pdf")
        self.assertTrue(letter.content.startswith(b"%PDF"))
        self.assertEqual(client_for(self.officer).get(self.base + "letter/").status_code, 200)

        self.assertEqual(self.client.post("/api/admissions/me/accept/").data["application"]["status"], "accepted")
        statuses = list(self.application.events.exclude(to_status="").values_list("to_status", flat=True))
        self.assertEqual(
            statuses, ["draft", "submitted", "under_review", "screening", "approved", "admitted", "accepted"]
        )
        audited = set(AuditLog.objects.filter(target_id=str(self.application.pk)).values_list("action", flat=True))
        self.assertTrue(
            {"admissions.under_review", "admissions.screening", "admissions.approved", "admissions.admitted"} <= audited
        )

    def test_letter_only_after_admission(self):
        self.assertEqual(self.client.get("/api/admissions/me/letter/").status_code, 404)
        self.assertIn("can't be moved", str(self.officer_post(self.base + "issue-letter/").data))

    def test_rejecting_a_document_asks_for_a_new_one(self):
        document = self.application.documents.get(kind="olevel")
        url = f"/api/admissions/documents/{document.pk}/review/"
        self.assertIn("what is wrong", str(self.officer_post(url, {"verified": False}).data))
        self.officer_post(url, {"verified": False, "note": "The scan is unreadable"})
        self.assertEqual(self.status(), "under_review")  # reviewing a document starts the review
        self.assertTrue(Notification.objects.filter(user=self.applicant, title="Please replace a document").exists())
        # The applicant may replace that document only.
        ok = self.client.post("/api/admissions/me/documents/", {"kind": "olevel", "file": upload()}, format="multipart")
        self.assertEqual(ok.status_code, 201)
        self.assertEqual(ApplicationDocument.objects.get(kind="olevel").status, "pending")
        other = self.client.post(
            "/api/admissions/me/documents/", {"kind": "jamb_result", "file": upload()}, format="multipart"
        )
        self.assertEqual(other.status_code, 400)

    def test_reject_and_waitlist_need_a_reason(self):
        self.officer_post(self.base + "start-review/")
        self.assertIn("reason", str(self.officer_post(self.base + "decide/", {"decision": "reject"}).data))
        with self.captureOnCommitCallbacks(execute=True):
            self.officer_post(self.base + "decide/", {"decision": "reject", "note": "Forged O-Level result"})
        self.assertEqual(self.status(), "rejected")
        email = next(m for m in mail.outbox if m.subject == "Update on your application")
        self.assertIn("Forged O-Level result", email.body)
        self.assertEqual(self.officer_post(self.base + "start-review/").status_code, 400)

    def test_waitlist_then_approve(self):
        self.officer_post(self.base + "start-review/")
        self.verify_all()
        self.officer_post(self.base + "to-screening/")
        self.officer_post(self.base + "screening/", {"score": 55})
        self.officer_post(self.base + "decide/", {"decision": "waitlist", "note": "Quota filled"})
        self.assertEqual(self.status(), "waitlisted")
        stranger = make_programme(make_department())
        wrong = self.officer_post(self.base + "decide/", {"decision": "approve", "programme": stranger.pk})
        self.assertIn("first or second choice", str(wrong.data))
        self.officer_post(self.base + "decide/", {"decision": "approve"})
        self.assertEqual(self.status(), "approved")
        self.assertEqual(self.application.admitted_programme, self.programme)

    def test_acceptance_deadline(self):
        Application.objects.filter(pk=self.application.pk).update(status=S.ADMITTED, admitted_programme=self.programme)
        AdmissionCycle.objects.update(acceptance_deadline=timezone.localdate() - timedelta(days=1))
        self.assertIn("deadline", str(self.client.post("/api/admissions/me/accept/").data))

    def test_internal_notes_are_hidden_from_the_applicant(self):
        self.officer_post(self.base + "note/", {"note": "Check the WAEC scratch card"})
        officer_view = client_for(self.officer).get(self.base).data["timeline"]
        self.assertIn("Check the WAEC scratch card", [e["note"] for e in officer_view])
        applicant_view = self.client.get("/api/admissions/me/").data["timeline"]
        self.assertNotIn("Check the WAEC scratch card", [e["note"] for e in applicant_view])

    def test_lecturer_cannot_review(self):
        response = client_for(self.lecturer).post(self.base + "start-review/")
        self.assertEqual(response.status_code, 403)
        self.assertFalse(ApplicationEvent.objects.filter(to_status="under_review").exists())


class ListAndReportTests(AdmissionsTestCase):
    def setUp(self):
        super().setUp()
        self.submitted()
        # A second applicant still drafting
        drafter = User.objects.create_user(
            "bola@example.com", email="bola@example.com", password="x", role=User.Role.APPLICANT
        )
        self.client = client_for(drafter)
        self.start()
        self.officer = client_for(self.officer)

    def test_list_search_filter_and_summary(self):
        rows = self.officer.get("/api/admissions/applications/").data["results"]
        self.assertEqual([r["applicant_name"] for r in rows], ["Ada"])  # drafts hidden by default
        self.assertTrue(rows[0]["fee_paid"])
        self.assertEqual(rows[0]["documents_pending"], 4)
        self.assertEqual(self.officer.get("/api/admissions/applications/?status=draft").data["count"], 1)
        self.assertEqual(self.officer.get("/api/admissions/applications/?search=20261234AB").data["count"], 1)
        self.assertEqual(self.officer.get("/api/admissions/applications/?search=nobody").data["count"], 0)
        faculty = self.programme.department.faculty_id
        self.assertEqual(
            self.officer.get(f"/api/admissions/applications/?programme__department__faculty={faculty}").data["count"], 1
        )
        self.assertEqual(self.officer.get("/api/admissions/applications/?fee_paid=false").data["count"], 0)
        summary = self.officer.get("/api/admissions/applications/summary/").data
        self.assertEqual((summary["by_status"]["submitted"], summary["by_status"]["draft"]), (1, 1))
        self.assertEqual(summary["submitted_total"], 1)

    def test_exports(self):
        csv = self.officer.get("/api/admissions/applications/export/?file=csv")
        lines = csv.content.decode("utf-8-sig").strip().splitlines()
        self.assertTrue(lines[0].startswith("Application no.,Surname,First name"))
        self.assertEqual(len(lines), 2)
        xlsx = self.officer.get("/api/admissions/applications/export/?file=xlsx&status=submitted")
        sheet = load_workbook(BytesIO(xlsx.content)).active
        self.assertEqual(sheet["A2"].value, Application.objects.get(status="submitted").number)
        self.assertTrue(AuditLog.objects.filter(action="admissions.export").exists())


class ApplicantBoundaryTests(AdmissionsTestCase):
    def test_applicants_cannot_see_university_internals(self):
        self.assertEqual(self.client.get("/api/academics/dashboard/").status_code, 403)
        self.assertEqual(self.client.get("/api/directory/").status_code, 403)
        self.assertEqual(self.client.get("/api/finance/accounts/").status_code, 403)
        self.assertEqual(self.client.get("/api/attendance/me/").status_code, 403)
