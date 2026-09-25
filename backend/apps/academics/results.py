"""The results workflow: the lecturer enters scores and submits; the HOD, the Dean and the Exams Office
approve in turn, and publication makes the results visible to students.

A course's results move together: draft → submitted → approved by HOD → approved by Dean → published.
Any reviewer can return them to the lecturer (back to draft) with a note. Nobody approves their own course.
"""

from collections import defaultdict

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.core.models import Notification
from apps.core.services import notify

from .models import CourseOffering, Enrollment, ResultAction

User = get_user_model()
R = Enrollment.ResultStatus
A = ResultAction.Action
REGISTERED = Enrollment.Status.REGISTERED

# Least to most advanced; a course's status is its least advanced student's.
ORDER = [R.PENDING, R.DRAFT, R.SUBMITTED, R.DEPARTMENT_APPROVED, R.FACULTY_APPROVED, R.PUBLISHED]
EDITABLE = (R.PENDING, R.DRAFT)

# status: (action, next status, permission needed to take it)
APPROVALS = {
    R.SUBMITTED: (A.APPROVE_DEPARTMENT, R.DEPARTMENT_APPROVED, "results.approve_department"),
    R.DEPARTMENT_APPROVED: (A.APPROVE_FACULTY, R.FACULTY_APPROVED, "results.approve_faculty"),
    R.FACULTY_APPROVED: (A.PUBLISH, R.PUBLISHED, "results.publish"),
}
REVIEW_PERMISSIONS = ("results.approve_department", "results.approve_faculty", "results.publish")


def registered(offering):
    return offering.enrollments.filter(status=REGISTERED)


def overall_status(statuses):
    """A course's results status: the least advanced of its students' (None if nobody is registered)."""
    statuses = list(statuses)
    return min(statuses, key=ORDER.index) if statuses else None


def offering_status(offering):
    return overall_status(registered(offering).values_list("result_status", flat=True))


def is_lecturer(user, offering):
    return offering.lecturer_id == user.id or user.is_super_admin


def _can_review(user, code, offering):
    department = offering.course.department
    return user.has_permission(code) and user.can_act_on_department(code, department.pk, department.faculty_id)


def can_view(user, offering):
    return is_lecturer(user, offering) or any(_can_review(user, code, offering) for code in REVIEW_PERMISSIONS)


def allowed_actions(user, offering, status):
    """What the user may do to the course's results now: edit, submit, approve (by step name) or return."""
    actions = []
    if status in EDITABLE and is_lecturer(user, offering):
        actions += ["edit", "submit"]
    step = APPROVALS.get(status)
    reviewing_own = offering.lecturer_id == user.id and not user.is_super_admin
    if step and not reviewing_own and _can_review(user, step[2], offering):
        actions += ["approve", "return"]
    return actions


def reviewers(offering, code):
    """Everyone who can take the step needing `code` for this course, except its lecturer."""
    department = offering.course.department
    candidates = User.objects.filter(is_active=True).exclude(pk=offering.lecturer_id)
    return [
        u
        for u in candidates.filter(Q(role=User.Role.ADMIN) | Q(assignments__isnull=False)).distinct()
        if u.has_permission(code) and u.can_act_on_department(code, department.pk, department.faculty_id)
    ]


def _locked(offering):
    return list(registered(offering).select_for_update().select_related("student"))


def _move(offering, enrollments, to_status, action, by, note):
    from_status = overall_status(e.result_status for e in enrollments)
    Enrollment.objects.filter(pk__in=[e.pk for e in enrollments]).update(
        result_status=to_status, updated_at=timezone.now()
    )
    return ResultAction.objects.create(
        offering=offering, action=action, from_status=from_status, to_status=to_status, note=note, by=by
    )


# --- Lecturer ------------------------------------------------------------------------------------


@transaction.atomic
def enter_scores(offering, rows, by):
    """rows: [{"enrollment": id, "ca_score": ..., "exam_score": ...}]. A score left out is unchanged;
    None clears it. Only allowed until the results are submitted."""
    if not is_lecturer(by, offering):
        raise PermissionDenied("Only the course lecturer can enter scores.")
    enrollments = {e.pk: e for e in _locked(offering)}
    changed = []
    for row in rows:
        enrollment = enrollments.get(row["enrollment"])
        if enrollment is None:
            raise ValidationError(f"Student record {row['enrollment']} isn't on this course's class list.")
        if enrollment.result_status not in EDITABLE:
            raise ValidationError(f"{enrollment.student}'s result has been submitted and can't be changed.")
        for field in ("ca_score", "exam_score"):
            if field in row:
                setattr(enrollment, field, row[field])
        enrollment.result_status, enrollment.updated_at = R.DRAFT, timezone.now()
        changed.append(enrollment)
    Enrollment.objects.bulk_update(changed, ["ca_score", "exam_score", "result_status", "updated_at"])
    return changed


