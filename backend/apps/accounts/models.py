from functools import cached_property

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.db.models.signals import post_delete
from django.dispatch import receiver

from . import numbering
from .rbac import PERMISSIONS


class User(AbstractUser):
    class Role(models.TextChoices):
        """Account type. What staff may do comes from their role appointments (see RoleAssignment)."""

        STUDENT = "student", "Student"
        STAFF = "staff", "Staff"
        APPLICANT = "applicant", "Applicant"
        ADMIN = "admin", "Super Admin"

    role = models.CharField(max_length=16, choices=Role.choices, default=Role.STUDENT)
    title = models.CharField(max_length=20, blank=True, help_text="e.g. Prof., Dr., Mrs.")
    # Matriculation number for students, staff number for staff.
    university_id = models.CharField(max_length=20, unique=True, null=True, blank=True)
    department = models.ForeignKey(
        "academics.Department", on_delete=models.SET_NULL, null=True, blank=True, related_name="members"
    )
    phone = models.CharField(max_length=32, blank=True)
    bio = models.TextField(blank=True)
    # Processed by accounts.avatars; always a 256×256 JPEG under media/avatars/. Doubles as the
    # student's passport photograph.
    avatar = models.ImageField(upload_to="avatars/", blank=True)

    class Meta:
        ordering = ["last_name", "first_name"]

    def __str__(self):
        return self.get_full_name() or self.username

    def save(self, *args, **kwargs):
        # Staff and admin numbers are assigned automatically (student matric numbers: see StudentProfile).
        generate = {self.Role.STAFF: numbering.staff_number, self.Role.ADMIN: numbering.admin_number}.get(self.role)
        if generate and not self.university_id:
            numbering.save_with_number(self, "university_id", generate, lambda: super(User, self).save(*args, **kwargs))
        else:
            super().save(*args, **kwargs)

    def get_full_name(self):
        name = super().get_full_name()
        return f"{self.title} {name}".strip() if self.title and name else name

    # --- Account type ---------------------------------------------------------------------

    @property
    def is_student(self):
        return self.role == self.Role.STUDENT

    @property
    def is_staff_member(self):
        return self.role == self.Role.STAFF

    @property
    def is_applicant(self):
        return self.role == self.Role.APPLICANT

    @property
    def is_super_admin(self):
        return self.role == self.Role.ADMIN or self.is_superuser

    # --- Permissions ----------------------------------------------------------------------

    @cached_property
    def role_assignments(self):
        return list(self.assignments.select_related("role", "faculty", "department"))

    @cached_property
    def role_codes(self):
        return sorted({a.role.code for a in self.role_assignments})

    @cached_property
    def permission_codes(self):
        if self.is_super_admin:
            return set(PERMISSIONS)
        return {code for a in self.role_assignments for code in a.role.permissions}

    def has_permission(self, *codes):
        """True if the user holds any of the given permission codes."""
        return bool(self.is_active and self.permission_codes & set(codes))

    def permission_scope(self, code):
        """Where `code` applies for this user.

        None means everywhere (super admins, or a university-wide role such as Registrar).
        Otherwise (department_ids, faculty_ids) from scoped roles such as HOD or Dean; both
        empty means the user doesn't hold the permission at all.
        """
        if self.is_super_admin:
            return None
        departments, faculties = set(), set()
        for a in self.role_assignments:
            if code not in a.role.permissions:
                continue
            if not (a.department_id or a.faculty_id):
                return None
            if a.department_id:
                departments.add(a.department_id)
            if a.faculty_id:
                faculties.add(a.faculty_id)
        return departments, faculties

    def scope_filter(self, code, department_path):
        """A Q limiting a queryset to where `code` applies, given the lookup path to a Department,
        e.g. user.scope_filter("attendance.view", "offering__course__department")."""
        scope = self.permission_scope(code)
        if scope is None:
            return Q()
        departments, faculties = scope
        return Q(**{f"{department_path}__in": departments}) | Q(**{f"{department_path}__faculty__in": faculties})

    def can_act_on_department(self, code, department_id, faculty_id):
        scope = self.permission_scope(code)
        if scope is None:
            return True
        departments, faculties = scope
        return department_id in departments or faculty_id in faculties

    # --- Profile photo --------------------------------------------------------------------

    @property
    def avatar_url(self):
        return f"{settings.MEDIA_URL}{self.avatar.name}" if self.avatar else None

    def set_avatar(self, content):
        """Replace the profile photo (or remove it when content is None), deleting the old file."""
        old = self.avatar.name
        if content is None:
            self.avatar = ""
        else:
            self.avatar.save(content.name, content, save=False)
        self.save(update_fields=["avatar"])
        if old and old != self.avatar.name:
            self.avatar.storage.delete(old)


@receiver(post_delete, sender=User)
def delete_avatar_file(sender, instance, **kwargs):
    if instance.avatar:
        instance.avatar.storage.delete(instance.avatar.name)


class Role(models.Model):
    """A staff role (Bursar, HOD, Lecturer...) and the permission codes it grants."""

    class Scope(models.TextChoices):
        NONE = "", "University-wide"
        FACULTY = "faculty", "Faculty"
        DEPARTMENT = "department", "Department"

    code = models.SlugField(max_length=40, unique=True)
    name = models.CharField(max_length=80)
    scope = models.CharField(max_length=16, choices=Scope.choices, blank=True)
    permissions = models.JSONField(default=list)
    is_system = models.BooleanField(default=False, help_text="Created by the portal; can't be deleted.")

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def clean(self):
        unknown = set(self.permissions) - set(PERMISSIONS)
        if unknown:
            raise ValidationError({"permissions": f"Unknown permissions: {', '.join(sorted(unknown))}"})


