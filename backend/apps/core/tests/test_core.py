from django.core import mail
from django.test import TestCase, override_settings

from apps.core.models import AuditLog, Notification
from apps.core.services import audit, notify
from apps.core.sms import normalise_phone
from apps.core.testing import client_for, make_admin, make_staff, make_student
from apps.finance.services import record_payment


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", PORTAL_URL="https://portal.test")
class NotificationTests(TestCase):
    def test_notify_in_app_email_and_sms(self):
        a, b = make_student(email="a@x.ng", phone="08031234567"), make_student(email="")
        with self.assertLogs("apps.core.sms", "INFO") as logs, self.captureOnCommitCallbacks(execute=True):
            notify(
                [a, b],
                "Your result is now available",
                "Check the portal.",
                link="/portal/results",
                email=True,
                sms=True,
            )
        self.assertEqual(Notification.objects.count(), 2)
        self.assertEqual(len(mail.outbox), 1)  # b has no email
        self.assertIn("https://portal.test/portal/results", mail.outbox[0].body)
        self.assertIn("2348031234567", logs.output[0])

    def test_api_is_per_user(self):
        a, b = make_student(), make_student()
        notify([a], "For A")
        notify([b], "For B")
        client = client_for(a)
        rows = client.get("/api/notifications/").data["results"]
        self.assertEqual([r["title"] for r in rows], ["For A"])
        self.assertEqual(client.get("/api/notifications/unread_count/").data["count"], 1)
        self.assertTrue(client.post(f"/api/notifications/{rows[0]['id']}/read/").data["is_read"])
        other = Notification.objects.get(user=b)
        self.assertEqual(client.post(f"/api/notifications/{other.id}/read/").status_code, 404)
        notify([a], "Another")
        self.assertEqual(client.post("/api/notifications/read_all/").data["marked"], 1)
        self.assertEqual(client.get("/api/notifications/unread_count/").data["count"], 0)

    def test_payment_confirmation_notifies(self):
        student = make_student()
        record_payment(student=student, amount=5000)
        self.assertIn("has been confirmed", Notification.objects.get(user=student).title)


class AuditTests(TestCase):
    def test_audit_log_access(self):
        admin = make_admin()
        audit(None, "test.action", admin, "Something happened", actor=admin)
        self.assertEqual(AuditLog.objects.get().target_type, "accounts.user")
        self.assertEqual(client_for(make_staff(roles=["lecturer"])).get("/api/audit-logs/").status_code, 403)
        self.assertEqual(len(client_for(make_staff(roles=["vc"])).get("/api/audit-logs/").data["results"]), 1)


class SmsTests(TestCase):
    def test_phone_normalisation(self):
        self.assertEqual(normalise_phone("0803 123 4567"), "2348031234567")
        self.assertEqual(normalise_phone("+234 803 123 4567"), "2348031234567")
        self.assertEqual(normalise_phone("123"), "")
