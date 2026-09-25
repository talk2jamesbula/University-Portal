"""The admission workflow.

    draft ─submit→ submitted ─start review→ under review ─documents verified→ screening
    screening → approved | waitlisted | rejected        (under review → rejected, e.g. forged documents)
    waitlisted → approved | rejected
    approved ─admission letter issued→ admitted ─applicant accepts→ accepted

Every step is recorded on the application's timeline (ApplicationEvent) and in the audit log,
and the applicant is notified in the portal and by email whenever their status changes.
"""

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.core.models import Notification
from apps.core.services import audit, notify

from .models import AdmissionCycle, Application, ApplicationDocument

S = Application.Status

# Officer transitions. The applicant's own steps (submit, accept) are checked separately.
TRANSITIONS = {
    S.SUBMITTED: {S.UNDER_REVIEW},
    S.UNDER_REVIEW: {S.SCREENING, S.REJECTED},
    S.SCREENING: {S.APPROVED, S.WAITLISTED, S.REJECTED},
    S.WAITLISTED: {S.APPROVED, S.REJECTED},
    S.APPROVED: {S.ADMITTED},
}

# What the applicant is told when their application reaches each status.
MESSAGES = {
    S.SUBMITTED: (
        "Application submitted",
        "We have received your application {number}. We'll let you know as it moves through review.",
    ),
    S.UNDER_REVIEW: (
        "Your application is under review",
        "The Admissions Office has started reviewing application {number} and verifying your documents.",
    ),
    S.SCREENING: (
        "You have been shortlisted for screening",
        "Your documents for application {number} have been verified and you have moved to the screening stage.",
    ),
    S.APPROVED: (
        "Your application has been approved",
        "Application {number} has been approved. Your admission letter will be issued shortly.",
    ),
    S.WAITLISTED: (
        "You have been placed on the waiting list",
        "Application {number} is on the waiting list. We will contact you if a place becomes available.",
    ),
    S.REJECTED: (
        "Update on your application",
        "We are sorry, but application {number} was not successful.",
    ),
    S.ADMITTED: (
        "Offer of provisional admission",
        "Congratulations! You have been offered provisional admission. Download your admission letter "
        "and accept the offer in the portal.",
    ),
    S.ACCEPTED: (
        "Admission accepted",
        "You have accepted your offer of admission. Welcome to the University!",
    ),
}

# --- O-Level results ----------------------------------------------------------------------------

GRADES = ["A1", "B2", "B3", "C4", "C5", "C6", "D7", "E8", "F9"]
CREDITS = set(GRADES[:6])
EXAMS = ["WAEC", "NECO", "NABTEB", "GCE"]
MIN_CREDITS = 5
MAX_SITTINGS = 2


def olevel_problems(results):
    """Why O-Level results don't meet the minimum requirement (an empty list if they do)."""
    credits = {r["subject"].strip().lower() for r in results if r.get("grade") in CREDITS}
    problems = []
    if len(credits) < MIN_CREDITS:
        problems.append(f"At least {MIN_CREDITS} credit passes (A1–C6) are required; you have {len(credits)}.")
    for subject in ("English Language", "Mathematics"):
        if subject.lower() not in credits:
            problems.append(f"A credit pass in {subject} is required.")
    sittings = {(r.get("exam"), r.get("year")) for r in results}
    if len(sittings) > MAX_SITTINGS:
        problems.append(f"Results may come from at most {MAX_SITTINGS} sittings.")
    return problems


# --- Completeness -------------------------------------------------------------------------------

PERSONAL_FIELDS = {
    "gender": "gender",
    "date_of_birth": "date of birth",
    "state_of_origin": "state of origin",
    "lga": "LGA",
    "address": "address",
    "phone": "phone number",
    "next_of_kin_name": "next of kin",
    "next_of_kin_phone": "next of kin's phone number",
}


def checklist(application):
    """Each section of the application and whether it's complete, for the applicant's progress view."""
    app = application
    missing_personal = [label for field, label in PERSONAL_FIELDS.items() if not getattr(app, field)]
    academic = []
    if app.entry_mode == Application.EntryMode.UTME:
        if not app.jamb_reg_number:
            academic.append("Enter your JAMB registration number.")
        if app.utme_score is None:
            academic.append("Enter your UTME score.")
        elif app.utme_score < app.cycle.min_utme_score:
            academic.append(f"The minimum UTME score for this admission is {app.cycle.min_utme_score}.")
    elif not (app.previous_institution and app.previous_qualification):
        academic.append("Enter your previous institution and qualification.")
    academic += olevel_problems(app.olevel_results)

    uploaded = {d.kind: d for d in app.documents.all()}
    missing_docs = [ApplicationDocument.Kind(k).label for k in ApplicationDocument.REQUIRED if k not in uploaded]
    rejected_docs = [d.get_kind_display() for d in uploaded.values() if d.status == ApplicationDocument.Status.REJECTED]

    programme = []
    if not app.programme:
        programme.append("Choose your first-choice programme.")
    elif app.second_choice_id == app.programme_id:
        programme.append("Your second choice must be a different programme.")

    def item(key, label, problems):
        return {"key": key, "label": label, "done": not problems, "problems": problems}

    return [
        item("personal", "Personal details", [f"Add your {', '.join(missing_personal)}."] if missing_personal else []),
        item("programme", "Programme choice", programme),
        item("academic", "Academic record", academic),
        item(
            "documents",
            "Documents",
            ([f"Upload: {', '.join(missing_docs)}."] if missing_docs else [])
            + ([f"Replace rejected: {', '.join(rejected_docs)}."] if rejected_docs else []),
        ),
        item("payment", "Application fee", [] if app.fee_paid else ["Pay the application fee."]),
    ]


