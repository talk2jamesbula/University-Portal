from django.contrib import admin

from .models import Announcement, Event


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ["title", "audience", "priority", "offering", "department", "author", "pinned", "created_at"]
    list_filter = ["audience", "priority", "pinned"]
    search_fields = ["title", "body"]


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ["title", "category", "location", "starts_at"]
    list_filter = ["category"]
    search_fields = ["title", "location"]
