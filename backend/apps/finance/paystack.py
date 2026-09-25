"""Paystack integration: start a hosted checkout, verify it, and handle webhooks.

Docs: https://paystack.com/docs/payments/accept-payments/
"""

import hashlib
import hmac
import secrets
from decimal import Decimal

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import GatewayTransaction, Payment
from .services import record_payment


class PaystackError(Exception):
    pass


def is_configured():
    return bool(settings.PAYSTACK_SECRET_KEY)


def _request(method, path, **kwargs):
    try:
        response = requests.request(
            method,
            f"{settings.PAYSTACK_BASE_URL}{path}",
            headers={"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"},
            timeout=20,
            **kwargs,
        )
        body = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise PaystackError("Could not reach Paystack. Please try again.") from exc
    if not response.ok or not body.get("status"):
        raise PaystackError(body.get("message") or "Paystack rejected the request.")
    return body["data"]


def to_kobo(amount):
    return int((Decimal(amount) * 100).quantize(Decimal("1")))


def initialize(student, amount, callback_url):
    """Create a pending transaction and return Paystack's hosted checkout URL."""
    reference = f"BU-{timezone.now():%Y%m%d}-{secrets.token_hex(6).upper()}"
    txn = GatewayTransaction.objects.create(student=student, reference=reference, amount=amount)
    data = _request(
        "POST",
        "/transaction/initialize",
        json={
            "email": student.email,
            "amount": to_kobo(amount),
            "currency": "NGN",
            "reference": reference,
            "callback_url": callback_url,
            "metadata": {
                "student_id": student.id,
                "university_id": student.university_id,
                "custom_fields": [
                    {"display_name": "Student", "variable_name": "student", "value": student.get_full_name()},
                    {
                        "display_name": "Student ID",
                        "variable_name": "university_id",
                        "value": student.university_id or "",
                    },
                ],
            },
        },
    )
    return txn, data["authorization_url"]


def record_success(reference, data):
    """Turn a verified Paystack charge into a Payment. Safe to call more than once."""
    txn = _record_success(reference, data)
    # Raised only after the atomic block commits, so the "failed" status is kept.
    if txn.status == GatewayTransaction.Status.FAILED:
        raise PaystackError("The amount paid does not match this transaction. Please contact the bursary.")
    return txn


@transaction.atomic
def _record_success(reference, data):
    txn = GatewayTransaction.objects.select_for_update().select_related("payment").get(reference=reference)
    if txn.payment:
        return txn

    paid = Decimal(data["amount"]) / 100
    if data.get("currency") != "NGN" or paid != txn.amount:
        txn.status = GatewayTransaction.Status.FAILED
        txn.gateway_response = f"Amount/currency mismatch: {data.get('currency')} {paid}"
        txn.save(update_fields=["status", "gateway_response"])
        return txn

    auth = data.get("authorization") or {}
    channel = data.get("channel") or ""
    txn.payment = record_payment(
        student=txn.student,
        amount=paid,
        method=Payment.Method.PAYSTACK,
        card_last4=(auth.get("last4") or "")[:4] if channel == "card" else "",
        reference=reference,
        note=f"Paid via {channel.replace('_', ' ')}" if channel else "",
        recorded_by=txn.student,
        paid_at=timezone.now(),
    )
    txn.status = GatewayTransaction.Status.SUCCESS
    txn.gateway_response = (data.get("gateway_response") or "")[:200]
    txn.verified_at = timezone.now()
    txn.save(update_fields=["payment", "status", "gateway_response", "verified_at"])
    return txn


def verify(reference):
    """Ask Paystack for the transaction's final state and record it."""
    data = _request("GET", f"/transaction/verify/{reference}")
    if data.get("status") == "success":
        return record_success(reference, data)
    txn = GatewayTransaction.objects.get(reference=reference)
    if data.get("status") in ("failed", "abandoned", "reversed"):
        txn.status = GatewayTransaction.Status.FAILED
    txn.gateway_response = (data.get("gateway_response") or data.get("status") or "")[:200]
    txn.save(update_fields=["status", "gateway_response"])
    return txn


def valid_signature(raw_body, signature):
    expected = hmac.new(settings.PAYSTACK_SECRET_KEY.encode(), raw_body, hashlib.sha512).hexdigest()
    return bool(signature) and hmac.compare_digest(expected, signature)