# --- Timeline -----------------------------------------------------------------------------------


def record(application, action, by=None, note="", *, public=False, from_status="", to_status=""):
    return application.events.create(
        action=action, actor=by, note=note[:300], public=public, from_status=from_status, to_status=to_status
    )


def _move(application, to_status, by, request=None, note="", *, audit_summary=""):
    """Change status: timeline, audit log, and a notification (with email) to the applicant."""
    from_status = application.status
    application.status = to_status
    application.save()
    record(application, "status", by, note, public=True, from_status=from_status, to_status=to_status)
    audit(
        request,
        f"admissions.{to_status}",
        application,
        audit_summary or f"{application.number}: {S(from_status).label} → {S(to_status).label}",
        actor=by,
    )
    title, body = MESSAGES[to_status]
    body = body.format(number=application.number)
    if note and to_status in (S.REJECTED, S.WAITLISTED):
        body += f"\n\nNote from the Admissions Office: {note}"
    notify(
        [application.applicant],
        title,
        body,
        link="/portal/application",
        category=Notification.Category.ADMISSION,
        email=True,
    )


def _require(application, *statuses, action):
    if application.status not in statuses:
        raise ValidationError(f"You can't {action} an application that is {application.get_status_display().lower()}.")


def _locked(application):
    """Re-read the application with a row lock, so two officers can't act on it at once."""
    return Application.objects.select_for_update().select_related("cycle", "applicant").get(pk=application.pk)


# --- Applicant ----------------------------------------------------------------------------------


@transaction.atomic
def start_application(applicant, cycle):
    if cycle is None or not cycle.is_open:
        raise ValidationError("Applications are not open at the moment.")
    if Application.objects.filter(cycle=cycle, applicant=applicant).exists():
        raise ValidationError("You have already started an application for this admission.")
    application = Application.objects.create(cycle=cycle, applicant=applicant, phone=applicant.phone)
    application.number = f"BU/APP/{cycle.code}/{application.pk:05d}"
    application.save(update_fields=["number"])
    record(application, "created", applicant, "Application started", public=True, to_status=S.DRAFT)
    return application


def can_replace_document(application, kind):
    """Drafts can change any document; after submission only rejected documents can be replaced."""
    if application.status == S.DRAFT:
        return True
    if application.status in (S.SUBMITTED, S.UNDER_REVIEW):
        return application.documents.filter(kind=kind, status=ApplicationDocument.Status.REJECTED).exists()
    return False


@transaction.atomic
def save_document(application, kind, upload, content_type, by):
    application = _locked(application)
    if not can_replace_document(application, kind):
        raise ValidationError(
            "Documents can't be changed after you submit, unless the Admissions Office asks you to replace one."
        )
    old = application.documents.filter(kind=kind).first()
    old_file = old.file.name if old else None
    if old:
        old.delete()
    document = ApplicationDocument.objects.create(
        application=application,
        kind=kind,
        file=upload,
        original_filename=upload.name[:200],
        content_type=content_type,
        size=upload.size,
    )
    if old_file:
        transaction.on_commit(lambda: document.file.storage.delete(old_file))
    if application.status != S.DRAFT:
        record(application, "document_replaced", by, document.get_kind_display(), public=True)
        if application.reviewer:
            notify(
                [application.reviewer],
                f"New document for {application.number}",
                f"{application.applicant} replaced their {document.get_kind_display().lower()}.",
                link=f"/portal/manage/admissions/{application.pk}",
                category=Notification.Category.ADMISSION,
            )
    return document


def delete_document(document):
    if document.application.status != S.DRAFT:
        raise ValidationError("Documents can't be removed after you submit.")
    name = document.file.name
    document.delete()
    transaction.on_commit(lambda: document.file.storage.delete(name))


@transaction.atomic
def submit(application, by, request=None):
    application = _locked(application)
    _require(application, S.DRAFT, action="submit")
    if not application.cycle.is_open:
        raise ValidationError(
            f"Applications for {application.cycle.session} closed on {application.cycle.closes_on:%d %B %Y}."
        )
    problems = [p for section in checklist(application) for p in section["problems"]]
    if problems:
        raise ValidationError({"detail": "Your application is not complete.", "problems": problems})
    application.submitted_at = timezone.now()
    _move(application, S.SUBMITTED, by, request)
    return application