class RoleAssignment(models.Model):
    """A staff member's appointment to a role, e.g. HOD of Computer Science."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="assignments")
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="assignments")
    faculty = models.ForeignKey("academics.Faculty", on_delete=models.CASCADE, null=True, blank=True)
    department = models.ForeignKey("academics.Department", on_delete=models.CASCADE, null=True, blank=True)
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["role__name"]
        constraints = [
            models.UniqueConstraint(fields=["user", "role", "faculty", "department"], name="unique_role_assignment"),
        ]

    def __str__(self):
        where = self.department or self.faculty
        return f"{self.user} — {self.role}" + (f" ({where.name})" if where else "")

    def clean(self):
        if self.role.scope == Role.Scope.FACULTY and not self.faculty_id:
            raise ValidationError({"faculty": f"Choose the faculty this {self.role.name} is responsible for."})
        if self.role.scope == Role.Scope.DEPARTMENT and not self.department_id:
            raise ValidationError({"department": f"Choose the department this {self.role.name} heads."})


class StudentProfile(models.Model):
    """Everything about a student beyond their login: programme, level, personal and contact details."""

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        PROBATION = "probation", "On probation"
        SUSPENDED = "suspended", "Suspended"
        DEFERRED = "deferred", "Deferred"
        WITHDRAWN = "withdrawn", "Withdrawn"
        EXPELLED = "expelled", "Expelled"
        COMPLETED = "completed", "Completed (awaiting graduation)"
        GRADUATED = "graduated", "Graduated"

    class Entry(models.TextChoices):
        UTME = "utme", "UTME"
        DIRECT_ENTRY = "de", "Direct Entry"
        TRANSFER = "transfer", "Inter-university transfer"

    class Gender(models.TextChoices):
        FEMALE = "female", "Female"
        MALE = "male", "Male"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="student_profile")
    # A permanent internal ID (the matriculation number is on the user as university_id).
    student_id = models.CharField(max_length=16, unique=True, null=True, blank=True)
    programme = models.ForeignKey("academics.Programme", on_delete=models.PROTECT, related_name="students")
    level = models.PositiveSmallIntegerField(default=100)
    current_session = models.CharField(max_length=9, blank=True, help_text="Academic session the student is in")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    # Admission
    entry_session = models.CharField(max_length=9, blank=True)
    mode_of_entry = models.CharField(max_length=16, choices=Entry.choices, default=Entry.UTME)
    admission_date = models.DateField(null=True, blank=True)
    jamb_reg_number = models.CharField("JAMB registration number", max_length=16, blank=True)
    # Personal
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=8, choices=Gender.choices, blank=True)
    nationality = models.CharField(max_length=60, default="Nigerian")
    state_of_origin = models.CharField(max_length=40, blank=True)
    lga = models.CharField("LGA", max_length=60, blank=True)
    home_address = models.CharField(max_length=255, blank=True)
    country = models.CharField(max_length=60, default="Nigeria", help_text="Country of residence")
    # Next of kin
    next_of_kin_name = models.CharField(max_length=120, blank=True)
    next_of_kin_relationship = models.CharField(max_length=40, blank=True)
    next_of_kin_phone = models.CharField(max_length=32, blank=True)
    next_of_kin_address = models.CharField(max_length=255, blank=True)
    # Emergency contact
    emergency_contact_name = models.CharField(max_length=120, blank=True)
    emergency_contact_relationship = models.CharField(max_length=40, blank=True)
    emergency_contact_phone = models.CharField(max_length=32, blank=True)

    def __str__(self):
        return f"{self.user} · {self.programme} · {self.level}L"

    def save(self, *args, **kwargs):
        user = self.user
        if not user.university_id:  # the matric number is assigned automatically
            numbering.save_with_number(
                user,
                "university_id",
                lambda: numbering.matric_number(self.programme, self.entry_session or self.current_session),
                lambda: user.save(update_fields=["university_id"]),
            )
        super().save(*args, **kwargs)
        if not self.student_id:
            self.student_id = f"STU{self.pk:07d}"
            super().save(update_fields=["student_id"])


class StaffProfile(models.Model):
    class Category(models.TextChoices):
        ACADEMIC = "academic", "Academic"
        NON_ACADEMIC = "non_academic", "Non-academic"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="staff_profile")
    category = models.CharField(max_length=16, choices=Category.choices, default=Category.ACADEMIC)
    designation = models.CharField(max_length=80, blank=True, help_text="e.g. Senior Lecturer, Deputy Bursar")
    qualifications = models.CharField(max_length=200, blank=True)
    office = models.CharField(max_length=80, blank=True)

    def __str__(self):
        return f"{self.user} · {self.designation}"


class LoginEvent(models.Model):
    """Sign-in history, successful or not, for security review."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, related_name="logins")
    username = models.CharField(max_length=150)
    successful = models.BooleanField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        outcome = "signed in" if self.successful else "failed to sign in"
        return f"{self.username} {outcome} at {self.created_at:%Y-%m-%d %H:%M}"
