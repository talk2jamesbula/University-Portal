"""Attendance rules: rotating check-in codes, check-in safeguards, marking, closing and corrections."""

import hashlib
import hmac
import time
from collections import defaultdict
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.academics.models import CourseOffering, Enrollment
from apps.core.models import Notification
from apps.core.services import notify

from .models import AttendanceCorrection, AttendanceRecord, AttendanceSession

User = get_user_model()
Status = AttendanceRecord.Status
Method = AttendanceRecord.Method
REGISTERED = Enrollment.Status.REGISTERED


# --- Rotating codes -----------------------------------------------------------------------------
#
# The QR code and the 6-digit code both change every ATTENDANCE_CODE_SECONDS. A code is accepted
# during its own window and the one after it, so a screenshot forwarded to an absent friend stops
# working within about two windows.


def _window(at=None):
    return int((at or time.time()) // settings.ATTENDANCE_CODE_SECONDS)


def _digest(session, window):
    message = f"{session.pk}:{window}".encode()
    return hmac.new(session.secret.encode(), message, hashlib.sha256).hexdigest()


def current_codes(session):
    """(token for the QR link, 6-digit code, seconds until they change)."""
    window = _window()
    digest = _digest(session, window)
    seconds_left = settings.ATTENDANCE_CODE_SECONDS - int(time.time() % settings.ATTENDANCE_CODE_SECONDS)
    return digest[:16], f"{int(digest[16:28], 16) % 1_000_000:06d}", seconds_left


def code_is_valid(session, token="", code=""):
    now = _window()
    for window in (now, now - 1):
        digest = _digest(session, window)
        if token and hmac.compare_digest(token, digest[:16]):
            return True
        if code and hmac.compare_digest(code, f"{int(digest[16:28], 16) % 1_000_000:06d}"):
            return True
    return False


# --- Helpers ------------------------------------------------------------------------------------


def registered_students(offering):
    return User.objects.filter(enrollments__offering=offering, enrollments__status=REGISTERED).order_by("university_id")


def ensure_lecturer(user, offering):
    if offering.lecturer_id != user.id and not user.is_super_admin:
        raise PermissionDenied("Only the course lecturer can take attendance for this course.")


# --- Session lifecycle --------------------------------------------------------------------------


def open_session(session, by):
    ensure_lecturer(by, session.offering)
    if session.status != AttendanceSession.Status.SCHEDULED:
        raise ValidationError("This session has already been started.")
    if session.date != timezone.localdate():
        raise ValidationError("Attendance can only be started on the day of the class. Mark past classes by hand.")
    session.status = AttendanceSession.Status.OPEN
    session.opened_at = timezone.now()
    session.save(update_fields=["status", "opened_at"])
    return session


@transaction.atomic
def close_session(session, by):
    """Close check-in; every registered student without a record is marked absent."""
    ensure_lecturer(by, session.offering)
    session = AttendanceSession.objects.select_for_update().get(pk=session.pk)
    if session.status == AttendanceSession.Status.CLOSED:
        raise ValidationError("This session is already closed.")
    session.status = AttendanceSession.Status.CLOSED
    session.closed_at = timezone.now()
    if not session.opened_at:  # closed without being opened: attendance marked by hand only
        session.opened_at = session.closed_at
    session.save(update_fields=["status", "closed_at", "opened_at"])

    marked = set(session.records.values_list("student_id", flat=True))
    absentees = [s for s in registered_students(session.offering) if s.pk not in marked]
    AttendanceRecord.objects.bulk_create(
        AttendanceRecord(session=session, student=s, status=Status.ABSENT, method=Method.SYSTEM, marked_by=by)
        for s in absentees
    )
    course = session.offering.course.code
    notify(
        absentees,
        f"You were marked absent for {course}",
        f"{course} on {session.date:%A %d %B}. If this is wrong, speak to your lecturer.",
        link="/portal/attendance",
        category=Notification.Category.ACADEMIC,
    )
    _warn_low_attendance(session.offering, absentees)
    return session


def _warn_low_attendance(offering, students):
    """Tell students (in-app and by email) when they fall below the minimum attendance."""
    minimum = settings.ATTENDANCE_MIN_PERCENT
    stats = offering_student_stats(offering, students=students)
    at_risk = [s for s in students if (stats[s.pk]["percent"] or 0) < minimum]
    if at_risk:
        notify(
            at_risk,
            f"Attendance warning: {offering.course.code} is below {minimum}%",
            f"Students need at least {minimum}% attendance to sit the {offering.course.code} examination.",
            link="/portal/attendance",
            category=Notification.Category.ACADEMIC,
            email=True,
        )


# --- Student check-in ---------------------------------------------------------------------------


def check_in(student, session, *, token="", code="", device_id="", ip_address=None):
    """A student's self check-in by QR (token) or typed code, with duplicate safeguards."""
    if session.status != AttendanceSession.Status.OPEN:
        raise ValidationError("Attendance for this class isn't open.")
    if not session.is_accepting_checkins:
        raise ValidationError("Check-in for this class has closed. Speak to your lecturer.")
    if not code_is_valid(session, token=token, code=code):
        raise ValidationError("That code has expired or is wrong. Scan the QR code again or enter the new code.")
    if not Enrollment.objects.filter(student=student, offering=session.offering, status=REGISTERED).exists():
        raise ValidationError(f"You aren't registered for {session.offering.course.code}.")

    existing = AttendanceRecord.objects.filter(session=session, student=student).first()
    if existing:
        return existing, False

    late = timezone.now() > session.opened_at + timedelta(minutes=session.late_after_minutes)
    record = AttendanceRecord(
        session=session,
        student=student,
        status=Status.LATE if late else Status.PRESENT,
        method=Method.QR if token else Method.CODE,
        marked_by=student,
        device_id=device_id[:64],
        ip_address=ip_address,
    )
    # One phone checking in several students is the classic proxy-attendance pattern.
    if device_id and session.records.filter(device_id=device_id[:64]).exclude(student=student).exists():
        record.flagged = True
        record.flag_reason = "This device already checked in another student for this class."
    try:
        with transaction.atomic():
            record.save()
    except IntegrityError:  # two simultaneous scans by the same student
        return AttendanceRecord.objects.get(session=session, student=student), False
    return record, True


# --- Lecturer marking and corrections -----------------------------------------------------------


def mark(session, student, status, by):
    """Lecturer marks a student directly. Allowed until the session is closed."""
    ensure_lecturer(by, session.offering)
    if session.status == AttendanceSession.Status.CLOSED:
        raise ValidationError("This session is closed. Submit a correction request instead.")
    if not Enrollment.objects.filter(student=student, offering=session.offering, status=REGISTERED).exists():
        raise ValidationError(f"{student} isn't registered for this course.")
    record, _ = AttendanceRecord.objects.update_or_create(
        session=session,
        student=student,
        defaults={
            "status": status,
            "method": Method.LECTURER,
            "marked_by": by,
            "marked_at": timezone.now(),
            "flagged": False,
            "flag_reason": "",
        },
    )
    return record


def correction_approvers(offering):
    department = offering.course.department
    candidates = User.objects.filter(is_active=True).exclude(pk=offering.lecturer_id)
    return [
        u
        for u in candidates.filter(Q(role=User.Role.ADMIN) | Q(assignments__isnull=False)).distinct()
        if u.has_permission("attendance.approve")
        and u.can_act_on_department("attendance.approve", department.pk, department.faculty_id)
    ]


def request_correction(record, to_status, reason, by):
    session = record.session
    ensure_lecturer(by, session.offering)
    if session.status != AttendanceSession.Status.CLOSED:
        raise ValidationError("The session is still open: mark attendance directly.")
    if record.status == to_status:
        raise ValidationError(f"The student is already marked {record.get_status_display().lower()}.")
    if record.corrections.filter(status=AttendanceCorrection.Status.PENDING).exists():
        raise ValidationError("A correction for this student is already awaiting approval.")
    correction = AttendanceCorrection.objects.create(
        record=record,
        from_status=record.status,
        to_status=to_status,
        reason=reason,
        requested_by=by,
    )
    notify(
        correction_approvers(session.offering),
        f"Attendance correction for {session.offering.course.code}",
        f"{by} asks to change {record.student} from {record.get_status_display()} to "
        f"{Status(to_status).label} for {session.date:%d %b}: {reason}",
        link="/portal/manage/attendance?tab=corrections",
        category=Notification.Category.ACADEMIC,
    )
    return correction


@transaction.atomic
def decide_correction(correction, approve, note, by):
    correction = (
        AttendanceCorrection.objects.select_for_update()
        .select_related("record__session__offering__course__department", "record__student")
        .get(pk=correction.pk)
    )
    if correction.status != AttendanceCorrection.Status.PENDING:
        raise ValidationError(f"This correction has already been {correction.get_status_display().lower()}.")
    department = correction.record.session.offering.course.department
    if not by.can_act_on_department("attendance.approve", department.pk, department.faculty_id):
        raise PermissionDenied("You can't approve attendance corrections for this department.")
    if correction.requested_by_id == by.pk:
        raise PermissionDenied("You can't approve your own correction request.")

    correction.status = AttendanceCorrection.Status.APPROVED if approve else AttendanceCorrection.Status.REJECTED
    correction.decided_by, correction.decided_at, correction.decision_note = by, timezone.now(), note
    correction.save()
    record = correction.record
    if approve:
        record.status, record.method, record.marked_by = correction.to_status, Method.CORRECTION, by
        record.flagged, record.flag_reason = False, ""
        record.save(update_fields=["status", "method", "marked_by", "flagged", "flag_reason"])
    if correction.requested_by:
        verdict = "approved" if approve else "rejected"
        notify(
            [correction.requested_by],
            f"Attendance correction {verdict}",
            f"{record.student} on {record.session.date:%d %b}: {note}".strip(": "),
            link=f"/portal/attendance/sessions/{record.session_id}",
            category=Notification.Category.ACADEMIC,
        )
    return correction


# --- Statistics ---------------------------------------------------------------------------------


def _percent(attended, held):
    return round(attended * 100 / held, 1) if held else None


def offering_student_stats(offering, students=None):
    """{student_id: {held, attended, present, late, excused, absent, percent}} over closed sessions."""
    held = offering.attendance_sessions.filter(status=AttendanceSession.Status.CLOSED).count()
    students = list(students) if students is not None else list(registered_students(offering))
    counts = defaultdict(lambda: defaultdict(int))
    rows = (
        AttendanceRecord.objects.filter(session__offering=offering, session__status=AttendanceSession.Status.CLOSED)
        .values("student_id", "status")
        .annotate(n=Count("id"))
    )
    for row in rows:
        counts[row["student_id"]][row["status"]] = row["n"]
    stats = {}
    for s in students:
        c = counts[s.pk]
        attended = c[Status.PRESENT] + c[Status.LATE] + c[Status.EXCUSED]
        stats[s.pk] = {
            "held": held,
            "attended": attended,
            "present": c[Status.PRESENT],
            "late": c[Status.LATE],
            "excused": c[Status.EXCUSED],
            "absent": c[Status.ABSENT],
            "percent": _percent(attended, held),
        }
    return stats


def report_rows(records):
    """Aggregate closed-session records into one row per (student, course offering)."""
    rows = (
        records.filter(session__status=AttendanceSession.Status.CLOSED)
        .values(
            "student_id",
            "student__first_name",
            "student__last_name",
            "student__title",
            "student__university_id",
            "session__offering_id",
            "session__offering__course__code",
            "session__offering__course__title",
            "session__offering__course__department__name",
            "session__offering__semester_id",
        )
        .annotate(
            held=Count("id"),
            present=Count("id", filter=Q(status=Status.PRESENT)),
            late=Count("id", filter=Q(status=Status.LATE)),
            excused=Count("id", filter=Q(status=Status.EXCUSED)),
            absent=Count("id", filter=Q(status=Status.ABSENT)),
        )
        .order_by("session__offering__course__code", "student__university_id")
    )
    minimum = settings.ATTENDANCE_MIN_PERCENT
    out = []
    for r in rows:
        attended = r["present"] + r["late"] + r["excused"]
        percent = _percent(attended, r["held"])
        out.append(
            {
                "student_id": r["student_id"],
                "student_name": " ".join(
                    p for p in (r["student__title"], r["student__first_name"], r["student__last_name"]) if p
                ),
                "matric_number": r["student__university_id"],
                "offering_id": r["session__offering_id"],
                "course_code": r["session__offering__course__code"],
                "course_title": r["session__offering__course__title"],
                "department": r["session__offering__course__department__name"],
                "held": r["held"],
                "attended": attended,
                "present": r["present"],
                "late": r["late"],
                "excused": r["excused"],
                "absent": r["absent"],
                "percent": percent,
                "at_risk": percent is not None and percent < minimum,
            }
        )
    return out


def student_attendance(student):
    """A student's attendance per course this semester, with full history."""
    offerings = CourseOffering.objects.filter(
        enrollments__student=student,
        enrollments__status=Enrollment.Status.REGISTERED,
        semester__is_current=True,
    ).select_related("course")
    minimum = settings.ATTENDANCE_MIN_PERCENT
    courses = []
    for offering in offerings:
        stats = offering_student_stats(offering, [student])[student.pk]
        history = (
            AttendanceRecord.objects.filter(student=student, session__offering=offering)
            .select_related("session")
            .order_by("-session__date", "-session__start_time")
        )
        courses.append(
            {
                "offering": offering.pk,
                "course_code": offering.course.code,
                "course_title": offering.course.title,
                **stats,
                "at_risk": stats["percent"] is not None and stats["percent"] < minimum,
                "history": [
                    {
                        "date": r.session.date,
                        "start_time": r.session.start_time,
                        "topic": r.session.topic,
                        "status": r.status,
                        "status_label": r.get_status_display(),
                        "method": r.get_method_display(),
                        "session_open": r.session.status != AttendanceSession.Status.CLOSED,
                    }
                    for r in history
                ],
            }
        )
    held = sum(c["held"] for c in courses)
    attended = sum(c["attended"] for c in courses)
    return {
        "minimum_percent": minimum,
        "overall_percent": round(attended * 100 / held, 1) if held else None,
        "courses": sorted(courses, key=lambda c: c["course_code"]),
    }
