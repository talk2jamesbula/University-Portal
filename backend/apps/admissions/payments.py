"""Application fee payments. Like every online payment at the University, they go through Paystack.

References start with "APP-", which is how the shared Paystack webhook tells them apart from
student fee payments.
"""

import secrets
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.core.models import Notification
from apps.core.services import notify
from apps.finance import paystack

from . import services
from .models import Application, ApplicationPayment

PREFIX = "APP-"


def new_reference():
    return f"{PREFIX}{timezone.now():%Y%m%d}-{secrets.token_hex(5).upper()}"


def _check_payable(application):
    if application.status != Application.Status.DRAFT:
        raise ValidationError("The application fee is paid before you submit.")
    if not application.cycle.is_open:
        raise ValidationError("Applications are closed, so the fee can no longer be paid.")
    if application.fee_paid:
        raise ValidationError("You have already paid the application fee.")


def start(application, callback_url):
    """Begin a Paystack checkout. Returns (payment, Paystack's checkout URL)."""
    _check_payable(application)
    if not paystack.is_configured():
        raise ValidationError("Online payment is not available right now. Please try again later.")
    applicant = application.applicant
    payment = ApplicationPayment.objects.create(
        application=application, reference=new_reference(), amount=application.cycle.application_fee
    )
    try:
        data = paystack._request(
            "POST",
            "/transaction/initialize",
            json={
                "email": applicant.email,
                "amount": paystack.to_kobo(payment.amount),
                "currency": "NGN",
                "reference": payment.reference,
                "callback_url": callback_url,
                "metadata": {
                    "purpose": "application_fee",
                    "application": application.number,
                    "custom_fields": [
                        {"display_name": "Applicant", "variable_name": "applicant", "value": applicant.get_full_name()},
                        {"display_name": "Application", "variable_name": "application", "value": application.number},
                    ],
                },
            },
        )
    except paystack.PaystackError as exc:
        payment.status, payment.gateway_response = ApplicationPayment.Status.FAILED, str(exc)[:200]
        payment.save(update_fields=["status", "gateway_response"])
        raise ValidationError(str(exc)) from exc
    return payment, data["authorization_url"]


def record_success(reference, data):
    """A verified charge. Safe to call more than once (verify and webhook both call it)."""
    return _record_success(reference, data)


@transaction.atomic
def _record_success(reference, data):
    payment = (
        ApplicationPayment.objects.select_for_update().select_related("application__applicant").get(reference=reference)
    )
    if payment.status == ApplicationPayment.Status.SUCCESS:
        return payment
    application = payment.application
    paid = Decimal(data["amount"]) / 100
    if data.get("currency") != "NGN" or paid != payment.amount:
        payment.status = ApplicationPayment.Status.FAILED
        payment.gateway_response = f"Amount/currency mismatch: {data.get('currency')} {paid}"
        payment.save(update_fields=["status", "gateway_response"])
        return payment
    if application.payments.filter(status=ApplicationPayment.Status.SUCCESS).exists():
        # Paid twice (e.g. two browser tabs). Keep one; flag this one for a refund.
        payment.status = ApplicationPayment.Status.FAILED
        payment.gateway_response = "Duplicate payment: the fee was already paid. Contact Admissions for a refund."
        payment.save(update_fields=["status", "gateway_response"])
        services.record(application, "duplicate_payment", application.applicant, payment.reference)
        return payment
    payment.status = ApplicationPayment.Status.SUCCESS
    payment.channel = (data.get("channel") or "")[:30]
    payment.gateway_response = (data.get("gateway_response") or "Successful")[:200]
    payment.paid_at = timezone.now()
    payment.save()
    services.record(
        application,
        "fee_paid",
        application.applicant,
        f"Application fee ₦{payment.amount:,.2f} ({payment.reference})",
        public=True,
    )
    notify(
        [application.applicant],
        "Application fee received",
        f"We received your application fee of ₦{payment.amount:,.2f} (reference {payment.reference}). "
        "You can download the receipt in the portal. Remember to submit your application.",
        link="/portal/application",
        category=Notification.Category.ADMISSION,
        email=True,
    )
    return payment


def verify(payment):
    """Ask Paystack for the final state of a checkout and record it."""
    if payment.status == ApplicationPayment.Status.SUCCESS or payment.gateway != "paystack":
        return payment
    try:
        data = paystack._request("GET", f"/transaction/verify/{payment.reference}")
    except paystack.PaystackError as exc:
        raise ValidationError(str(exc)) from exc
    if data.get("status") == "success":
        return record_success(payment.reference, data)
    if data.get("status") in ("failed", "abandoned", "reversed"):
        payment.status = ApplicationPayment.Status.FAILED
    payment.gateway_response = (data.get("gateway_response") or data.get("status") or "")[:200]
    payment.save(update_fields=["status", "gateway_response"])
    return payment
