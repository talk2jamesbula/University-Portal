"""Emails about payments. All are sent after the database commit and never raise:
a mail or PDF failure must not undo, or appear to undo, a recorded payment."""

import logging

from django.conf import settings
from django.core.mail import EmailMessage
from django.db import transaction

from .models import Payment

logger = logging.getLogger(__name__)


def _send(subject, body, to, attachments=()):
    if not to:
        return
    try:
        message = EmailMessage(subject=subject, body=body, to=to)
        for attachment in attachments:
            message.attach(*attachment)
        message.send()
    except Exception:
        logger.exception("Could not send email: %s", subject)


def _signature():
    return f"{settings.UNIVERSITY_NAME}\n{settings.UNIVERSITY_ADDRESS}"


def _send_receipt(payment_id):
    # Imported here: documents imports services, which imports this module.
    from .documents import receipt_pdf

    try:
        payment = Payment.objects.select_related("student__department").get(pk=payment_id)
        pdf = receipt_pdf(payment)
    except Exception:
        logger.exception("Could not build receipt for payment %s", payment_id)
        return
    student = payment.student
    _send(
        subject=f"Payment receipt {payment.receipt_number} — {settings.UNIVERSITY_NAME}",
        body=(
            f"Dear {student.first_name or student.get_full_name() or student.username},\n\n"
            f"We have received your payment of ₦{payment.amount:,.2f}. "
            f"Your receipt ({payment.receipt_number}) is attached.\n\n"
            "You can view your statement and download receipts and invoices at any time from "
            f"Fees & Payments in the student portal.\n\n{_signature()}"
        ),
        to=[student.email] if student.email else [],
        attachments=[(f"{payment.receipt_number}.pdf", pdf, "application/pdf")],
    )


def email_receipt(payment):
    """Email the student their PDF receipt once the payment is committed."""
    transaction.on_commit(lambda: _send_receipt(payment.pk))


def proof_submitted(proof):
    if not settings.BURSARY_NOTIFY_EMAIL:
        return
    student = proof.student
    transaction.on_commit(
        lambda: _send(
            subject=f"New proof of payment: {student.get_full_name()} — ₦{proof.amount:,.2f}",
            body=(
                f"{student.get_full_name()} ({student.university_id}) uploaded proof of a "
                f"{proof.get_method_display().lower()} of ₦{proof.amount:,.2f} made on {proof.payment_date:%d %B %Y}, "
                f"reference {proof.reference}.\n\nReview it under Fees & Payments → Payment proofs in the portal."
            ),
            to=[settings.BURSARY_NOTIFY_EMAIL],
        )
    )


def proof_rejected(proof):
    student = proof.student
    transaction.on_commit(
        lambda: _send(
            subject=f"Proof of payment not accepted — {settings.UNIVERSITY_NAME}",
            body=(
                f"Dear {student.first_name or student.get_full_name()},\n\n"
                f"The proof of payment you uploaded (₦{proof.amount:,.2f}, reference {proof.reference}, "
                f"paid {proof.payment_date:%d %B %Y}) could not be verified.\n\n"
                f"Reason: {proof.review_note}\n\n"
                "You can upload a corrected proof from Fees & Payments in the student portal, or visit the Bursary."
                f"\n\n{_signature()}"
            ),
            to=[student.email] if student.email else [],
        )
    )
