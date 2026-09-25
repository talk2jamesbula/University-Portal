"""Billing and payment rules: fee assessment, balances, recording payments, reviewing proofs."""

from datetime import datetime, time, timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.academics.models import Enrollment
from apps.core.models import Notification
from apps.core.services import notify

from .models import Category, Charge, FeeType, Payment, PaymentProof
from .notifications import email_receipt, proof_rejected

ZERO = Decimal("0.00")


# --- Fees ------------------------------------------------------------------------------------


def semester_due_date(semester):
    return semester.fee_due_date or (semester.start_date + timedelta(days=30))


@transaction.atomic
def assess_semester_fees(student, semester):
    """Bring a student's automatic charges for a semester in line with their current enrollment.

    Tuition = registered units x the semester's rate. Mandatory fees apply to anyone registered
    for at least one course. Dropping every course removes the automatic charges; any
    money already paid then shows as a credit on the account.
    """
    units = (
        Enrollment.objects.filter(student=student, offering__semester=semester)
        .exclude(status=Enrollment.Status.DROPPED)
        .aggregate(total=Sum("offering__course__units"))["total"]
        or 0
    )
    wanted = {}
    if units:
        wanted["tuition"] = (
            Category.TUITION,
            f"Tuition — {units} units × ₦{semester.tuition_per_unit:,}",
            semester.tuition_per_unit * units,
        )
        for fee in FeeType.objects.filter(is_active=True):
            wanted[f"fee:{fee.id}"] = (Category.MANDATORY, fee.name, fee.amount)

    existing = {c.auto_key: c for c in Charge.objects.filter(student=student, semester=semester).exclude(auto_key="")}
    for key, charge in existing.items():
        if key not in wanted:
            charge.delete()
    for key, (category, description, amount) in wanted.items():
        charge = existing.get(key)
        if charge is None:
            Charge.objects.create(
                student=student,
                semester=semester,
                auto_key=key,
                category=category,
                description=description,
                amount=amount,
                due_date=semester_due_date(semester),
            )
        elif (charge.amount, charge.description) != (amount, description):
            charge.amount, charge.description = amount, description
            charge.save(update_fields=["amount", "description"])


# --- Balances --------------------------------------------------------------------------------


def _allocate(charges, payments):
    """Apply payments (oldest first) to charges (earliest due first).

    Returns ({payment_id: [(charge, amount), ...]}, {charge_id: amount_paid}).
    """
    remaining = {c.id: c.amount for c in charges}
    by_payment, by_charge = {}, {c.id: ZERO for c in charges}
    for payment in payments:
        left, parts = payment.amount, []
        for charge in charges:
            if left <= 0:
                break
            take = min(left, remaining[charge.id])
            if take > 0:
                remaining[charge.id] -= take
                by_charge[charge.id] += take
                left -= take
                parts.append((charge, take))
        by_payment[payment.id] = parts
    return by_payment, by_charge


def _charges(student):
    return list(Charge.objects.filter(student=student).select_related("semester").order_by("due_date", "id"))


def _completed_payments(student):
    return list(Payment.objects.filter(student=student, status=Payment.Status.COMPLETED).order_by("paid_at", "id"))


def allocate_payments(student):
    """Which charges each completed payment paid for. See _allocate."""
    return _allocate(_charges(student), _completed_payments(student))


def account_summary(student):
    """Totals, plus each charge annotated with amount_paid / amount_due / status."""
    today = timezone.localdate()
    charges = _charges(student)
    _, paid_by_charge = _allocate(charges, _completed_payments(student))
    payments = list(Payment.objects.filter(student=student).order_by("-paid_at"))

    overdue, next_due = ZERO, None
    for charge in charges:
        charge.amount_paid = paid_by_charge[charge.id]
        charge.amount_due = charge.amount - charge.amount_paid
        if charge.amount_due == 0:
            charge.status = "paid"
        elif charge.due_date < today:
            charge.status = "overdue"
            overdue += charge.amount_due
        else:
            charge.status = "partial" if charge.amount_paid else "unpaid"
            next_due = next_due or charge.due_date

    charged_total = sum((c.amount for c in charges), ZERO)
    paid_total = sum((p.amount for p in payments if p.status == Payment.Status.COMPLETED), ZERO)
    return {
        "total_charged": charged_total,
        "total_paid": paid_total,
        "balance": charged_total - paid_total,
        "overdue": overdue,
        "next_due_date": next_due,
        "charges": charges,
        "payments": payments,
    }


# --- Payments --------------------------------------------------------------------------------


def record_payment(**fields):
    """Create a completed payment and email the student their receipt once it's committed.

    Every way of paying (Paystack, approved proofs, bursary entries)
    goes through here so receipts are always sent.
    """
    payment = Payment.objects.create(**fields)
    email_receipt(payment)
    notify(
        [payment.student],
        f"Your payment of ₦{payment.amount:,.2f} has been confirmed",
        f"Receipt {payment.receipt_number}.",
        link="/portal/fees",
        category=Notification.Category.FINANCE,
    )
    return payment


def void_payment(payment, reason=""):
    if payment.status == Payment.Status.VOID:
        raise ValidationError("This payment is already void.")
    payment.status = Payment.Status.VOID
    payment.voided_at = timezone.now()
    if reason:
        payment.note = f"Voided: {reason}"[:200]
    payment.save(update_fields=["status", "voided_at", "note"])
    return payment


# --- Proofs of offline payment ---------------------------------------------------------------


def _lock_pending_proof(proof_id):
    proof = PaymentProof.objects.select_for_update().get(pk=proof_id)
    if proof.status != PaymentProof.Status.PENDING:
        raise ValidationError(f"This proof has already been {proof.get_status_display().lower()}.")
    return proof


def _mark_reviewed(proof, status, reviewer, note):
    proof.status = status
    proof.review_note = note[:300]
    proof.reviewed_by = reviewer
    proof.reviewed_at = timezone.now()
    proof.save()


@transaction.atomic
def approve_proof(proof_id, reviewer, amount=None, note=""):
    """Record the offline payment a proof describes. The bursary may correct the amount."""
    proof = _lock_pending_proof(proof_id)
    amount = amount or proof.amount
    proof.payment = record_payment(
        student=proof.student,
        amount=amount,
        method=Payment.Method(proof.method),
        reference=proof.reference,
        note=(note or f"Offline payment verified from uploaded proof #{proof.pk}")[:200],
        recorded_by=reviewer,
        # Midday on the payment date, but never later than now (for payments made today).
        paid_at=min(timezone.make_aware(datetime.combine(proof.payment_date, time(12))), timezone.now()),
    )
    if amount != proof.amount:
        note = f"Amount corrected from ₦{proof.amount:,.2f} to ₦{amount:,.2f}. {note}"
    _mark_reviewed(proof, PaymentProof.Status.APPROVED, reviewer, note)
    return proof


@transaction.atomic
def reject_proof(proof_id, reviewer, reason):
    proof = _lock_pending_proof(proof_id)
    _mark_reviewed(proof, PaymentProof.Status.REJECTED, reviewer, reason)
    proof_rejected(proof)
    notify(
        [proof.student],
        "Your proof of payment was not accepted",
        reason,
        link="/portal/fees",
        category=Notification.Category.FINANCE,
    )
    return proof
