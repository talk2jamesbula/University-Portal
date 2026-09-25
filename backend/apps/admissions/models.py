"""Online admissions: admission cycles, applications, their documents, fee payments and history."""

import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

MONEY = {"max_digits": 12, "decimal_places": 2}


class AdmissionCycle(models.Model):
    """One admission exercise, e.g. admission into the 2026/2027 session."""

    session = models.CharField(max_length=9, unique=True, help_text="e.g. 2026/2027")
    application_fee = models.DecimalField(**MONEY, default=10000)
    opens_on = models.DateField()
    closes_on = models.DateField(help_text="Last day applications can be started, paid for or submitted.")
    min_utme_score = models.PositiveSmallIntegerField(
        default=160, validators=[MaxValueValidator(400)], help_text="Lowest UTME score that may apply."
    )
    resumption_date = models.DateField(null=True, blank=True, help_text="Shown on admission letters.")
    acceptance_deadline = models.DateField(null=True, blank=True, help_text="Last day to accept an offer.")
    is_active = models.BooleanField(default=True, help_text="Only one cycle can be active at a time.")

    class Meta:
        ordering = ["-session"]
        constraints = [
            models.UniqueConstraint(
                fields=["is_active"], condition=Q(is_active=True), name="one_active_admission_cycle"
            ),
            models.CheckConstraint(condition=Q(closes_on__gte=models.F("opens_on")), name="cycle_closes_after_opening"),
        ]

    def __str__(self):
        return f"Admission {self.session}"

    @property
    def is_open(self):
        return self.is_active and self.opens_on <= timezone.localdate() <= self.closes_on

    @property
    def code(self):
        """ "2026/2027" → "2627", used in application and letter numbers."""
        return self.session[2:4] + self.session[7:9]

    @classmethod
    def current(cls):
        return cls.objects.filter(is_active=True).first()


class Application(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        UNDER_REVIEW = "under_review", "Under review"
        SCREENING = "screening", "Screening"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        WAITLISTED = "waitlisted", "Waitlisted"
        ADMITTED = "admitted", "Admitted"
        ACCEPTED = "accepted", "Accepted"

    class EntryMode(models.TextChoices):
        UTME = "utme", "UTME (100 Level)"
        DIRECT_ENTRY = "direct_entry", "Direct Entry (200 Level)"
        TRANSFER = "transfer", "Inter-university transfer"

    class Gender(models.TextChoices):
        MALE = "male", "Male"
        FEMALE = "female", "Female"

    cycle = models.ForeignKey(AdmissionCycle, on_delete=models.PROTECT, related_name="applications")
    applicant = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="applications")
    number = models.CharField(max_length=24, unique=True, null=True, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT, db_index=True)

    # Programme choice
    entry_mode = models.CharField(max_length=16, choices=EntryMode.choices, default=EntryMode.UTME)
    programme = models.ForeignKey(
        "academics.Programme", on_delete=models.PROTECT, null=True, blank=True, related_name="first_choice_applications"
    )
    second_choice = models.ForeignKey(
        "academics.Programme",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="second_choice_applications",
    )

    # Personal details
    middle_name = models.CharField(max_length=60, blank=True)
    gender = models.CharField(max_length=8, choices=Gender.choices, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    nationality = models.CharField(max_length=40, default="Nigerian")
    state_of_origin = models.CharField(max_length=40, blank=True)
    lga = models.CharField("LGA", max_length=60, blank=True)
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    nin = models.CharField("NIN", max_length=11, blank=True, help_text="National Identification Number")
    next_of_kin_name = models.CharField(max_length=120, blank=True)
    next_of_kin_relationship = models.CharField(max_length=40, blank=True)
    next_of_kin_phone = models.CharField(max_length=20, blank=True)

    # Academic record
    jamb_reg_number = models.CharField("JAMB registration number", max_length=16, blank=True)
    utme_score = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MaxValueValidator(400)])
    # [{"exam": "WAEC", "year": 2025, "subject": "Mathematics", "grade": "B3"}, ...]
    olevel_results = models.JSONField(default=list, blank=True)
    previous_institution = models.CharField(max_length=160, blank=True)
    previous_qualification = models.CharField(max_length=160, blank=True)

    submitted_at = models.DateTimeField(null=True, blank=True)

    # Review
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    screening_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Post-UTME screening score out of 100.",
    )
    screening_remarks = models.CharField(max_length=300, blank=True)
    screened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    screened_at = models.DateTimeField(null=True, blank=True)

    # Decision and offer
    decision_note = models.CharField(max_length=300, blank=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    admitted_programme = models.ForeignKey(
        "academics.Programme", on_delete=models.PROTECT, null=True, blank=True, related_name="admissions"
    )
    letter_number = models.CharField(max_length=32, unique=True, null=True, blank=True)
    letter_issued_at = models.DateTimeField(null=True, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-submitted_at", "-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["cycle", "applicant"], name="one_application_per_cycle"),
        ]

    def __str__(self):
        return f"{self.number or 'Draft'} · {self.applicant}"

    @property
    def aggregate_score(self):
        """The usual Nigerian aggregate out of 100: UTME (out of 400) ÷ 8 plus screening (out of 100) ÷ 2."""
        if self.utme_score is None or self.screening_score is None:
            return None
        return round(self.utme_score / 8 + float(self.screening_score) / 2, 2)

    @property
    def fee_paid(self):
        return self.payments.filter(status=ApplicationPayment.Status.SUCCESS).exists()


