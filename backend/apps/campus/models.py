from django.conf import settings
from django.db import models


class Announcement(models.Model):
    class Audience(models.TextChoices):
        ALL = "all", "Everyone"
        STUDENTS = "student", "Students"
        STAFF = "staff", "Staff"

    class Priority(models.TextChoices):
        NORMAL = "normal", "Normal"
        IMPORTANT = "important", "Important"
        URGENT = "urgent", "Urgent"

    title = models.CharField(max_length=200)
    body = models.TextField()
    audience = models.CharField(max_length=16, choices=Audience.choices, default=Audience.ALL)
    priority = models.CharField(max_length=16, choices=Priority.choices, default=Priority.NORMAL)
    # Optional scope: one course offering's lecturer and students, or one department's members.
    offering = models.ForeignKey(
        "academics.CourseOffering",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="announcements",
    )
    department = models.ForeignKey(
        "academics.Department",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="announcements",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="announcements"
    )
    pinned = models.BooleanField(default=False)
    is_public = models.BooleanField(
        "Publish on the website", default=False, help_text="Also show this as news on the public website."
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-pinned", "-created_at"]

    def __str__(self):
        return self.title


class Event(models.Model):
    class Category(models.TextChoices):
        ACADEMIC = "academic", "Academic"
        CAREER = "career", "Career"
        SOCIAL = "social", "Social"
        SPORTS = "sports", "Sports"
        DEADLINE = "deadline", "Deadline"

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=16, choices=Category.choices, default=Category.ACADEMIC)
    location = models.CharField(max_length=120, blank=True)
    is_public = models.BooleanField("Show on the website", default=True)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["starts_at"]

    def __str__(self):
        return self.title
