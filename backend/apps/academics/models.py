import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from .grading import CA_MAX, EXAM_MAX, grade_for

LEVELS = [(level, f"{level} Level") for level in (100, 200, 300, 400, 500, 600)]


def validate_session(value):
    """Academic sessions are written "2026/2027": two consecutive years."""
    match = re.fullmatch(r"(\d{4})/(\d{4})", value or "")
    if not match or int(match[2]) != int(match[1]) + 1:
        raise ValidationError('Enter the session as two consecutive years, e.g. "2026/2027".')


class Faculty(models.Model):
    code = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "faculties"

    def __str__(self):
        return self.name


class Department(models.Model):
    faculty = models.ForeignKey(Faculty, on_delete=models.PROTECT, related_name="departments")
    code = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Programme(models.Model):
    """A degree programme, e.g. B.Sc. Computer Science (4 years, 100–400 Level)."""

    class Degree(models.TextChoices):
        BSC = "B.Sc.", "Bachelor of Science"
        BA = "B.A.", "Bachelor of Arts"
        BENG = "B.Eng.", "Bachelor of Engineering"
        BED = "B.Ed.", "Bachelor of Education"
        LLB = "LL.B.", "Bachelor of Laws"
        MBBS = "MBBS", "Bachelor of Medicine, Bachelor of Surgery"

    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="programmes")
    code = models.CharField(max_length=12, unique=True)
    name = models.CharField(max_length=120)
    degree = models.CharField(max_length=8, choices=Degree.choices, default=Degree.BSC)
    duration_years = models.PositiveSmallIntegerField(
        default=4, validators=[MinValueValidator(1), MaxValueValidator(7)]
    )
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.title

    @property
    def title(self):
        return f"{self.degree} {self.name}"

    @property
    def final_level(self):
        return self.duration_years * 100


class Semester(models.Model):
    """One half of an academic session, e.g. First Semester 2026/2027."""

    class Number(models.IntegerChoices):
        FIRST = 1, "First Semester"
        SECOND = 2, "Second Semester"

    session = models.CharField(max_length=9, validators=[validate_session])
    number = models.PositiveSmallIntegerField(choices=Number.choices)
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False)
    registration_open = models.BooleanField(default=True, help_text="Students may register and add/drop courses.")
    # Billing: tuition is charged per registered unit; all semester charges are due on fee_due_date.
    tuition_per_unit = models.DecimalField(max_digits=10, decimal_places=2, default=350)
    fee_due_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["-start_date"]
        constraints = [
            models.UniqueConstraint(fields=["session", "number"], name="unique_semester_per_session"),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # Only one semester can be current at a time.
        if self.is_current:
            Semester.objects.exclude(pk=self.pk).update(is_current=False)
        super().save(*args, **kwargs)

    @property
    def name(self):
        return f"{self.get_number_display()} {self.session}"

    @property
    def code(self):
        """Compact form for document numbers, e.g. 2627-1 for First Semester 2026/2027."""
        start, end = self.session.split("/")
        return f"{start[2:]}{end[2:]}-{self.number}"

    def clean(self):
        if self.start_date and self.end_date and self.start_date >= self.end_date:
            raise ValidationError("The semester must end after it starts.")


class Course(models.Model):
    """A course in the catalogue, e.g. CSC 201 Data Structures (3 units, 200 Level, First Semester)."""

    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="courses")
    code = models.CharField(max_length=12, unique=True)
    title = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    units = models.PositiveSmallIntegerField(default=3, validators=[MinValueValidator(1), MaxValueValidator(6)])
    level = models.PositiveSmallIntegerField(choices=LEVELS, default=100)
    semester_number = models.PositiveSmallIntegerField(choices=Semester.Number.choices, default=Semester.Number.FIRST)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} {self.title}"


class ProgrammeCourse(models.Model):
    """A course in a programme's curriculum, and whether it's compulsory or elective there."""

    programme = models.ForeignKey(Programme, on_delete=models.CASCADE, related_name="curriculum")
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="programmes")
    is_compulsory = models.BooleanField(default=True)

    class Meta:
        ordering = ["course__level", "course__semester_number", "course__code"]
        constraints = [
            models.UniqueConstraint(fields=["programme", "course"], name="unique_programme_course"),
        ]

    def __str__(self):
        kind = "compulsory" if self.is_compulsory else "elective"
        return f"{self.programme.code}: {self.course.code} ({kind})"


