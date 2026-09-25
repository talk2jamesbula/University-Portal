from datetime import date
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.academics.models import Semester
from apps.core.testing import make_staff
from apps.finance.documents import amount_in_words
from apps.finance.models import Charge, Payment
from apps.finance.services import allocate_payments

User = get_user_model()


@override_settings(PAYSTACK_SECRET_KEY="", EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class DocumentTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.semester = Semester.objects.create(
            session="2026/2027", number=1, start_date=date(2026, 9, 1), end_date=date(2026, 12, 15)
        )
        cls.student = User.objects.create_user(
            "stu", password="x", role=User.Role.STUDENT, email="stu@uni.edu", first_name="Ada", university_id="S1"
        )
        cls.other = User.objects.create_user("stu2", password="x", role=User.Role.STUDENT)
        cls.prof = make_staff("prof", roles=["lecturer"])
        cls.admin = User.objects.create_user("adm", password="x", role=User.Role.ADMIN)
        cls.tuition = Charge.objects.create(
            student=cls.student, semester=cls.semester, description="Tuition", amount=1000, due_date=date(2026, 9, 30)
        )
        cls.fee = Charge.objects.create(
            student=cls.student, semester=cls.semester, description="Library", amount=200, due_date=date(2026, 10, 30)
        )

    def client_for(self, user):
        client = APIClient()
        client.force_authenticate(user)
        return client

    def pay(self, amount):
        with self.captureOnCommitCallbacks(execute=True):
            res = self.client_for(self.admin).post(
                "/api/finance/payments/", {"student": self.student.id, "amount": amount, "method": "bank_transfer"}
            )
        self.assertEqual(res.status_code, 201)
        return res.data

    def test_payment_emails_pdf_receipt(self):
        payment = self.pay("1100")
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.to, ["stu@uni.edu"])
        self.assertIn(payment["receipt_number"], email.subject)
        name, content, mimetype = email.attachments[0]
        self.assertEqual((name, mimetype), (f"{payment['receipt_number']}.pdf", "application/pdf"))
        self.assertTrue(content.startswith(b"%PDF"))

    def test_admin_recorded_payment_also_emails(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.client_for(self.admin).post(
                "/api/finance/payments/", {"student": self.student.id, "amount": "50", "method": "cash"}
            )
        self.assertEqual(len(mail.outbox), 1)

    def test_paystack_payment_emails_receipt(self):
        with (
            override_settings(PAYSTACK_SECRET_KEY="sk_test"),
            mock.patch("apps.finance.paystack.requests.request") as req,
        ):
            req.return_value = mock.Mock(
                ok=True, json=lambda: {"status": True, "data": {"authorization_url": "https://x"}}
            )
            ref = (
                self.client_for(self.student)
                .post("/api/finance/paystack/initialize/", {"amount": "300"})
                .data["reference"]
            )
            req.return_value = mock.Mock(
                ok=True,
                json=lambda: {
                    "status": True,
                    "data": {
                        "reference": ref,
                        "status": "success",
                        "amount": 30000,
                        "currency": "NGN",
                        "channel": "bank_transfer",
                    },
                },
            )
            with self.captureOnCommitCallbacks(execute=True):
                self.client_for(self.student).post("/api/finance/paystack/verify/", {"reference": ref})
        self.assertEqual(len(mail.outbox), 1)

    def test_receipt_pdf_access(self):
        payment = self.pay("100")
        url = f"/api/finance/payments/{payment['id']}/receipt/"
        res = self.client_for(self.student).get(url)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res["Content-Type"], "application/pdf")
        self.assertIn("attachment", res["Content-Disposition"])
        self.assertTrue(res.content.startswith(b"%PDF"))
        self.assertIn("inline", self.client_for(self.student).get(url, {"inline": "1"})["Content-Disposition"])
        self.assertEqual(self.client_for(self.other).get(url).status_code, 404)
        self.assertEqual(self.client_for(self.prof).get(url).status_code, 403)
        self.assertEqual(self.client_for(self.admin).get(url).status_code, 200)

    def test_invoice_pdf_access(self):
        res = self.client_for(self.student).get("/api/finance/invoice/", {"semester": self.semester.id})
        self.assertEqual(res.status_code, 200)
        self.assertIn("INV-2627-1-S1.pdf", res["Content-Disposition"])
        admin = self.client_for(self.admin).get(
            "/api/finance/invoice/", {"semester": self.semester.id, "student": self.student.id}
        )
        self.assertEqual(admin.status_code, 200)
        # A student can't request someone else's invoice; ?student is ignored for them.
        other = self.client_for(self.other).get(
            "/api/finance/invoice/", {"semester": self.semester.id, "student": self.student.id}
        )
        self.assertEqual(other.status_code, 400)
        self.assertEqual(
            self.client_for(self.prof).get("/api/finance/invoice/", {"semester": self.semester.id}).status_code, 403
        )

    def test_allocation_splits_payments_across_charges(self):
        first = Payment.objects.create(student=self.student, amount=700)
        second = Payment.objects.create(student=self.student, amount=400)
        by_payment, by_charge = allocate_payments(self.student)
        self.assertEqual([(c.description, a) for c, a in by_payment[first.id]], [("Tuition", Decimal("700"))])
        self.assertEqual(
            [(c.description, a) for c, a in by_payment[second.id]],
            [("Tuition", Decimal("300")), ("Library", Decimal("100"))],
        )
        self.assertEqual(by_charge[self.fee.id], Decimal("100"))

    def test_amount_in_words(self):
        self.assertEqual(amount_in_words("3080"), "Three thousand and eighty naira only")
        self.assertEqual(amount_in_words("1000.50"), "One thousand naira, fifty kobo only")
        self.assertEqual(amount_in_words("2580000"), "Two million five hundred and eighty thousand naira only")
