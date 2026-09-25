from django.contrib import admin

from .models import ContactMessage


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ["created_at", "name", "email", "topic", "subject", "handled"]
    list_filter = ["topic", "handled"]
    list_editable = ["handled"]
    search_fields = ["name", "email", "subject", "message"]
    readonly_fields = ["name", "email", "phone", "topic", "subject", "message", "ip_address", "created_at"]
