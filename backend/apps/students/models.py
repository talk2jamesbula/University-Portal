"""Student records management: status history and documents kept by the Registry.

The student record itself is accounts.StudentProfile (with the login on accounts.User).
"""

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.accounts.models import StudentProfile


class StatusChange(models.Model):
    """Every change to a student's academic status, with the reason, for the record."""

    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="status_changes")
    from_status = models.CharField(max_length=16, choices=StudentProfile.Status.choices)
    to_status = models.CharField(max_length=16, choices=StudentProfile.Status.choices)
    reason = models.CharField(max_length=300)
    effective_date = models.DateField(default=timezone.localdate)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.student}: {self.from_status} → {self.to_status}"


def document_upload_path(instance, filename):
    # Random names: the original filename is kept in the database, not on disk.
    ext = filename.rsplit(".", 1)[-1].lower()
    return f"student_documents/{timezone.now():%Y/%m}/{uuid.uuid4().hex}.{ext}"


class StudentDocument(models.Model):
    class Kind(models.TextChoices):
        ADMISSION_LETTER = "admission_letter", "Admission letter"
        OLEVEL = "olevel", "O-Level result"
        JAMB_RESULT = "jamb_result", "JAMB result slip"
        BIRTH_CERTIFICATE = "birth_certificate", "Birth certificate"
        LGA_CERTIFICATE = "lga_certificate", "Certificate of state of origin"
        MEDICAL = "medical", "Medical report"
        TRANSCRIPT = "transcript", "Transcript"
        LETTER = "letter", "Official letter"
        OTHER = "other", "Other"

    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="student_documents")
    kind = models.CharField(max_length=24, choices=Kind.choices)
    title = models.CharField(max_length=120, blank=True)
    file = models.FileField(upload_to=document_upload_path)
    original_filename = models.CharField(max_length=200)
    content_type = models.CharField(max_length=40)
    size = models.PositiveIntegerField()
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"{self.get_kind_display()} · {self.student}"
