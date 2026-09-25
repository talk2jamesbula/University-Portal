from django.conf import settings
from django.db import models


class Notification(models.Model):
    """An in-app notification. The same message may also have gone out by email or SMS."""

    class Category(models.TextChoices):
        GENERAL = "general", "General"
        ACADEMIC = "academic", "Academic"
        REGISTRATION = "registration", "Course registration"
        RESULTS = "results", "Results"
        EXAMS = "exams", "Examinations"
        FINANCE = "finance", "Fees & payments"
        ADMISSION = "admission", "Admission"
        ACCOMMODATION = "accommodation", "Accommodation"
        LIBRARY = "library", "Library"
        SUPPORT = "support", "Support"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    category = models.CharField(max_length=16, choices=Category.choices, default=Category.GENERAL)
    title = models.CharField(max_length=160)
    body = models.TextField(blank=True)
    link = models.CharField(max_length=200, blank=True, help_text="Portal path to open, e.g. /results")
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "read_at"])]

    def __str__(self):
        return f"{self.user}: {self.title}"


class AuditLog(models.Model):
    """Who did what, to what, from where. Written by core.audit.record()."""

    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    action = models.CharField(max_length=60, help_text='Dotted verb, e.g. "payment.void"')
    target_type = models.CharField(max_length=60, blank=True)
    target_id = models.CharField(max_length=40, blank=True)
    summary = models.CharField(max_length=255)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["action"]), models.Index(fields=["target_type", "target_id"])]

    def __str__(self):
        return f"{self.created_at:%Y-%m-%d %H:%M} {self.actor}: {self.summary}"
