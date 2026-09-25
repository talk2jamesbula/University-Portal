import re
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import serializers

from .models import Charge, FeeType, Payment, PaymentProof
from .services import account_summary

User = get_user_model()
MONEY = {"max_digits": 12, "decimal_places": 2}
POSITIVE_MONEY = {**MONEY, "min_value": Decimal("0.01")}


class FeeTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeeType
        fields = ["id", "name", "amount", "description", "is_active"]


class ChargeSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.get_full_name", read_only=True)
    semester_name = serializers.CharField(source="semester.name", read_only=True, default=None)
    category_label = serializers.CharField(source="get_category_display", read_only=True)
    is_automatic = serializers.BooleanField(read_only=True)
    # Filled in by account_summary(); absent on plain list views.
    amount_paid = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True, default=None)
    amount_due = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True, default=None)
    status = serializers.CharField(read_only=True, default=None)

    class Meta:
        model = Charge
        fields = [
            "id",
            "student",
            "student_name",
            "semester",
            "semester_name",
            "category",
            "category_label",
            "description",
            "amount",
            "due_date",
            "is_automatic",
            "created_at",
            "amount_paid",
            "amount_due",
            "status",
        ]
        read_only_fields = ["created_at"]

    def validate_student(self, value):
        if not value.is_student:
            raise serializers.ValidationError("Charges can only be added to student accounts.")
        return value

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than zero.")
        return value


class StudentBalanceSerializer(serializers.ModelSerializer):
    """A row in the bursary's list of student accounts (annotated by views.accounts.with_balances)."""

    full_name = serializers.CharField(source="get_full_name")
    avatar_url = serializers.CharField()
    total_charged = serializers.DecimalField(**MONEY)
    total_paid = serializers.DecimalField(**MONEY)
    balance = serializers.DecimalField(**MONEY)

    class Meta:
        model = User
        fields = ["id", "full_name", "university_id", "email", "avatar_url", "total_charged", "total_paid", "balance"]
        read_only_fields = fields


class PaymentSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.get_full_name", read_only=True)
    student_university_id = serializers.CharField(source="student.university_id", read_only=True)
    method_label = serializers.CharField(source="get_method_display", read_only=True)
    recorded_by_name = serializers.CharField(source="recorded_by.get_full_name", read_only=True, default=None)

    class Meta:
        model = Payment
        fields = [
            "id",
            "student",
            "student_name",
            "student_university_id",
            "amount",
            "method",
            "method_label",
            "status",
            "receipt_number",
            "card_last4",
            "reference",
            "note",
            "recorded_by_name",
            "paid_at",
            "voided_at",
        ]
        read_only_fields = fields


def validate_payable_amount(student, value):
    balance = account_summary(student)["balance"]
    if balance <= 0:
        raise serializers.ValidationError("Your account has no balance to pay.")
    if value > balance:
        raise serializers.ValidationError(f"Amount cannot exceed your balance of ₦{balance:,.2f}.")
    return value


class OnlinePaymentSerializer(serializers.Serializer):
    """Amount a student wants to pay through Paystack."""

    amount = serializers.DecimalField(**POSITIVE_MONEY)

    def validate_amount(self, value):
        return validate_payable_amount(self.context["request"].user, value)


class RecordPaymentSerializer(serializers.ModelSerializer):
    """A payment recorded by the bursar's office (cash, transfer, aid, or card)."""

    class Meta:
        model = Payment
        fields = ["student", "amount", "method", "reference", "note", "paid_at", "card_last4"]
        extra_kwargs = {"paid_at": {"required": False}}

    def validate_student(self, value):
        if not value.is_student:
            raise serializers.ValidationError("Payments can only be recorded for students.")
        return value

    def validate_method(self, value):
        # Paystack payments are created only from verified Paystack transactions, never typed in.
        if value == Payment.Method.PAYSTACK:
            raise serializers.ValidationError(
                "Paystack payments are recorded automatically when Paystack confirms them."
            )
        return value


class VoidPaymentSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=180, required=False, allow_blank=True, default="")


