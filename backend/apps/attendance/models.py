import secrets
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


def new_secret():
    return secrets.token_hex(16)


class AttendanceSession(models.Model):
    """One class meeting of a course offering at which attendance is taken."""

    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        OPEN = "open", "Open for check-in"
        CLOSED = "closed", "Closed"

    offering = models.ForeignKey(
        "academics.CourseOffering", on_delete=models.CASCADE, related_name="attendance_sessions"
    )
    date = models.DateField()
    start_time = models.TimeField()
    topic = models.CharField(max_length=160, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.SCHEDULED)
    checkin_minutes = models.PositiveSmallIntegerField(default=15, help_text="How long students may check in.")
    late_after_minutes = models.PositiveSmallIntegerField(default=10, help_text="Check-ins after this count as late.")
    # Signs the rotating QR / 6-digit codes; never sent to students.
    secret = models.CharField(max_length=32, default=new_secret, editable=False)
    opened_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-start_time"]
        constraints = [
            models.UniqueConstraint(fields=["offering", "date", "start_time"], name="unique_session_per_slot"),
        ]

    def __str__(self):
        return f"{self.offering.course.code} · {self.date:%d %b %Y} {self.start_time:%H:%M}"

    @property
    def checkin_closes_at(self):
        return self.opened_at + timedelta(minutes=self.checkin_minutes) if self.opened_at else None

    @property
    def is_accepting_checkins(self):
        return self.status == self.Status.OPEN and timezone.now() <= self.checkin_closes_at


class AttendanceRecord(models.Model):
    class Status(models.TextChoices):
        PRESENT = "present", "Present"
        LATE = "late", "Late"
        EXCUSED = "excused", "Excused"
        ABSENT = "absent", "Absent"

    class Method(models.TextChoices):
        QR = "qr", "QR code"
        CODE = "code", "Check-in code"
        LECTURER = "lecturer", "Marked by lecturer"
        UPLOAD = "upload", "Uploaded register"
        CORRECTION = "correction", "Approved correction"
        SYSTEM = "system", "Absent at close"

    # Statuses that count as attending for the attendance percentage.
    ATTENDED = (Status.PRESENT, Status.LATE, Status.EXCUSED)

    session = models.ForeignKey(AttendanceSession, on_delete=models.CASCADE, related_name="records")
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="attendance")
    status = models.CharField(max_length=10, choices=Status.choices)
    method = models.CharField(max_length=12, choices=Method.choices)
    marked_at = models.DateTimeField(default=timezone.now)
    marked_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    # Duplicate safeguards: where a self check-in came from, and whether it looks suspicious.
    device_id = models.CharField(max_length=64, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    flagged = models.BooleanField(default=False)
    flag_reason = models.CharField(max_length=160, blank=True)

    class Meta:
        ordering = ["student__university_id"]
        constraints = [
            # The core guarantee: one record per student per session, however many times they scan.
            models.UniqueConstraint(fields=["session", "student"], name="one_record_per_student_per_session"),
        ]
        indexes = [models.Index(fields=["session", "device_id"])]

    def __str__(self):
        return f"{self.student} · {self.session} · {self.status}"

    @property
    def attended(self):
        return self.status in self.ATTENDED


class AttendanceCorrection(models.Model):
    """A change to a closed session's record. Needs approval by the HOD (or another approver)."""

    class Status(models.TextChoices):
        PENDING = "pending", "Awaiting approval"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    record = models.ForeignKey(AttendanceRecord, on_delete=models.CASCADE, related_name="corrections")
    from_status = models.CharField(max_length=10, choices=AttendanceRecord.Status.choices)
    to_status = models.CharField(max_length=10, choices=AttendanceRecord.Status.choices)
    reason = models.CharField(max_length=300)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    decision_note = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["record"], condition=models.Q(status="pending"), name="one_pending_correction_per_record"
            ),
        ]

    def __str__(self):
        return f"{self.record}: {self.from_status} → {self.to_status} ({self.status})"
