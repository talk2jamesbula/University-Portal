from django.contrib import admin

from .models import STUDENT_SEARCH_FIELDS, Charge, FeeType, GatewayTransaction, Payment, PaymentProof


@admin.register(FeeType)
class FeeTypeAdmin(admin.ModelAdmin):
    list_display = ["name", "amount", "is_active"]
    list_editable = ["is_active"]


@admin.register(Charge)
class ChargeAdmin(admin.ModelAdmin):
    list_display = ["student", "description", "category", "semester", "amount", "due_date", "auto_key"]
    list_filter = ["category", "semester"]
    search_fields = [*STUDENT_SEARCH_FIELDS, "description"]
    raw_id_fields = ["student"]


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ["receipt_number", "student", "amount", "method", "status", "paid_at"]
    list_filter = ["method", "status"]
    search_fields = ["receipt_number", "reference", *STUDENT_SEARCH_FIELDS]
    raw_id_fields = ["student"]
    readonly_fields = ["receipt_number"]


@admin.register(GatewayTransaction)
class GatewayTransactionAdmin(admin.ModelAdmin):
    list_display = ["reference", "student", "amount", "status", "gateway_response", "created_at", "verified_at"]
    list_filter = ["status"]
    search_fields = ["reference", *STUDENT_SEARCH_FIELDS]
    readonly_fields = [
        "reference",
        "student",
        "amount",
        "status",
        "gateway_response",
        "payment",
        "created_at",
        "verified_at",
    ]

    def has_add_permission(self, request):
        return False


@admin.register(PaymentProof)
class PaymentProofAdmin(admin.ModelAdmin):
    """Read-only here; approve or reject proofs in the portal so payments and emails are created."""

    list_display = ["student", "amount", "method", "reference", "payment_date", "status", "submitted_at"]
    list_filter = ["status", "method"]
    search_fields = ["reference", *STUDENT_SEARCH_FIELDS]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