MAX_PROOF_SIZE = 5 * 1024 * 1024
# Identify uploads by their first bytes rather than trusting the filename or browser.
PROOF_SIGNATURES = {
    b"%PDF-": ("application/pdf", "pdf"),
    b"\xff\xd8\xff": ("image/jpeg", "jpg"),
    b"\x89PNG\r\n\x1a\n": ("image/png", "png"),
}


def normalise_reference(value):
    return re.sub(r"\s+", "", value or "").upper()


class PaymentProofSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.get_full_name", read_only=True)
    student_university_id = serializers.CharField(source="student.university_id", read_only=True)
    method_label = serializers.CharField(source="get_method_display", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    reviewed_by_name = serializers.CharField(source="reviewed_by.get_full_name", read_only=True, default=None)
    receipt_number = serializers.CharField(source="payment.receipt_number", read_only=True, default=None)

    class Meta:
        model = PaymentProof
        fields = [
            "id",
            "student",
            "student_name",
            "student_university_id",
            "amount",
            "method",
            "method_label",
            "payment_date",
            "bank_name",
            "reference",
            "note",
            "original_filename",
            "content_type",
            "status",
            "status_label",
            "review_note",
            "reviewed_by_name",
            "reviewed_at",
            "payment",
            "receipt_number",
            "submitted_at",
        ]
        read_only_fields = fields


class PaymentProofCreateSerializer(serializers.ModelSerializer):
    file = serializers.FileField()

    class Meta:
        model = PaymentProof
        fields = ["amount", "method", "payment_date", "bank_name", "reference", "note", "file"]

    def validate_payment_date(self, value):
        today = timezone.localdate()
        if value > today:
            raise serializers.ValidationError("Payment date can't be in the future.")
        if (today - value).days > 365:
            raise serializers.ValidationError("Payments older than a year must be resolved at the Bursary.")
        return value

    def validate_reference(self, value):
        ref = normalise_reference(value)
        if len(ref) < 4:
            raise serializers.ValidationError("Enter the teller number or transaction reference.")
        already_used = (
            PaymentProof.objects.filter(reference=ref).exclude(status=PaymentProof.Status.REJECTED).exists()
            or Payment.objects.filter(reference__iexact=ref, status=Payment.Status.COMPLETED).exists()
        )
        if already_used:
            raise serializers.ValidationError(
                "This reference has already been submitted. Each teller or transaction can only be used once."
            )
        return ref

    def validate_file(self, upload):
        if upload.size > MAX_PROOF_SIZE:
            raise serializers.ValidationError("File is too large. The maximum size is 5 MB.")
        head = upload.read(8)
        upload.seek(0)
        for signature, detected in PROOF_SIGNATURES.items():
            if head.startswith(signature):
                self._detected = detected
                return upload
        raise serializers.ValidationError("Upload a PDF, JPG or PNG file.")

    def validate(self, attrs):
        method = attrs.get("method", PaymentProof._meta.get_field("method").default)
        needs_bank = method in (PaymentProof.Method.BANK_DEPOSIT, PaymentProof.Method.BANK_TRANSFER)
        if needs_bank and not attrs.get("bank_name", "").strip():
            raise serializers.ValidationError({"bank_name": "Enter the bank you paid into or from."})
        return attrs

    def create(self, validated_data):
        upload = validated_data["file"]
        content_type, ext = self._detected
        # Keep the student's filename for display, but with the extension matching the real content.
        base = upload.name.rsplit(".", 1)[0]
        upload.name = f"{base}.{ext}"
        return PaymentProof.objects.create(
            **validated_data,
            original_filename=upload.name[:200],
            content_type=content_type,
        )


class ApproveProofSerializer(serializers.Serializer):
    """The bursary may credit a corrected amount (e.g. when the bank shows a different figure)."""

    amount = serializers.DecimalField(**POSITIVE_MONEY, required=False, allow_null=True)
    note = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")


class RejectProofSerializer(serializers.Serializer):
    reason = serializers.CharField(
        min_length=5,
        max_length=300,
        error_messages={
            "min_length": "Tell the student why the proof was rejected.",
            "blank": "Tell the student why the proof was rejected.",
        },
    )
