import hashlib
import hmac
import json
from datetime import date
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.finance.models import Charge, GatewayTransaction, Payment

User = get_user_model()
KEY = "sk_test_secret"


def paystack_response(data, ok=True, message="ok"):
    response = mock.Mock(ok=ok)
    response.json.return_value = {"status": ok, "message": message, "data": data}
    return response


def charge_data(reference, amount_kobo, status="success", currency="NGN"):
    return {
        "reference": reference,
        "status": status,
        "amount": amount_kobo,
        "currency": currency,
        "channel": "card",
        "gateway_response": "Approved",
        "authorization": {"last4": "4081"},
    }


@override_settings(PAYSTACK_SECRET_KEY=KEY, PAYSTACK_CALLBACK_URL="http://portal.test/portal/fees/paystack/callback")
class PaystackTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.student = User.objects.create_user("stu", password="x", role=User.Role.STUDENT, email="stu@uni.edu")
        cls.other = User.objects.create_user("stu2", password="x", role=User.Role.STUDENT, email="s2@uni.edu")
        Charge.objects.create(student=cls.student, description="Tuition", amount=50000, due_date=date(2099, 1, 1))

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.student)

    def balance(self):
        return self.client.get("/api/finance/account/").data["balance"]

    @mock.patch("apps.finance.paystack.requests.request")
    def start(self, amount, request_mock):
        request_mock.return_value = paystack_response({"authorization_url": "https://checkout.paystack.com/abc"})
        res = self.client.post("/api/finance/paystack/initialize/", {"amount": amount})
        if res.status_code == 200:
            method, url = request_mock.call_args.args
            body = request_mock.call_args.kwargs["json"]
            self.assertEqual((method, url), ("POST", "https://api.paystack.co/transaction/initialize"))
            self.assertEqual(request_mock.call_args.kwargs["headers"]["Authorization"], f"Bearer {KEY}")
            self.assertEqual(body["amount"], int(float(amount) * 100))
            self.assertEqual(body["callback_url"], "http://portal.test/portal/fees/paystack/callback")
        return res

    @mock.patch("apps.finance.paystack.requests.request")
    def verify(self, reference, data, request_mock):
        request_mock.return_value = paystack_response(data)
        return self.client.post("/api/finance/paystack/verify/", {"reference": reference})

    def test_config_reports_paystack(self):
        self.assertEqual(self.client.get("/api/finance/payment-config/").data["gateway"], "paystack")

    def test_successful_checkout_records_payment_once(self):
        res = self.start("20000.50")
        self.assertEqual(res.data["authorization_url"], "https://checkout.paystack.com/abc")
        ref = res.data["reference"]
        self.assertEqual(GatewayTransaction.objects.get(reference=ref).status, "pending")
        self.assertEqual(self.balance(), 50000)

        res = self.verify(ref, charge_data(ref, 2000050))
        self.assertEqual(res.data["status"], "success")
        self.assertEqual(res.data["payment"]["method"], "paystack")
        self.assertEqual(res.data["payment"]["card_last4"], "4081")
        self.assertEqual(self.balance(), 50000 - 20000.5)

        # Returning to the callback page again must not record a second payment.
        self.verify(ref, charge_data(ref, 2000050))
        self.assertEqual(Payment.objects.count(), 1)

    def test_amount_mismatch_is_rejected(self):
        ref = self.start("1000").data["reference"]
        res = self.verify(ref, charge_data(ref, 100))  # paid ₦1 instead of ₦1,000
        self.assertEqual(res.status_code, 400)
        self.assertEqual(Payment.objects.count(), 0)
        self.assertEqual(GatewayTransaction.objects.get(reference=ref).status, "failed")

    def test_failed_charge_records_nothing(self):
        ref = self.start("1000").data["reference"]
        res = self.verify(ref, charge_data(ref, 100000, status="failed"))
        self.assertEqual(res.data["status"], "failed")
        self.assertEqual(Payment.objects.count(), 0)

    def test_amount_limits_and_ownership(self):
        self.assertEqual(self.start("60000").status_code, 400)  # more than the balance
        ref = self.start("1000").data["reference"]
        other = APIClient()
        other.force_authenticate(self.other)
        self.assertEqual(other.post("/api/finance/paystack/verify/", {"reference": ref}).status_code, 404)

    def test_paystack_error_is_reported(self):
        with mock.patch("apps.finance.paystack.requests.request") as request_mock:
            request_mock.return_value = paystack_response(None, ok=False, message="Invalid key")
            res = self.client.post("/api/finance/paystack/initialize/", {"amount": "100"})
        self.assertEqual(res.status_code, 400)
        self.assertIn("Invalid key", str(res.data))

    def webhook(self, payload, secret=KEY):
        body = json.dumps(payload).encode()
        signature = hmac.new(secret.encode(), body, hashlib.sha512).hexdigest()
        return APIClient().post(
            "/api/finance/paystack/webhook/",
            body,
            content_type="application/json",
            HTTP_X_PAYSTACK_SIGNATURE=signature,
        )

    def test_webhook_records_payment_and_checks_signature(self):
        ref = self.start("5000").data["reference"]
        event = {"event": "charge.success", "data": charge_data(ref, 500000)}
        self.assertEqual(self.webhook(event, secret="wrong").status_code, 401)
        self.assertEqual(Payment.objects.count(), 0)

        self.assertEqual(self.webhook(event).status_code, 200)
        self.assertEqual(self.balance(), 45000)
        # Webhook retries and the browser redirect both arriving are harmless.
        self.webhook(event)
        res = self.verify(ref, charge_data(ref, 500000))
        self.assertEqual(res.data["status"], "success")
        self.assertEqual(Payment.objects.count(), 1)

    def test_webhook_ignores_unknown_references(self):
        event = {"event": "charge.success", "data": charge_data("NOT-OURS", 100)}
        self.assertEqual(self.webhook(event).status_code, 200)
        self.assertEqual(Payment.objects.count(), 0)

    def test_students_cannot_record_payments_themselves(self):
        res = self.client.post("/api/finance/payments/", {"amount": "10", "card_last4": "4242"})
        self.assertEqual(res.status_code, 403)


@override_settings(PAYSTACK_SECRET_KEY="", DEBUG=True)
class NoGatewayTests(TestCase):
    def test_no_online_payments_without_paystack_even_in_development(self):
        student = User.objects.create_user("stu", password="x", role=User.Role.STUDENT)
        Charge.objects.create(student=student, description="T", amount=100, due_date=date(2099, 1, 1))
        client = APIClient()
        client.force_authenticate(student)
        self.assertIsNone(client.get("/api/finance/payment-config/").data["gateway"])
        self.assertEqual(client.post("/api/finance/payments/", {"amount": "10", "card_last4": "4242"}).status_code, 403)
        self.assertEqual(client.post("/api/finance/paystack/initialize/", {"amount": "10"}).status_code, 400)
