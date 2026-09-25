"""Student records: who may see them, creating and updating students, status changes and access.

Every change is written to the audit log (and status changes to the student's status history).
"""

import secrets

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts import numbering
from apps.accounts.models import StudentProfile
from apps.core.models import Notification
from apps.core.services import audit, notify

from .models import StatusChange

User = get_user_model()
Status = StudentProfile.Status

PROFILE_FIELDS = [
    "programme",
    "level",
    "current_session",
    "entry_session",
    "mode_of_entry",
    "admission_date",
    "jamb_reg_number",
    "gender",
    "date_of_birth",
    "nationality",
    "state_of_origin",
    "lga",
    "home_address",
    "country",
    "next_of_kin_name",
    "next_of_kin_relationship",
    "next_of_kin_phone",
    "next_of_kin_address",
    "emergency_contact_name",
    "emergency_contact_relationship",
    "emergency_contact_phone",
]
USER_FIELDS = ["first_name", "last_name", "email", "phone"]

# Statuses in which a student is (normally) still expected to sign in.
ENROLLED = (Status.ACTIVE, Status.PROBATION, Status.DEFERRED, Status.SUSPENDED, Status.COMPLETED)


# --- Access -------------------------------------------------------------------------------------


def can_manage(user):
    return user.has_permission("students.manage")


def can_view(user):
    return user.has_permission("students.manage", "students.view")


def visible_students(user):
    """Students the user may see: everyone for the Registry; their department or faculty for HODs and Deans."""
    qs = User.objects.filter(role=User.Role.STUDENT, student_profile__isnull=False)
    if can_manage(user):
        return qs
    if not user.has_permission("students.view"):
        return qs.none()
    return qs.filter(user.scope_filter("students.view", "student_profile__programme__department"))


def require_manage(user):
    if not can_manage(user):
        raise PermissionDenied("Only the Registry can change student records.")


# --- Numbers and passwords ----------------------------------------------------------------------


def username_for(matric_number):
    return matric_number.replace("/", "").lower()


def temporary_password():
    """Readable but strong: shown once to the Registry (or emailed) and changed by the student."""
    return f"Bu-{secrets.token_urlsafe(8)}"


# --- Create and update --------------------------------------------------------------------------


@transaction.atomic
def create_student(data, by, request=None, *, notify_student=True):
    """Create the login and the student record, with a matric number the system assigns.
    Returns (user, temporary password)."""
    require_manage(by)
    programme = data["programme"]
    password = temporary_password()
    user = User(role=User.Role.STUDENT, department=programme.department, **{f: data.get(f, "") for f in USER_FIELDS})
    user.set_password(password)

    def save():
        user.username = username_for(user.university_id)  # students sign in with their matric number
        user.save()

    numbering.save_with_number(
        user, "university_id", lambda: numbering.matric_number(programme, data["entry_session"]), save
    )
    matric = user.university_id
    profile = StudentProfile.objects.create(
        user=user,
        status=Status.ACTIVE,
        **{f: data[f] for f in PROFILE_FIELDS if f in data},
    )
    audit(
        request,
        "students.create",
        user,
        f"Created student {user.get_full_name()} ({matric}, {profile.student_id})",
        actor=by,
    )
    if notify_student:
        notify(
            [user],
            "Welcome to the student portal",
            f"Your student record has been created. Matric number: {matric}. Sign in with your matric number; "
            "the Registry will give you your first password. Change it after you sign in.",
            link="/portal/profile",
            category=Notification.Category.ACADEMIC,
            email=True,
        )
    return user, password


def _label(value):
    return "—" if value in ("", None) else str(value)


@transaction.atomic
def update_student(student, data, by, request=None):
    """Apply changes; the audit log records which fields changed, from what, to what."""
    require_manage(by)
    profile = student.student_profile
    changes = []
    for field in USER_FIELDS:
        if field in data and getattr(student, field) != data[field]:
            changes.append(f"{field}: {_label(getattr(student, field))} → {_label(data[field])}")
            setattr(student, field, data[field])
    for field in PROFILE_FIELDS:
        if field in data and getattr(profile, field) != data[field]:
            changes.append(f"{field.replace('_', ' ')}: {_label(getattr(profile, field))} → {_label(data[field])}")
            setattr(profile, field, data[field])
    if not changes:
        return student
    # The department follows the programme; HOD and Dean access depends on it.
    student.department = profile.programme.department
    student.save()
    profile.save()
    audit(request, "students.update", student, f"Updated {student.university_id}: {'; '.join(changes)}"[:255], actor=by)
    return student


@transaction.atomic
def change_status(student, to_status, reason, by, request=None, effective_date=None):
    require_manage(by)
    profile = StudentProfile.objects.select_for_update().get(user=student)
    if profile.status == to_status:
        raise ValidationError({"status": f"The student is already {profile.get_status_display().lower()}."})
    change = StatusChange.objects.create(
        student=student,
        from_status=profile.status,
        to_status=to_status,
        reason=reason,
        effective_date=effective_date or timezone.localdate(),
        changed_by=by,
    )
    profile.status = to_status
    profile.save(update_fields=["status"])
    audit(
        request,
        "students.status",
        student,
        f"{student.university_id}: {Status(change.from_status).label} → {Status(to_status).label}. {reason}"[:255],
        actor=by,
    )
    notify(
        [student],
        f"Your academic status is now: {Status(to_status).label}",
        f"Effective {change.effective_date:%d %B %Y}. Reason: {reason}\n\nContact the Registry if you have questions.",
        link="/portal/profile",
        category=Notification.Category.ACADEMIC,
        email=True,
    )
    return change


def set_active(student, active, reason, by, request=None):
    """Allow or block sign-in to the portal (separate from academic status)."""
    require_manage(by)
    if student.is_active == active:
        raise ValidationError(f"The account is already {'active' if active else 'deactivated'}.")
    student.is_active = active
    student.save(update_fields=["is_active"])
    verb = "Activated" if active else "Deactivated"
    audit(
        request,
        f"students.{'activate' if active else 'deactivate'}",
        student,
        f"{verb} portal access for {student.university_id}. {reason}".strip()[:255],
        actor=by,
    )
    return student


def reset_password(student, by, request=None):
    require_manage(by)
    password = temporary_password()
    student.set_password(password)
    student.save(update_fields=["password"])
    audit(request, "students.password_reset", student, f"Reset the password of {student.university_id}", actor=by)
    return password


def search_filter(term):
    term = term.strip()
    q = (
        Q(first_name__icontains=term)
        | Q(last_name__icontains=term)
        | Q(email__icontains=term)
        | Q(phone__icontains=term)
        | Q(university_id__icontains=term)
        | Q(student_profile__student_id__icontains=term)
        | Q(student_profile__jamb_reg_number__icontains=term)
    )
    parts = term.split()
    if len(parts) == 2:  # "Ada Okafor" or "Okafor Ada"
        a, b = parts
        q |= Q(first_name__iexact=a, last_name__icontains=b) | Q(first_name__iexact=b, last_name__icontains=a)
    return q
