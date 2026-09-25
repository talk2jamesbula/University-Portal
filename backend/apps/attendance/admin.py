from django.contrib import admin

from .models import AttendanceCorrection, AttendanceRecord, AttendanceSession


class RecordInline(admin.TabularInline):
    model = AttendanceRecord
    extra = 0
    raw_id_fields = ["student", "marked_by"]
    readonly_fields = ["device_id", "ip_address", "marked_at"]


@admin.register(AttendanceSession)
class AttendanceSessionAdmin(admin.ModelAdmin):
    list_display = ["offering", "date", "start_time", "status", "opened_at", "closed_at"]
    list_filter = ["status", "offering__semester"]
    search_fields = ["offering__course__code", "topic"]
    inlines = [RecordInline]


@admin.register(AttendanceCorrection)
class AttendanceCorrectionAdmin(admin.ModelAdmin):
    list_display = ["record", "from_status", "to_status", "status", "requested_by", "decided_by", "created_at"]
    list_filter = ["status"]
