from datetime import date, timedelta
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.testing import (
    add_to_curriculum,
    make_admin,
    make_course,
    make_offering,
    make_programme,
    make_semester,
    make_staff,
    make_student,
)
from apps.finance.models import Charge, FeeType, Payment

User = get_user_model()


@override_settings(DEBUG=True, PAYSTACK_SECRET_KEY="")
class FinanceAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.semester = make_semester(tuition_per_unit=100, fee_due_date=timezone.localdate() + timedelta(days=10))
        cls.fee = FeeType.objects.create(name="Activity", amount=50)
        programme = make_programme()
        cls.student = make_student("stu", programme=programme)
        cls.other = make_student("stu2", programme=programme)
        cls.prof = make_staff("prof", roles=["lecturer"])
        cls.admin = make_admin("adm")
        cls.c1 = make_offering(make_course(units=3), cls.semester, days="MON")
        cls.c2 = make_offering(make_course(units=4), cls.semester, days="TUE")
        add_to_curriculum(programme, cls.c1.course, cls.c2.course)

    def client_for(self, user):
        client = APIClient()
        client.force_authenticate(user)
        return client

    def account(self, user=None, as_user=None):
        params = {"student": user.id} if as_user else {}
        return self.client_for(as_user or user).get("/api/finance/account/", params).data

    def test_enrollment_bills_tuition_and_fees_and_drop_rebills(self):
        s = self.client_for(self.student)
        s.post("/api/academics/registration/", {"offering": self.c1.id})
        self.assertEqual(self.account(self.student)["balance"], 3 * 100 + 50)
        s.post("/api/academics/registration/", {"offering": self.c2.id})
        acct = self.account(self.student)
        self.assertEqual(acct["balance"], 7 * 100 + 50)
        self.assertEqual(len(acct["charges"]), 2)  # tuition updated in place, fee not duplicated
        s.post("/api/academics/registration/", {"offering": self.c2.id, "action": "drop"})
        self.assertEqual(self.account(self.student)["balance"], 3 * 100 + 50)
        s.post("/api/academics/registration/", {"offering": self.c1.id, "action": "drop"})
        self.assertEqual(self.account(self.student)["charges"], [])

    @override_settings(PAYSTACK_SECRET_KEY="sk_test_x")
    def test_online_payments_only_through_paystack(self):
        self.student.email = "stu@example.com"  # Paystack needs one
        self.student.save()
        s = self.client_for(self.student)
        # Students can't record a payment themselves; online payments start a Paystack checkout.
        self.assertEqual(s.post("/api/finance/payments/", {"amount": "10", "card_last4": "4242"}).status_code, 403)
        checkout = {"status": True, "data": {"authorization_url": "https://checkout.paystack.com/x"}}
        with mock.patch(
            "apps.finance.paystack.requests.request", return_value=mock.Mock(ok=True, json=lambda: checkout)
        ):
            no_balance = s.post("/api/finance/paystack/initialize/", {"amount": "10"})
            self.assertIn("no balance", str(no_balance.data))
            s.post("/api/academics/registration/", {"offering": self.c1.id})
            self.assertEqual(s.post("/api/finance/paystack/initialize/", {"amount": "351"}).status_code, 400)
            self.assertEqual(s.post("/api/finance/paystack/initialize/", {"amount": "100.50"}).status_code, 200)

    def test_bursary_records_offline_payments_but_not_paystack_ones(self):
        self.client_for(self.student).post("/api/academics/registration/", {"offering": self.c1.id})
        a = self.client_for(self.admin)
        fake = a.post("/api/finance/payments/", {"student": self.student.id, "amount": "100", "method": "paystack"})
        self.assertEqual(fake.status_code, 400)
        self.assertIn("automatically", str(fake.data))
        res = a.post("/api/finance/payments/", {"student": self.student.id, "amount": "100.50", "method": "pos"})
        self.assertEqual(res.status_code, 201)
        self.assertTrue(res.data["receipt_number"].startswith("RCP-"))
        acct = self.account(self.student)
        self.assertEqual(acct["balance"], 249.5)
        self.assertEqual([c["status"] for c in acct["charges"]], ["partial", "unpaid"])

    def test_payments_apply_oldest_first_and_overdue(self):
        Charge.objects.create(student=self.student, description="Old", amount=100, due_date=date(2020, 1, 1))
        Charge.objects.create(student=self.student, description="New", amount=100, due_date=date(2099, 1, 1))
        Payment.objects.create(student=self.student, amount=50)
        acct = self.account(self.student)
        self.assertEqual([c["status"] for c in acct["charges"]], ["overdue", "unpaid"])
        self.assertEqual(acct["overdue"], 50)
        self.assertEqual(acct["next_due_date"], date(2099, 1, 1))

    def test_access_control(self):
        Charge.objects.create(student=self.other, description="X", amount=10, due_date=date(2099, 1, 1))
        s = self.client_for(self.student)
        self.assertEqual(s.get("/api/finance/charges/").data["results"], [])
        self.assertEqual(s.get("/api/finance/account/", {"student": self.other.id}).data["balance"], 0)
        payload = {"student": self.student.id, "description": "Fine", "amount": "5", "due_date": "2099-01-01"}
        self.assertEqual(s.post("/api/finance/charges/", payload).status_code, 403)
        self.assertEqual(s.get("/api/finance/accounts/").status_code, 403)
        self.assertEqual(self.client_for(self.prof).get("/api/finance/account/").status_code, 403)
        self.assertEqual(self.client_for(self.prof).get("/api/finance/payments/").status_code, 403)

    def test_admin_charges_payments_and_void(self):
        a = self.client_for(self.admin)
        payload = {
            "student": self.student.id,
            "category": "housing",
            "description": "Dorm",
            "amount": "800",
            "due_date": "2099-01-01",
        }
        self.assertEqual(a.post("/api/finance/charges/", payload).status_code, 201)
        self.assertEqual(a.post("/api/finance/charges/", {**payload, "student": self.prof.id}).status_code, 400)
        res = a.post("/api/finance/payments/", {"student": self.student.id, "amount": "300", "method": "bank_transfer"})
        self.assertEqual(res.status_code, 201)
        self.assertEqual(self.account(self.student, as_user=self.admin)["balance"], 500)

        rows = a.get("/api/finance/accounts/", {"balance": "outstanding"}).data["results"]
        self.assertEqual([(r["full_name"], r["balance"]) for r in rows], [("", 500)])
        summary = a.get("/api/finance/summary/").data
        self.assertEqual((summary["total_billed"], summary["total_collected"], summary["outstanding"]), (800, 300, 500))

        self.assertEqual(
            a.post(f"/api/finance/payments/{res.data['id']}/void/", {"reason": "Bounced"}).status_code, 200
        )
        self.assertEqual(self.account(self.student)["balance"], 800)
        self.assertEqual(a.post(f"/api/finance/payments/{res.data['id']}/void/").status_code, 400)

    def test_automatic_charges_are_locked(self):
        self.client_for(self.student).post("/api/academics/registration/", {"offering": self.c1.id})
        tuition = Charge.objects.get(auto_key="tuition")
        a = self.client_for(self.admin)
        self.assertEqual(a.delete(f"/api/finance/charges/{tuition.id}/").status_code, 400)
        self.assertEqual(a.patch(f"/api/finance/charges/{tuition.id}/", {"amount": "1"}).status_code, 400)
        self.assertEqual(Charge.objects.get(pk=tuition.pk).amount, Decimal("300.00"))

    def test_void_rejects_non_text_reason_gracefully(self):
        payment = Payment.objects.create(student=self.student, amount=10)
        res = self.client_for(self.admin).post(
            f"/api/finance/payments/{payment.id}/void/", {"reason": 42}, format="json"
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["note"], "Voided: 42")

    def test_large_amounts_fit(self):
        payload = {
            "student": self.student.id,
            "category": "other",
            "description": "Big",
            "amount": "9999999999.99",
            "due_date": "2099-01-01",
        }
        self.assertEqual(self.client_for(self.admin).post("/api/finance/charges/", payload).status_code, 201)
