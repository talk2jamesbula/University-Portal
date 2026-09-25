from django.contrib import admin

from .models import AdmissionCycle, Application, ApplicationDocument, ApplicationEvent, ApplicationPayment


@admin.register(AdmissionCycle)
class AdmissionCycleAdmin(admin.ModelAdmin):
    list_display = ["session", "application_fee", "opens_on", "closes_on", "min_utme_score", "is_active"]


class DocumentInline(admin.TabularInline):
    model = ApplicationDocument
    extra = 0
    fields = ["kind", "original_filename", "status", "review_note", "reviewed_by", "uploaded_at"]
    readonly_fields = ["uploaded_at"]


class PaymentInline(admin.TabularInline):
    model = ApplicationPayment
    extra = 0
    readonly_fields = ["reference", "amount", "gateway", "status", "channel", "paid_at"]
    can_delete = False


class EventInline(admin.TabularInline):
    model = ApplicationEvent
    extra = 0
    readonly_fields = ["created_at", "action", "from_status", "to_status", "actor", "note", "public"]
    can_delete = False


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ["number", "applicant", "programme", "status", "utme_score", "screening_score", "submitted_at"]
    list_filter = ["cycle", "status", "entry_mode"]
    search_fields = ["number", "applicant__first_name", "applicant__last_name", "applicant__email", "jamb_reg_number"]
    raw_id_fields = ["applicant"]
    inlines = [DocumentInline, PaymentInline, EventInline]