class CourseOffering(models.Model):
    """A course taught in a particular semester: lecturer, timetable, venue and capacity."""

    class Weekday(models.TextChoices):
        MON = "MON", "Monday"
        TUE = "TUE", "Tuesday"
        WED = "WED", "Wednesday"
        THU = "THU", "Thursday"
        FRI = "FRI", "Friday"

    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name="offerings")
    semester = models.ForeignKey(Semester, on_delete=models.PROTECT, related_name="offerings")
    lecturer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="offerings_taught",
    )
    capacity = models.PositiveIntegerField(default=120)
    # Comma separated weekday codes, e.g. "MON,WED".
    days = models.CharField(max_length=32, blank=True)
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    venue = models.CharField(max_length=80, blank=True)

    class Meta:
        ordering = ["course__code"]
        constraints = [
            models.UniqueConstraint(fields=["course", "semester"], name="unique_offering_per_semester"),
        ]

    def __str__(self):
        return f"{self.course.code} ({self.semester})"

    def clean(self):
        if self.start_time and self.end_time and self.start_time >= self.end_time:
            raise ValidationError("End time must be after start time.")

    @property
    def day_list(self):
        return [d for d in self.days.split(",") if d]


class Enrollment(models.Model):
    """A student's registration for a course offering, and their result in it."""

    class Status(models.TextChoices):
        REGISTERED = "registered", "Registered"
        DROPPED = "dropped", "Dropped"

    class ResultStatus(models.TextChoices):
        """Results move lecturer → HOD → Dean → publication before students can see them."""

        PENDING = "pending", "Not yet entered"
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted to HOD"
        DEPARTMENT_APPROVED = "department_approved", "Approved by HOD"
        FACULTY_APPROVED = "faculty_approved", "Approved by Dean"
        PUBLISHED = "published", "Published"

    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="enrollments")
    offering = models.ForeignKey(CourseOffering, on_delete=models.CASCADE, related_name="enrollments")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.REGISTERED)
    is_carryover = models.BooleanField(default=False, help_text="Re-registration of a course previously failed.")
    ca_score = models.DecimalField(
        "CA score",
        max_digits=4,
        decimal_places=1,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(CA_MAX)],
    )
    exam_score = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(EXAM_MAX)],
    )
    result_status = models.CharField(max_length=24, choices=ResultStatus.choices, default=ResultStatus.PENDING)
    registered_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-registered_at"]
        constraints = [
            models.UniqueConstraint(fields=["student", "offering"], name="unique_registration"),
        ]

    def __str__(self):
        return f"{self.student} → {self.offering}"

    @property
    def total_score(self):
        if self.ca_score is None or self.exam_score is None:
            return None
        return self.ca_score + self.exam_score

    @property
    def grade(self):
        total = self.total_score
        return grade_for(total)[0] if total is not None else None

    @property
    def grade_points(self):
        total = self.total_score
        return grade_for(total)[1] if total is not None else None

    @property
    def is_published(self):
        return self.result_status == self.ResultStatus.PUBLISHED


class ResultAction(models.Model):
    """One step in a course's results workflow (submitted, approved, returned, published), with who and why."""

    class Action(models.TextChoices):
        SUBMIT = "submit", "Submitted to HOD"
        APPROVE_DEPARTMENT = "approve_department", "Approved by HOD"
        APPROVE_FACULTY = "approve_faculty", "Approved by Dean"
        PUBLISH = "publish", "Published"
        RETURN = "return", "Returned to lecturer"

    offering = models.ForeignKey(CourseOffering, on_delete=models.CASCADE, related_name="result_actions")
    action = models.CharField(max_length=20, choices=Action.choices)
    from_status = models.CharField(max_length=24, choices=Enrollment.ResultStatus.choices)
    to_status = models.CharField(max_length=24, choices=Enrollment.ResultStatus.choices)
    note = models.CharField(max_length=500, blank=True)
    by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-at"]

    def __str__(self):
        return f"{self.offering}: {self.get_action_display()}"