@transaction.atomic
def accept_offer(application, by, request=None):
    application = _locked(application)
    _require(application, S.ADMITTED, action="accept the offer on")
    deadline = application.cycle.acceptance_deadline
    if deadline and timezone.localdate() > deadline:
        raise ValidationError(
            f"The deadline to accept this offer was {deadline:%d %B %Y}. Contact the Admissions Office."
        )
    application.accepted_at = timezone.now()
    _move(application, S.ACCEPTED, by, request)
    return application


# --- Admissions Office --------------------------------------------------------------------------


def _officer_move(application, to_status, by, request, note="", **kw):
    if to_status not in TRANSITIONS.get(application.status, set()):
        raise ValidationError(
            f"An application that is {application.get_status_display().lower()} can't be moved to "
            f"{S(to_status).label.lower()}."
        )
    _move(application, to_status, by, request, note, **kw)


@transaction.atomic
def start_review(application, by, request=None):
    application = _locked(application)
    application.reviewer = by
    _officer_move(application, S.UNDER_REVIEW, by, request)
    return application


@transaction.atomic
def review_document(document, verified, note, by, request=None):
    application = _locked(document.application)
    _require(application, S.SUBMITTED, S.UNDER_REVIEW, action="verify documents on")
    if not verified and not note:
        raise ValidationError({"note": "Tell the applicant what is wrong with the document."})
    if application.status == S.SUBMITTED:  # verifying a document starts the review
        application.reviewer = by
        _officer_move(application, S.UNDER_REVIEW, by, request)
    document.status = ApplicationDocument.Status.VERIFIED if verified else ApplicationDocument.Status.REJECTED
    document.review_note, document.reviewed_by, document.reviewed_at = note, by, timezone.now()
    document.save(update_fields=["status", "review_note", "reviewed_by", "reviewed_at"])
    verb = "verified" if verified else "rejected"
    record(
        application,
        f"document_{verb}",
        by,
        f"{document.get_kind_display()}{': ' + note if note else ''}",
        public=not verified,
    )
    audit(
        request,
        f"admissions.document_{verb}",
        document,
        f"{application.number}: {verb} {document.get_kind_display()}",
        actor=by,
    )
    if not verified:
        notify(
            [application.applicant],
            "Please replace a document",
            f"Your {document.get_kind_display().lower()} could not be verified: {note}\n\n"
            "Upload a clearer or correct copy in the portal.",
            link="/portal/application?step=documents",
            category=Notification.Category.ADMISSION,
            email=True,
        )
    return document


@transaction.atomic
def move_to_screening(application, by, request=None):
    application = _locked(application)
    documents = {d.kind: d for d in application.documents.all()}
    unverified = [
        ApplicationDocument.Kind(k).label
        for k in ApplicationDocument.REQUIRED
        if k not in documents or documents[k].status != ApplicationDocument.Status.VERIFIED
    ]
    if unverified:
        raise ValidationError(f"Verify these documents first: {', '.join(unverified)}.")
    _officer_move(application, S.SCREENING, by, request)
    return application


@transaction.atomic
def record_screening(application, score, remarks, by, request=None):
    application = _locked(application)
    _require(application, S.SCREENING, action="record a screening result for")
    previous = application.screening_score
    application.screening_score, application.screening_remarks = score, remarks
    application.screened_by, application.screened_at = by, timezone.now()
    application.save()
    change = f"{previous} → {score}" if previous is not None else f"{score}"
    record(application, "screening", by, f"Screening score {change}. {remarks}".strip())
    audit(request, "admissions.screening", application, f"{application.number}: screening score {change}", actor=by)
    return application


DECISIONS = {"approve": S.APPROVED, "waitlist": S.WAITLISTED, "reject": S.REJECTED}


@transaction.atomic
def decide(application, decision, note, by, request=None, programme=None):
    application = _locked(application)
    to_status = DECISIONS[decision]
    if to_status in (S.APPROVED, S.WAITLISTED) and application.screening_score is None:
        raise ValidationError("Record the screening result before deciding.")
    if to_status in (S.REJECTED, S.WAITLISTED) and not note:
        raise ValidationError({"note": "Give a reason; the applicant will see it."})
    if to_status == S.APPROVED:
        programme = programme or application.programme
        if programme not in (application.programme, application.second_choice):
            raise ValidationError({"programme": "Offer the applicant their first or second choice."})
        if not programme.is_active:
            raise ValidationError({"programme": f"{programme} is not currently admitting students."})
        application.admitted_programme = programme
    application.decision_note, application.decided_by, application.decided_at = note, by, timezone.now()
    _officer_move(application, to_status, by, request, note)
    return application


@transaction.atomic
def issue_letter(application, by, request=None):
    application = _locked(application)
    application.letter_number = f"BU/ADM/{application.cycle.code}/{application.pk:05d}"
    application.letter_issued_at = timezone.now()
    _officer_move(
        application,
        S.ADMITTED,
        by,
        request,
        f"Admission letter {application.letter_number}",
        audit_summary=f"{application.number}: issued admission letter {application.letter_number}",
    )
    return application


def current_cycle():
    return AdmissionCycle.current()