def document_upload_path(instance, filename):
    # Random names: the original filename is kept in the database, not on disk.
    ext = filename.rsplit(".", 1)[-1].lower()
    return f"admissions/{timezone.now():%Y/%m}/{uuid.uuid4().hex}.{ext}"


class ApplicationDocument(models.Model):
    class Kind(models.TextChoices):
        PASSPORT = "passport", "Passport photograph"
        OLEVEL = "olevel", "O-Level result (WAEC/NECO/NABTEB)"
        JAMB_RESULT = "jamb_result", "JAMB UTME result slip"
        BIRTH_CERTIFICATE = "birth_certificate", "Birth certificate or age declaration"
        LGA_CERTIFICATE = "lga_certificate", "Certificate of state of origin"
        OTHER = "other", "Other supporting document"

    REQUIRED = (Kind.PASSPORT, Kind.OLEVEL, Kind.JAMB_RESULT, Kind.BIRTH_CERTIFICATE)

    class Status(models.TextChoices):
        PENDING = "pending", "Awaiting verification"
        VERIFIED = "verified", "Verified"
        REJECTED = "rejected", "Rejected"

    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="documents")
    kind = models.CharField(max_length=24, choices=Kind.choices)
    file = models.FileField(upload_to=document_upload_path)
    original_filename = models.CharField(max_length=200)
    content_type = models.CharField(max_length=40)
    size = models.PositiveIntegerField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    review_note = models.CharField(max_length=300, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["kind"]
        constraints = [models.UniqueConstraint(fields=["application", "kind"], name="one_document_per_kind")]

    def __str__(self):
        return f"{self.get_kind_display()} · {self.application}"


class ApplicationPayment(models.Model):
    """The application fee, paid through Paystack."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SUCCESS = "success", "Successful"
        FAILED = "failed", "Failed"

    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="payments")
    reference = models.CharField(max_length=64, unique=True)
    amount = models.DecimalField(**MONEY)
    gateway = models.CharField(max_length=16, default="paystack")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    channel = models.CharField(max_length=30, blank=True)
    gateway_response = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            # A fee can only be paid once; a second successful charge would be a double payment.
            models.UniqueConstraint(
                fields=["application"], condition=Q(status="success"), name="one_successful_fee_payment"
            ),
        ]

    def __str__(self):
        return f"{self.reference} · ₦{self.amount:,} · {self.status}"


class ApplicationEvent(models.Model):
    """The application's history: every status change, document review, payment and note."""

    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="events")
    action = models.CharField(max_length=40)
    from_status = models.CharField(max_length=16, blank=True)
    to_status = models.CharField(max_length=16, blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    note = models.CharField(max_length=300, blank=True)
    # Shown to the applicant on their timeline; internal notes aren't.
    public = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self):
        return f"{self.action} · {self.application}"