@transaction.atomic
def submit(offering, by, note=""):
    if not is_lecturer(by, offering):
        raise PermissionDenied("Only the course lecturer can submit these results.")
    enrollments = _locked(offering)
    if not enrollments:
        raise ValidationError("No students are registered for this course.")
    if overall_status(e.result_status for e in enrollments) not in EDITABLE:
        raise ValidationError("These results have already been submitted.")
    missing = [e for e in enrollments if e.ca_score is None or e.exam_score is None]
    if missing:
        raise ValidationError(
            f"Enter the CA and examination scores for every student first ({len(missing)} still incomplete)."
        )
    action = _move(offering, enrollments, R.SUBMITTED, A.SUBMIT, by, note)
    code = offering.course.code
    notify(
        reviewers(offering, "results.approve_department"),
        f"{code} results are awaiting your approval",
        f"{by} submitted the {code} results for {offering.semester} ({len(enrollments)} students).",
        link=f"/portal/results/sheets/{offering.pk}",
        category=Notification.Category.RESULTS,
    )
    return action


# --- Reviewers -----------------------------------------------------------------------------------


def _check_reviewer(by, code, offering):
    if offering.lecturer_id == by.id and not by.is_super_admin:
        raise PermissionDenied("You can't approve or return the results of a course you teach.")
    if not _can_review(by, code, offering):
        raise PermissionDenied("You can't approve these results at this stage.")


@transaction.atomic
def approve(offering, by, note=""):
    enrollments = _locked(offering)
    status = overall_status(e.result_status for e in enrollments)
    if status not in APPROVALS:
        raise ValidationError("These results aren't awaiting approval.")
    step, to_status, code = APPROVALS[status]
    _check_reviewer(by, code, offering)
    action = _move(offering, enrollments, to_status, step, by, note)

    course = offering.course.code
    link = f"/portal/results/sheets/{offering.pk}"
    if to_status == R.DEPARTMENT_APPROVED:
        notify(
            reviewers(offering, "results.approve_faculty"),
            f"{course} results are awaiting your approval",
            f"Approved by the HOD ({by}).",
            link=link,
            category=Notification.Category.RESULTS,
        )
    elif to_status == R.FACULTY_APPROVED:
        notify(
            reviewers(offering, "results.publish"),
            f"{course} results are ready to publish",
            f"Approved by the Dean ({by}).",
            link=link,
            category=Notification.Category.RESULTS,
        )
    else:
        notify(
            [e.student for e in enrollments],
            f"Your {course} result has been published",
            f"{course} {offering.course.title}, {offering.semester}.",
            link="/portal/results",
            category=Notification.Category.RESULTS,
            email=True,
        )
        if offering.lecturer:
            notify(
                [offering.lecturer],
                f"{course} results have been published",
                link=link,
                category=Notification.Category.RESULTS,
            )
    return action


@transaction.atomic
def return_to_lecturer(offering, by, note):
    if not note.strip():
        raise ValidationError({"note": "Say what the lecturer needs to change."})
    enrollments = _locked(offering)
    status = overall_status(e.result_status for e in enrollments)
    if status not in APPROVALS:
        raise ValidationError("Only results awaiting approval can be returned.")
    _check_reviewer(by, APPROVALS[status][2], offering)
    action = _move(offering, enrollments, R.DRAFT, A.RETURN, by, note)
    if offering.lecturer:
        notify(
            [offering.lecturer],
            f"{offering.course.code} results were returned to you",
            f"{by}: {note}",
            link=f"/portal/results/sheets/{offering.pk}",
            category=Notification.Category.RESULTS,
            email=True,
        )
    return action


# --- Listing -------------------------------------------------------------------------------------


def visible_offerings(user, semester):
    """Offerings in the semester whose results the user may see: courses they teach, plus those
    in the departments or faculties where they review results."""
    qs = CourseOffering.objects.filter(semester=semester).select_related("course__department", "lecturer")
    if user.is_super_admin:
        return qs
    visible = Q(lecturer=user)
    for code in REVIEW_PERMISSIONS:
        if not user.has_permission(code):
            continue
        if user.permission_scope(code) is None:  # university-wide (e.g. the Exams Office)
            return qs
        visible |= user.scope_filter(code, "course__department")
    return qs.filter(visible)


def sheet_summaries(user, semester):
    """One row per visible course: status, progress of score entry, and what the user may do."""
    offerings = list(visible_offerings(user, semester).order_by("course__code"))
    enrollments = Enrollment.objects.filter(offering__in=offerings, status=REGISTERED).values(
        "offering_id", "result_status", "ca_score", "exam_score"
    )
    statuses, complete = defaultdict(list), defaultdict(int)
    for e in enrollments:
        statuses[e["offering_id"]].append(e["result_status"])
        complete[e["offering_id"]] += e["ca_score"] is not None and e["exam_score"] is not None
    rows = []
    for offering in offerings:
        status = overall_status(statuses[offering.pk])
        if status is None:
            continue  # nobody registered: nothing to approve
        rows.append(
            {
                "offering": offering.pk,
                "code": offering.course.code,
                "title": offering.course.title,
                "department": offering.course.department.name,
                "lecturer_name": offering.lecturer.get_full_name() if offering.lecturer else None,
                "students": len(statuses[offering.pk]),
                "complete": complete[offering.pk],
                "status": status,
                "status_label": R(status).label,
                "actions": allowed_actions(user, offering, status),
            }
        )
    return rows
