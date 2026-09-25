import secrets
import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.utils import timezone

# Money is stored with 12 digits (up to ₦9,999,999,999.99) everywhere so amounts can move
# between charges, proofs, gateway transactions and payments without overflowing.
MONEY = {"max_digits": 12, "decimal_places": 2}
NON_NEGATIVE = MinValueValidator(0)
POSITIVE = MinValueValidator(Decimal("0.01"))

# Lets lists of student-owned records (API and admin) be searched by the student.
STUDENT_SEARCH_FIELDS = ["student__first_name", "student__last_name", "student__university_id"]


class Category(models.TextChoices):
    TUITION = "tuition", "Tuition"
    MANDATORY = "mandatory", "Mandatory fee"
    HOUSING = "housing", "Housing"
    LAB = "lab", "Lab / materials"
    FINE = "fine", "Fine"
    OTHER = "other", "Other"


class FeeType(models.Model):
    """A fee every enrolled student is billed once per semester (activity, technology, ...)."""

    name = models.CharField(max_length=80, unique=True)
    amount = models.DecimalField(**MONEY, validators=[NON_NEGATIVE])
    description = models.CharField(max_length=200, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} (₦{self.amount:,})"


class Charge(models.Model):
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="charges")
    semester = models.ForeignKey(
        "academics.Semester", on_delete=models.PROTECT, null=True, blank=True, related_name="charges"
    )
    category = models.CharField(max_length=16, choices=Category.choices, default=Category.OTHER)
    description = models.CharField(max_length=200)
    amount = models.DecimalField(**MONEY, validators=[NON_NEGATIVE])
    due_date = models.DateField()
    # Charges generated from enrollment carry a key ("tuition", "fee:<id>") so they can be
    # recalculated in place. Manual charges leave it blank.
    auto_key = models.CharField(max_length=32, blank=True, editable=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["due_date", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["student", "semester", "auto_key"],
                condition=~models.Q(auto_key=""),
                name="unique_auto_charge_per_semester",
            ),
        ]

    def __str__(self):
        return f"{self.student} · {self.description} · ₦{self.amount:,}"

    @property
    def is_automatic(self):
        return bool(self.auto_key)


def new_receipt_number(when):
    return f"RCP-{when:%Y%m%d}-{secrets.token_hex(3).upper()}"


class Payment(models.Model):
    class Method(models.TextChoices):
        CARD = "card", "Card"
        BANK_TRANSFER = "bank_transfer", "Bank transfer"
        BANK_DEPOSIT = "bank_deposit", "Bank deposit"
        POS = "pos", "POS"
        CASH = "cash", "Cash"
        SCHOLARSHIP = "scholarship", "Scholarship / aid"
        PAYSTACK = "paystack", "Paystack"

    class Status(models.TextChoices):
        COMPLETED = "completed", "Completed"
        VOID = "void", "Void"

    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="payments")
    amount = models.DecimalField(**MONEY, validators=[POSITIVE])
    method = models.CharField(max_length=16, choices=Method.choices, default=Method.CARD)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.COMPLETED)
    receipt_number = models.CharField(max_length=32, unique=True, editable=False)
    # Card payments keep only the last four digits; full card data never reaches the server.
    card_last4 = models.CharField(max_length=4, blank=True)
    reference = models.CharField(max_length=80, blank=True)
    note = models.CharField(max_length=200, blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    paid_at = models.DateTimeField(default=timezone.now)
    voided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-paid_at"]

    def __str__(self):
        return f"{self.receipt_number} · {self.student} · ₦{self.amount:,}"

    def save(self, *args, **kwargs):
        if not self.receipt_number:
            self.receipt_number = new_receipt_number(timezone.localtime(self.paid_at))
        super().save(*args, **kwargs)


class GatewayTransaction(models.Model):
    """An online checkout started with Paystack. Becomes a Payment once verified."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SUCCESS = "success", "Successful"
        FAILED = "failed", "Failed"

    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="gateway_transactions")
    reference = models.CharField(max_length=64, unique=True)
    amount = models.DecimalField(**MONEY)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    gateway_response = models.CharField(max_length=200, blank=True)
    payment = models.OneToOneField(
        Payment, on_delete=models.SET_NULL, null=True, blank=True, related_name="gateway_transaction"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.reference} · {self.student} · ₦{self.amount:,} · {self.status}"


def proof_upload_path(instance, filename):
    # Random names: the original filename is kept in the database, not on disk.
    ext = filename.rsplit(".", 1)[-1].lower()
    return f"payment_proofs/{timezone.now():%Y/%m}/{uuid.uuid4().hex}.{ext}"


class PaymentProof(models.Model):
    """Evidence of an offline payment (bank teller, transfer alert, POS slip) awaiting bursary review."""

    class Method(models.TextChoices):
        BANK_DEPOSIT = "bank_deposit", "Bank deposit (teller)"
        BANK_TRANSFER = "bank_transfer", "Bank transfer"
        POS = "pos", "POS"
        CASH = "cash", "Cash at the Bursary"

    class Status(models.TextChoices):
        PENDING = "pending", "Awaiting review"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="payment_proofs")
    amount = models.DecimalField(**MONEY, validators=[POSITIVE])
    method = models.CharField(max_length=16, choices=Method.choices, default=Method.BANK_DEPOSIT)
    payment_date = models.DateField()
    bank_name = models.CharField(max_length=80, blank=True)
    reference = models.CharField(max_length=80, help_text="Teller number or transaction reference")
    note = models.CharField(max_length=300, blank=True)
    file = models.FileField(upload_to=proof_upload_path)
    original_filename = models.CharField(max_length=200)
    content_type = models.CharField(max_length=40)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    review_note = models.CharField(max_length=300, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    payment = models.OneToOneField(Payment, on_delete=models.SET_NULL, null=True, blank=True, related_name="proof")
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-submitted_at"]

    def __str__(self):
        return f"{self.student} · ₦{self.amount:,} · {self.reference} · {self.status}"


@receiver(post_delete, sender=PaymentProof)
def delete_proof_file(sender, instance, **kwargs):
    # Covers every way a proof disappears: withdrawn, deleted in the admin, or its student removed.
    if instance.file:
        instance.file.storage.delete(instance.file.name)
