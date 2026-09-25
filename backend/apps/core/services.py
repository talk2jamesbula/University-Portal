"""notify() and audit(): the two things every module needs.

notify(students, "Course registration is now open", link="/portal/registration",
       category=Notification.Category.REGISTRATION, email=True, sms=True)

audit(request, "payment.void", payment, f"Voided {payment.receipt_number}")
"""

import logging

from django.conf import settings
from django.core.mail import send_mass_mail
from django.db import transaction

from .models import AuditLog, Notification
from .sms import send_sms

logger = logging.getLogger(__name__)


def notify(users, title, body="", *, link="", category=Notification.Category.GENERAL, email=False, sms=False):
    """Create in-app notifications and optionally email / SMS the same message.

    Email and SMS go out after the database commit and never raise.
    """
    users = [u for u in users if u.is_active]
    Notification.objects.bulk_create(
        Notification(user=u, title=title[:160], body=body, link=link, category=category) for u in users
    )
    if email:
        footer = f"\n\n{settings.UNIVERSITY_NAME}"
        if link and settings.PORTAL_URL:
            footer = f"\n\nOpen the portal: {settings.PORTAL_URL.rstrip('/')}{link}{footer}"
        messages = [(title, f"{body}{footer}", None, [u.email]) for u in users if u.email]
        transaction.on_commit(lambda: _send_emails(messages))
    if sms:
        text = f"{settings.UNIVERSITY_SHORT_NAME}: {title}"
        phones = [u.phone for u in users if u.phone]
        transaction.on_commit(lambda: [send_sms(p, text) for p in phones])


def _send_emails(messages):
    try:
        send_mass_mail(messages, fail_silently=False)
    except Exception:
        logger.exception("Could not send %s notification emails", len(messages))


def client_ip(request):
    if request is None:
        return None
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return (forwarded.split(",")[0].strip() or request.META.get("REMOTE_ADDR")) or None


def audit(request, action, target=None, summary="", *, actor=None):
    """Record an action in the audit log. `request` may be None (e.g. webhooks, commands)."""
    user = actor or (request.user if request is not None and request.user.is_authenticated else None)
    AuditLog.objects.create(
        actor=user,
        action=action,
        target_type=target._meta.label_lower if target is not None else "",
        target_id=str(target.pk) if target is not None else "",
        summary=(summary or action)[:255],
        ip_address=client_ip(request),
    )
