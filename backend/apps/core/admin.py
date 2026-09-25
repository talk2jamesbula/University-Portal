from django.contrib import admin

from .models import AuditLog, Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ["user", "title", "category", "created_at", "read_at"]
    list_filter = ["category"]
    search_fields = ["title", "user__username", "user__last_name"]
    raw_id_fields = ["user"]


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """Read-only: the audit trail must not be edited."""

    list_display = ["created_at", "actor", "action", "summary", "ip_address"]
    list_filter = ["action"]
    search_fields = ["summary", "actor__username", "target_id"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
