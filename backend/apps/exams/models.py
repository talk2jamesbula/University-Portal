from datetime import datetime, timedelta

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class Venue(models.Model):
    """An examination hall or CBT centre."""

    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=120)
    capacity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    location = models.CharField(max_length=160, blank=True)
    is_cbt_centre = models.BooleanField("CBT centre", default=False, help_text="Has computers for online exams.")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Exam(models.Model):
    """The examination for a course offering: when and where it's written, and whether on paper or by CBT."""

    class Mode(models.TextChoices):
        PAPER = "paper", "Written (paper)"
        CBT = "cbt", "Computer-based test"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "On the timetable"

    offering = models.OneToOneField("academics.CourseOffering", on_delete=models.CASCADE, related_name="exam")
    date = models.DateField()
    start_time = models.TimeField()
    duration_minutes = models.PositiveSmallIntegerField(
        default=120, validators=[MinValueValidator(10), MaxValueValidator(360)]
    )
    mode = models.CharField(max_length=8, choices=Mode.choices, default=Mode.PAPER)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    venues = models.ManyToManyField(Venue, blank=True, related_name="exams")
    instructions = models.TextField(blank=True, help_text="Shown to candidates before they start.")
    # CBT only.
    questions_per_candidate = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text="Draw this many questions at random for each candidate; blank for all."
    )
    late_entry_minutes = models.PositiveSmallIntegerField(
        default=30, validators=[MaxValueValidator(120)], help_text="How long after the start a CBT can be begun."
    )
    scores_released_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["date", "start_time"]

    def __str__(self):
        return f"{self.offering.course.code} exam · {self.date:%d %b %Y} {self.start_time:%H:%M}"

    @property
    def starts_at(self):
        return timezone.make_aware(datetime.combine(self.date, self.start_time))

    @property
    def ends_at(self):
        return self.starts_at + timedelta(minutes=self.duration_minutes)

    @property
    def entry_closes_at(self):
        """The last moment a CBT can be started."""
        return self.starts_at + timedelta(minutes=self.late_entry_minutes)

    @property
    def closes_at(self):
        """When the last possible CBT attempt ends."""
        return self.entry_closes_at + timedelta(minutes=self.duration_minutes)

    @property
    def is_cbt(self):
        return self.mode == self.Mode.CBT

    def overlaps(self, other):
        return self.date == other.date and self.starts_at < other.ends_at and other.starts_at < self.ends_at


class Candidate(models.Model):
    """A student's place at an exam: their seat, any eligibility waiver, and whether they turned up."""

    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="candidates")
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="exam_candidacies")
    venue = models.ForeignKey(Venue, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    seat_number = models.PositiveIntegerField(null=True, blank=True)
    # The Exams Office may let a student sit despite the attendance or fees rule (e.g. medical grounds).
    waived = models.BooleanField(default=False)
    waiver_reason = models.CharField(max_length=300, blank=True)
    waived_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    checked_in_at = models.DateTimeField(null=True, blank=True)
    checked_in_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    class Meta:
        ordering = ["venue__name", "seat_number"]
        constraints = [
            models.UniqueConstraint(fields=["exam", "student"], name="one_candidacy_per_exam"),
            models.UniqueConstraint(fields=["exam", "venue", "seat_number"], name="one_candidate_per_seat"),
        ]

    def __str__(self):
        return f"{self.student} · {self.exam}"


# --- Computer-based tests ---------------------------------------------------------------------------


class Question(models.Model):
    """A multiple-choice (or true/false) question in a CBT exam."""

    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="questions")
    text = models.TextField()
    marks = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1), MaxValueValidator(20)])
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.text[:60]


class Choice(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="choices")
    text = models.CharField(max_length=500)
    is_correct = models.BooleanField(default=False)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.text[:60]


class Attempt(models.Model):
    """A student's one sitting of a CBT. The paper (question and option order) is fixed when it starts."""

    class Status(models.TextChoices):
        IN_PROGRESS = "in_progress", "In progress"
        SUBMITTED = "submitted", "Submitted"
        TIMED_OUT = "timed_out", "Submitted when time ran out"

    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="attempts")
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="exam_attempts")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.IN_PROGRESS)
    started_at = models.DateTimeField(default=timezone.now)
    deadline = models.DateTimeField()
    submitted_at = models.DateTimeField(null=True, blank=True)
    # This candidate's paper: question ids in order, and each question's option ids in order.
    question_ids = models.JSONField(default=list)
    choice_order = models.JSONField(default=dict)
    score = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True, help_text="Marks obtained.")
    max_score = models.PositiveIntegerField(default=0)
    focus_losses = models.PositiveIntegerField(default=0, help_text="Times the candidate left the exam page.")
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ["student__university_id"]
        constraints = [
            # One attempt per student per exam, whatever happens.
            models.UniqueConstraint(fields=["exam", "student"], name="one_attempt_per_exam"),
        ]

    def __str__(self):
        return f"{self.student} · {self.exam} ({self.status})"

    @property
    def is_open(self):
        return self.status == self.Status.IN_PROGRESS

    @property
    def flagged(self):
        return self.focus_losses >= settings.EXAM_FOCUS_FLAG_AFTER


class Answer(models.Model):
    attempt = models.ForeignKey(Attempt, on_delete=models.CASCADE, related_name="answers")
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="+")
    choice = models.ForeignKey(Choice, on_delete=models.CASCADE, null=True, blank=True, related_name="+")
    answered_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["attempt", "question"], name="one_answer_per_question"),
        ]

    def __str__(self):
        return f"{self.attempt} · Q{self.question_id}"


class AttemptEvent(models.Model):
    """Something the lecturer may want to know about during a CBT, e.g. the candidate switching tabs."""

    class Kind(models.TextChoices):
        LEFT_PAGE = "left_page", "Left the exam page"
        RETURNED = "returned", "Came back to the exam page"
        FULLSCREEN_EXIT = "fullscreen_exit", "Left full screen"

    attempt = models.ForeignKey(Attempt, on_delete=models.CASCADE, related_name="events")
    kind = models.CharField(max_length=16, choices=Kind.choices)
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["at"]

    def __str__(self):
        return f"{self.attempt} · {self.get_kind_display()}"
