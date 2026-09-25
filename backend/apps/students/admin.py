from django.contrib import admin

from .models import StatusChange, StudentDocument


@admin.register(StatusChange)
class StatusChangeAdmin(admin.ModelAdmin):
    list_display = ["student", "from_status", "to_status", "effective_date", "changed_by", "created_at"]
    list_filter = ["to_status"]
    search_fields = ["student__first_name", "student__last_name", "student__university_id"]
    raw_id_fields = ["student", "changed_by"]


@admin.register(StudentDocument)
class StudentDocumentAdmin(admin.ModelAdmin):
    list_display = ["student", "kind", "title", "original_filename", "uploaded_by", "uploaded_at"]
    list_filter = ["kind"]
    raw_id_fields = ["student", "uploaded_by"]
