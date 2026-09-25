from django.db import models


class ContactMessage(models.Model):
    """A message sent from the public website's contact form."""

    class Topic(models.TextChoices):
        GENERAL = "general", "General enquiry"
        ADMISSIONS = "admissions", "Admissions"
        ACADEMIC = "academic", "Academic matters"
        FINANCE = "finance", "Fees and payments"
        TECHNICAL = "technical", "Portal / technical support"

    name = models.CharField(max_length=120)
    email = models.EmailField()
    phone = models.CharField(max_length=32, blank=True)
    topic = models.CharField(max_length=16, choices=Topic.choices, default=Topic.GENERAL)
    subject = models.CharField(max_length=160)
    message = models.TextField(max_length=5000)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    handled = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name}: {self.subject}"
