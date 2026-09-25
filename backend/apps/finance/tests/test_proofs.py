import os
import shutil
import tempfile
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.testing import make_staff
from apps.finance.models import Charge, Payment, PaymentProof

User = get_user_model()
MEDIA = tempfile.mkdtemp()
PDF = b"%PDF-1.4\n%fake teller\n"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


def upload(content=PDF, name="teller.pdf"):
    return SimpleUploadedFile(name, content, content_type="application/octet-stream")


@override_settings(
    MEDIA_ROOT=MEDIA,
    BURSARY_NOTIFY_EMAIL="bursary@uni.edu",
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class PaymentProofTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.student = User.objects.create_user(
            "stu", password="x", role=User.Role.STUDENT, email="stu@uni.edu", first_name="Ada"
        )
        cls.other = User.objects.create_user("stu2", password="x", role=User.Role.STUDENT)
        cls.prof = make_staff("prof", roles=["lecturer"])
        cls.admin = User.objects.create_user("adm", password="x", role=User.Role.ADMIN)
        Charge.objects.create(student=cls.student, description="Tuition", amount=100000, due_date=date(2099, 1, 1))

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def client_for(self, user):
        client = APIClient()
        client.force_authenticate(user)
        return client

    def submit(self, user=None, **overrides):
        data = {
            "amount": "50000",
            "method": "bank_deposit",
            "bank_name": "First Bank",
            "reference": "ft 2026 0912 44",
            "payment_date": (timezone.localdate() - timedelta(days=2)).isoformat(),
            "file": upload(),
            **overrides,
        }
        with self.captureOnCommitCallbacks(execute=True):
            return self.client_for(user or self.student).post("/api/finance/payment-proofs/", data, format="multipart")

    def balance(self):
        return self.client_for(self.student).get("/api/finance/account/").data["balance"]

    def test_submit_is_pending_and_does_not_change_balance(self):
        res = self.submit()
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual((res.data["status"], res.data["reference"]), ("pending", "FT2026091244"))
        self.assertEqual(res.data["content_type"], "application/pdf")
        self.assertEqual(self.balance(), 100000)
        self.assertEqual(mail.outbox[0].to, ["bursary@uni.edu"])  # bursary notified

    def test_file_validation(self):
        self.assertIn("PDF, JPG or PNG", str(self.submit(file=upload(b"MZ\x90\x00 not a pdf", "teller.pdf")).data))
        big = upload(PDF + b"0" * (5 * 1024 * 1024))
        self.assertIn("too large", str(self.submit(file=big).data))
        res = self.submit(file=upload(PNG, "alert.jpeg"), reference="REF-PNG-1")
        self.assertEqual(res.data["content_type"], "image/png")
        self.assertTrue(res.data["original_filename"].endswith(".png"))

    def test_field_validation(self):
        tomorrow = (timezone.localdate() + timedelta(days=1)).isoformat()
        self.assertIn("future", str(self.submit(payment_date=tomorrow).data))
        self.assertIn("bank", str(self.submit(bank_name="").data))
        self.assertEqual(self.submit(method="cash", bank_name="", reference="CASH-001").status_code, 201)
        self.assertEqual(self.submit(amount="0").status_code, 400)

    def test_duplicate_reference_rejected(self):
        self.submit()
        self.assertIn("already been submitted", str(self.submit(user=self.other, reference="FT2026091244").data))

    def test_permissions(self):
        proof_id = self.submit().data["id"]
        self.assertEqual(self.submit(user=self.admin).status_code, 403)
        self.assertEqual(self.client_for(self.prof).get("/api/finance/payment-proofs/").status_code, 403)
        other = self.client_for(self.other)
        self.assertEqual(other.get("/api/finance/payment-proofs/").data["results"], [])
        self.assertEqual(other.get(f"/api/finance/payment-proofs/{proof_id}/file/").status_code, 404)
        self.assertEqual(
            self.client_for(self.student).post(f"/api/finance/payment-proofs/{proof_id}/approve/").status_code, 403
        )

        res = self.client_for(self.student).get(f"/api/finance/payment-proofs/{proof_id}/file/")
        self.assertEqual((res.status_code, res["Content-Type"]), (200, "application/pdf"))
        self.assertEqual(b"".join(res.streaming_content), PDF)
        res.close()
        res = self.client_for(self.admin).get(f"/api/finance/payment-proofs/{proof_id}/file/")
        self.assertEqual(res.status_code, 200)
        res.close()

    def test_approve_records_payment_and_emails_receipt(self):
        proof_id = self.submit().data["id"]
        mail.outbox.clear()
        admin = self.client_for(self.admin)
        with self.captureOnCommitCallbacks(execute=True):
            res = admin.post(f"/api/finance/payment-proofs/{proof_id}/approve/", {"amount": "45000"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["status"], "approved")
        self.assertIn("corrected", res.data["review_note"])
        self.assertTrue(res.data["receipt_number"].startswith("RCP-"))
        payment = Payment.objects.get()
        self.assertEqual((payment.method, payment.reference, payment.amount), ("bank_deposit", "FT2026091244", 45000))
        self.assertEqual(self.balance(), 55000)
        self.assertEqual(mail.outbox[0].to, ["stu@uni.edu"])
        self.assertTrue(mail.outbox[0].attachments[0][0].endswith(".pdf"))
        # No double approval.
        self.assertEqual(admin.post(f"/api/finance/payment-proofs/{proof_id}/approve/").status_code, 400)
        self.assertEqual(Payment.objects.count(), 1)
        # Approved reference can't be reused.
        self.assertEqual(self.submit().status_code, 400)

    def test_reject_requires_reason_and_notifies(self):
        proof_id = self.submit().data["id"]
        mail.outbox.clear()
        admin = self.client_for(self.admin)
        self.assertEqual(admin.post(f"/api/finance/payment-proofs/{proof_id}/reject/", {"reason": ""}).status_code, 400)
        with self.captureOnCommitCallbacks(execute=True):
            res = admin.post(f"/api/finance/payment-proofs/{proof_id}/reject/", {"reason": "Teller is not legible."})
        self.assertEqual(res.data["status"], "rejected")
        self.assertIn("Teller is not legible.", mail.outbox[0].body)
        self.assertEqual(Payment.objects.count(), 0)
        # A rejected reference may be resubmitted with a better scan.
        self.assertEqual(self.submit().status_code, 201)

    def test_student_can_withdraw_only_pending(self):
        proof = PaymentProof.objects.get(pk=self.submit().data["id"])
        path = proof.file.path
        self.assertEqual(
            self.client_for(self.student).delete(f"/api/finance/payment-proofs/{proof.id}/").status_code, 204
        )
        self.assertFalse(PaymentProof.objects.exists())
        self.assertFalse(os.path.exists(path))

        proof_id = self.submit(reference="SECOND-1").data["id"]
        self.client_for(self.admin).post(f"/api/finance/payment-proofs/{proof_id}/approve/")
        self.assertEqual(
            self.client_for(self.student).delete(f"/api/finance/payment-proofs/{proof_id}/").status_code, 400
        )

    def test_same_day_payment_is_not_dated_in_the_future(self):
        proof_id = self.submit(payment_date=timezone.localdate().isoformat()).data["id"]
        self.client_for(self.admin).post(f"/api/finance/payment-proofs/{proof_id}/approve/")
        self.assertLessEqual(Payment.objects.get().paid_at, timezone.now())

    def test_review_input_is_validated(self):
        proof_id = self.submit().data["id"]
        admin = self.client_for(self.admin)
        url = f"/api/finance/payment-proofs/{proof_id}"
        self.assertEqual(admin.post(f"{url}/approve/", {"amount": "NaN"}).status_code, 400)
        self.assertEqual(admin.post(f"{url}/approve/", {"amount": "-5"}).status_code, 400)
        self.assertEqual(admin.post(f"{url}/reject/", {"reason": 12345}, format="json").status_code, 200)

    def test_method_defaults_when_omitted(self):
        data = {
            "amount": "100",
            "bank_name": "First Bank",
            "reference": "NOMETHOD1",
            "payment_date": timezone.localdate().isoformat(),
            "file": upload(),
        }
        res = self.client_for(self.student).post("/api/finance/payment-proofs/", data, format="multipart")
        self.assertEqual((res.status_code, res.data.get("method")), (201, "bank_deposit"))

    def test_unicode_filename_download(self):
        proof_id = self.submit(file=upload(PDF, "reçu “bank”.pdf")).data["id"]
        res = self.client_for(self.student).get(f"/api/finance/payment-proofs/{proof_id}/file/")
        self.assertIn("filename*=utf-8''", res["Content-Disposition"])
        res.close()

    def test_deleting_proof_removes_file(self):
        proof = PaymentProof.objects.get(pk=self.submit().data["id"])
        path = proof.file.path
        proof.delete()  # e.g. from the Django admin
        self.assertFalse(os.path.exists(path))

    def test_summary_counts_pending(self):
        self.submit()
        self.assertEqual(self.client_for(self.admin).get("/api/finance/summary/").data["pending_proofs"], 1)

    @override_settings(
        BURSARY_BANK_NAME="First Bank", BURSARY_ACCOUNT_NAME="Uni Fees", BURSARY_ACCOUNT_NUMBER="0123456789"
    )
    def test_bank_account_shown_when_configured(self):
        data = self.client_for(self.student).get("/api/finance/payment-config/").data
        self.assertEqual(data["bank_account"]["account_number"], "0123456789")
