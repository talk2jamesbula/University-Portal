"""Course registration and results: the academic rules, kept out of views so they're easy to test."""

from collections import defaultdict

from django.conf import settings
from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.accounts.models import StudentProfile
from apps.finance.services import assess_semester_fees

from .grading import academic_standing, degree_class, weighted_average
from .models import CourseOffering, Enrollment, ProgrammeCourse, Semester

REGISTERED = Enrollment.Status.REGISTERED
PUBLISHED = Enrollment.ResultStatus.PUBLISHED
CAN_REGISTER = (StudentProfile.Status.ACTIVE, StudentProfile.Status.PROBATION)


def current_semester():
    return Semester.objects.filter(is_current=True).first()


def times_overlap(a, b):
    if not (a.start_time and a.end_time and b.start_time and b.end_time):
        return False
    if not set(a.day_list) & set(b.day_list):
        return False
    return a.start_time < b.end_time and b.start_time < a.end_time


# --- What a student may register ---------------------------------------------------------------


def _course_history(student):
    """{course_id: "passed" | "failed"} from the student's published results."""
    history = {}
    published = Enrollment.objects.filter(student=student, result_status=PUBLISHED).select_related("offering")
    for e in published:
        passed = (e.grade_points or 0) > 0
        if passed or history.get(e.offering.course_id) != "passed":
            history[e.offering.course_id] = "passed" if passed else "failed"
    return history


def available_offerings(student, semester):
    """Offerings the student can register for this semester.

    Returns [(offering, is_compulsory, is_carryover)], carry-overs and compulsory courses first.
    Courses already passed are left out; failed ones come back as carry-overs.
    """
    profile = student.student_profile
    curriculum = {
        pc.course_id: pc.is_compulsory
        for pc in ProgrammeCourse.objects.filter(
            programme=profile.programme,
            course__level__lte=profile.level,
            course__semester_number=semester.number,
        )
    }
    history = _course_history(student)
    offerings = CourseOffering.objects.filter(semester=semester, course_id__in=curriculum).select_related(
        "course__department", "lecturer"
    )
    rows = [
        (offering, curriculum[offering.course_id], history.get(offering.course_id) == "failed")
        for offering in offerings
        if history.get(offering.course_id) != "passed"
    ]
    rows.sort(key=lambda r: (not r[2], not r[1], r[0].course.level, r[0].course.code))
    return rows


def registration_summary(student, semester):
    registered = list(
        Enrollment.objects.filter(student=student, offering__semester=semester, status=REGISTERED)
        .select_related("offering__course", "offering__lecturer")
        .order_by("offering__course__code")
    )
    units = sum(e.offering.course.units for e in registered)
    if not registered:
        state = "not_started"
    elif units < settings.MIN_UNITS_PER_SEMESTER:
        state = "incomplete"
    else:
        state = "complete"
    return {
        "registered": registered,
        "units": units,
        "min_units": settings.MIN_UNITS_PER_SEMESTER,
        "max_units": settings.MAX_UNITS_PER_SEMESTER,
        "state": state,
    }


# --- Registering and dropping ------------------------------------------------------------------


def _check_can_register(student, semester):
    profile = getattr(student, "student_profile", None)
    if profile is None:
        raise ValidationError("Your student record isn't set up yet. Please contact the Registry.")
    if profile.status not in CAN_REGISTER:
        status = profile.get_status_display().lower()
        raise ValidationError(f"Your studentship is {status}; you can't register courses.")
    if not semester.registration_open:
        raise ValidationError(f"Course registration for {semester} is closed.")


@transaction.atomic
def register_course(student, offering):
    # Lock the offering so two students can't both take the last seat.
    offering = CourseOffering.objects.select_for_update().select_related("course", "semester").get(pk=offering.pk)
    semester = offering.semester
    _check_can_register(student, semester)

    eligible = {o.pk: carryover for o, _, carryover in available_offerings(student, semester)}
    if offering.pk not in eligible:
        raise ValidationError(f"{offering.course.code} isn't available to you this semester.")

    summary = registration_summary(student, semester)
    if any(e.offering_id == offering.pk for e in summary["registered"]):
        raise ValidationError(f"You're already registered for {offering.course.code}.")
    if offering.enrollments.filter(status=REGISTERED).count() >= offering.capacity:
        raise ValidationError(f"{offering.course.code} is full.")
    if summary["units"] + offering.course.units > summary["max_units"]:
        raise ValidationError(f"Registering would exceed the {summary['max_units']}-unit limit for {semester}.")
    for e in summary["registered"]:
        if times_overlap(e.offering, offering):
            raise ValidationError(f"{offering.course.code} clashes with {e.offering.course.code} on your timetable.")

    enrollment, created = Enrollment.objects.get_or_create(
        student=student, offering=offering, defaults={"is_carryover": eligible[offering.pk]}
    )
    if not created:  # re-registering after a drop
        enrollment.status = REGISTERED
        enrollment.save(update_fields=["status", "updated_at"])
    assess_semester_fees(student, semester)
    return enrollment


@transaction.atomic
def drop_course(student, offering):
    try:
        enrollment = Enrollment.objects.select_related("offering__semester", "offering__course").get(
            student=student, offering=offering, status=REGISTERED
        )
    except Enrollment.DoesNotExist:
        raise ValidationError("You aren't registered for this course.") from None
    semester = enrollment.offering.semester
    if not semester.registration_open:
        raise ValidationError(f"The add/drop period for {semester} has ended.")
    if enrollment.result_status != Enrollment.ResultStatus.PENDING:
        raise ValidationError(f"Scores have already been entered for {enrollment.offering.course.code}.")
    enrollment.status = Enrollment.Status.DROPPED
    enrollment.save(update_fields=["status", "updated_at"])
    assess_semester_fees(student, semester)
    return enrollment


# --- Results ------------------------------------------------------------------------------------


def _result_pairs(enrollments):
    return [(e.offering.course.units, e.grade_points) for e in enrollments if e.grade_points is not None]


def student_results(student):
    """Published results by semester (newest first) with GPA, plus CGPA and standing."""
    published = list(
        Enrollment.objects.filter(student=student, result_status=PUBLISHED)
        .exclude(status=Enrollment.Status.DROPPED)
        .select_related("offering__course", "offering__semester")
        .order_by("-offering__semester__start_date", "offering__course__code")
    )
    by_semester = defaultdict(list)
    for e in published:
        by_semester[e.offering.semester].append(e)

    semesters = []
    for semester, enrollments in by_semester.items():
        gpa, units, passed = weighted_average(_result_pairs(enrollments))
        semesters.append(
            {
                "semester": semester,
                "enrollments": enrollments,
                "gpa": gpa,
                "units_taken": units,
                "units_passed": passed,
            }
        )
    cgpa, total_units, total_passed = weighted_average(_result_pairs(published))
    return {
        "semesters": semesters,
        "cgpa": cgpa,
        "units_taken": total_units,
        "units_passed": total_passed,
        "standing": academic_standing(cgpa),
        "degree_class": degree_class(cgpa),
    }
