"""Examination rules: eligibility, seating, the timetable, exam cards, check-in and computer-based tests."""

import random
from collections import Counter, defaultdict
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal
from itertools import combinations

from django.conf import settings
from django.core import signing
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.academics import results
from apps.academics.grading import EXAM_MAX
from apps.academics.models import Enrollment
from apps.attendance.services import offering_student_stats, registered_students
from apps.core.models import Notification
from apps.core.services import notify
from apps.finance.services import account_summary

from .models import Answer, Attempt, AttemptEvent, Candidate, Choice, Exam, Question

EXAMS = Notification.Category.EXAMS


def local(dt):
    return timezone.localtime(dt)


# --- Eligibility ---------------------------------------------------------------------------------
#
# To sit a course's exam a student must be registered for it, have at least ATTENDANCE_MIN_PERCENT
# attendance in it (once any classes have been recorded) and, if EXAM_REQUIRE_FEES_CLEARED, have no
# overdue fees. The Exams Office can waive the attendance and fees rules for a student.


def overdue_fees(student):
    return account_summary(student)["overdue"]


def assess(percent, overdue, waived=False):
    """{eligible, reasons, waived} from a student's attendance percentage and overdue fees."""
    reasons = []
    minimum = settings.ATTENDANCE_MIN_PERCENT
    if percent is not None and percent < minimum:
        reasons.append(f"Attendance is {percent:g}%, below the {minimum}% required.")
    if settings.EXAM_REQUIRE_FEES_CLEARED and overdue > 0:
        reasons.append(f"School fees of ₦{overdue:,.2f} are overdue.")
    return {"eligible": waived or not reasons, "reasons": reasons, "waived": waived and bool(reasons)}


def is_registered(student, offering):
    return Enrollment.objects.filter(student=student, offering=offering, status=Enrollment.Status.REGISTERED).exists()


def eligibility(student, exam, *, overdue=None):
    if not is_registered(student, exam.offering):
        return {"eligible": False, "reasons": [f"Not registered for {exam.offering.course.code}."], "waived": False}
    percent = offering_student_stats(exam.offering, [student])[student.pk]["percent"]
    candidate = exam.candidates.filter(student=student).first()
    overdue = overdue_fees(student) if overdue is None else overdue
    return assess(percent, overdue, waived=bool(candidate and candidate.waived))


def roster(exam):
    """Every registered student with their seat, eligibility, check-in and (for CBT) attempt."""
    offering = exam.offering
    students = list(registered_students(offering).select_related("student_profile__programme"))
    stats = offering_student_stats(offering, students)
    candidates = {c.student_id: c for c in exam.candidates.select_related("venue")}
    attempts = {a.student_id: a for a in exam.attempts.all()}
    rows = []
    for student in students:
        candidate = candidates.get(student.pk)
        percent = stats[student.pk]["percent"]
        rows.append(
            {
                "student": student,
                "candidate": candidate,
                "attempt": attempts.get(student.pk),
                "attendance_percent": percent,
                **assess(percent, overdue_fees(student), waived=bool(candidate and candidate.waived)),
            }
        )
    return rows


@transaction.atomic
def set_waiver(exam, student, waived, reason, by):
    if not is_registered(student, exam.offering):
        raise ValidationError(f"{student} isn't registered for {exam.offering.course.code}.")
    if waived and not reason.strip():
        raise ValidationError({"reason": "Give the reason for the waiver."})
    candidate, _ = Candidate.objects.get_or_create(exam=exam, student=student)
    candidate.waived = waived
    candidate.waiver_reason = reason.strip() if waived else ""
    candidate.waived_by = by if waived else None
    candidate.save(update_fields=["waived", "waiver_reason", "waived_by"])
    if waived:
        notify(
            [student],
            f"You may sit the {exam.offering.course.code} examination",
            "The Examinations Office has granted you a waiver. Download your exam card again.",
            link="/portal/exams",
            category=EXAMS,
        )
    return candidate


# --- Seating -------------------------------------------------------------------------------------


def overlapping_exams(exam):
    return [e for e in Exam.objects.filter(date=exam.date).exclude(pk=exam.pk) if e.overlaps(exam)]


@transaction.atomic
def allocate_seats(exam):
    """Give every registered student without a seat one in the exam's venues.

    Seats already given out are kept (students may have printed their cards). Seats taken by other
    exams in the same hall at the same time are left alone. Students who dropped the course lose
    their place unless they were already checked in.
    """
    exam = Exam.objects.select_for_update().get(pk=exam.pk)
    venues = list(exam.venues.filter(is_active=True).order_by("name"))
    if not venues:
        raise ValidationError(f"Choose a venue for the {exam.offering.course.code} exam first.")
    students = list(registered_students(exam.offering))
    student_ids = {s.pk for s in students}
    exam.candidates.exclude(student_id__in=student_ids).filter(checked_in_at__isnull=True, waived=False).delete()
    exam.candidates.exclude(venue__in=venues).update(venue=None, seat_number=None)

    taken = defaultdict(set)  # venue id -> seat numbers in use at this time
    others = Candidate.objects.filter(exam__in=overlapping_exams(exam), venue__in=venues, seat_number__isnull=False)
    for venue_id, seat in [*others.values_list("venue_id", "seat_number")]:
        taken[venue_id].add(seat)
    candidates = {c.student_id: c for c in exam.candidates.all()}
    for c in candidates.values():
        if c.venue_id:
            taken[c.venue_id].add(c.seat_number)

    free = [(v, n) for v in venues for n in range(1, v.capacity + 1) if n not in taken[v.pk]]
    unseated = [s for s in students if not (candidates.get(s.pk) and candidates[s.pk].venue_id)]
    if len(unseated) > len(free):
        raise ValidationError(
            f"{exam.offering.course.code}: {len(unseated)} students need seats but the chosen venues have only "
            f"{len(free)} free at that time. Add another venue."
        )
    new, changed = [], []
    for student, (venue, seat) in zip(unseated, free, strict=False):
        candidate = candidates.get(student.pk)
        if candidate:
            candidate.venue, candidate.seat_number = venue, seat
            changed.append(candidate)
        else:
            new.append(Candidate(exam=exam, student=student, venue=venue, seat_number=seat))
    Candidate.objects.bulk_update(changed, ["venue", "seat_number"])
    Candidate.objects.bulk_create(new)
    return len(unseated)


# --- The timetable -------------------------------------------------------------------------------


def timetable_problems(semester):
    """Problems with a semester's exam timetable, most serious first: [{level, exams, message}]."""
    exams = list(
        Exam.objects.filter(offering__semester=semester)
        .select_related("offering__course")
        .prefetch_related("venues", "questions")
    )
    enrolled = defaultdict(set)
    for offering_id, student_id in Enrollment.objects.filter(
        offering__semester=semester, status=Enrollment.Status.REGISTERED
    ).values_list("offering_id", "student_id"):
        enrolled[offering_id].add(student_id)
    seated = Counter(Candidate.objects.filter(exam__in=exams, venue__isnull=False).values_list("exam_id", flat=True))

    problems = []
    for a, b in combinations(exams, 2):
        shared = enrolled[a.offering_id] & enrolled[b.offering_id]
        if shared and a.overlaps(b):
            problems.append(
                {
                    "level": "error",
                    "exams": [a.pk, b.pk],
                    "message": f"{a.offering.course.code} and {b.offering.course.code} overlap on "
                    f"{a.date:%a %d %b} and {len(shared)} student{'s' if len(shared) != 1 else ''} take both.",
                }
            )
    for exam in exams:
        code = exam.offering.course.code
        students = len(enrolled[exam.offering_id])
        venues = [v for v in exam.venues.all() if v.is_active]
        capacity = sum(v.capacity for v in venues)
        if not venues:
            problems.append({"level": "warning", "exams": [exam.pk], "message": f"{code} has no venue."})
        elif capacity < students:
            problems.append(
                {
                    "level": "error",
                    "exams": [exam.pk],
                    "message": f"{code}: {students} students but its venues seat only {capacity}.",
                }
            )
        elif exam.status == Exam.Status.PUBLISHED and seated[exam.pk] < students:
            missing = students - seated[exam.pk]
            problems.append(
                {
                    "level": "warning",
                    "exams": [exam.pk],
                    "message": f"{code}: {missing} student{'s' if missing != 1 else ''} registered late and "
                    "need a seat. Allocate seats again.",
                }
            )
        if exam.is_cbt:
            if not exam.questions.all():
                problems.append(
                    {"level": "warning", "exams": [exam.pk], "message": f"{code} is a CBT but has no questions yet."}
                )
            if venues and not all(v.is_cbt_centre for v in venues):
                problems.append(
                    {"level": "warning", "exams": [exam.pk], "message": f"{code} is a CBT in a hall without computers."}
                )
    return sorted(problems, key=lambda p: p["level"] != "error")


@transaction.atomic
def publish(exams, by):
    """Put draft exams on the timetable: seat everyone, then tell each student once."""
    if not exams:
        raise ValidationError("There are no draft exams to publish.")
    students = {}
    for exam in exams:
        if exam.status == Exam.Status.PUBLISHED:
            raise ValidationError(f"The {exam.offering.course.code} exam is already on the timetable.")
        allocate_seats(exam)
        exam.status = Exam.Status.PUBLISHED
        exam.save(update_fields=["status", "updated_at"])
        for student in registered_students(exam.offering):
            students[student.pk] = student
    semester = exams[0].offering.semester
    notify(
        list(students.values()),
        f"Your examination timetable for {semester} is out",
        "Check your exam dates, venues and seats, and download your exam card.",
        link="/portal/exams",
        category=EXAMS,
        email=True,
    )
    return len(students)


def announce_change(exam, before):
    """Tell candidates when a published exam's date, time or venue changes."""
    after = (exam.date, exam.start_time, sorted(v.pk for v in exam.venues.all()))
    if exam.status != Exam.Status.PUBLISHED or before == after:
        return
    when = f"{exam.date:%A %d %B} at {exam.start_time:%H:%M}"
    notify(
        list(registered_students(exam.offering)),
        f"Change to your {exam.offering.course.code} examination",
        f"It is now on {when}. Check your venue and seat, and print your exam card again.",
        link="/portal/exams",
        category=EXAMS,
        email=True,
        sms=True,
    )


# --- Exam cards and verification -----------------------------------------------------------------

CARD_SALT = "exams.card"


def card_token(student, semester):
    return signing.dumps([student.pk, semester.pk], salt=CARD_SALT, compress=True)


def read_card_token(token):
    """(student id, semester id) from an exam card's QR code."""
    try:
        student_id, semester_id = signing.loads(token.strip(), salt=CARD_SALT)
    except (signing.BadSignature, ValueError, TypeError):
        raise ValidationError("This exam card isn't genuine, or the code was mistyped.") from None
    return student_id, semester_id


def student_exams(student, semester):
    """The student's published exams this semester, each with seat, eligibility and CBT attempt."""
    exams = list(
        Exam.objects.filter(
            status=Exam.Status.PUBLISHED,
            offering__semester=semester,
            offering__enrollments__student=student,
            offering__enrollments__status=Enrollment.Status.REGISTERED,
        ).select_related("offering__course", "offering__semester")
    )
    overdue = overdue_fees(student)
    candidates = {
        c.exam_id: c for c in Candidate.objects.filter(student=student, exam__in=exams).select_related("venue")
    }
    attempts = {a.exam_id: a for a in Attempt.objects.filter(student=student, exam__in=exams)}
    rows = []
    for exam in exams:
        percent = offering_student_stats(exam.offering, [student])[student.pk]["percent"]
        candidate = candidates.get(exam.pk)
        attempt = attempts.get(exam.pk)
        if attempt:
            attempt = finalize_if_expired(attempt)
        rows.append(
            {
                "exam": exam,
                "candidate": candidate,
                "attempt": attempt,
                "attendance_percent": percent,
                **assess(percent, overdue, waived=bool(candidate and candidate.waived)),
            }
        )
    return rows


@transaction.atomic
def check_in(exam, student, by):
    """An invigilator admits a candidate to the hall after checking their exam card."""
    if exam.status != Exam.Status.PUBLISHED:
        raise ValidationError("This exam isn't on the timetable.")
    if exam.date != timezone.localdate():
        raise ValidationError(f"The {exam.offering.course.code} exam isn't today.")
    status = eligibility(student, exam)
    if not status["eligible"]:
        raise ValidationError(f"{student} may not sit {exam.offering.course.code}: {' '.join(status['reasons'])}")
    candidate, _ = Candidate.objects.select_for_update().get_or_create(exam=exam, student=student)
    if candidate.checked_in_at:
        return candidate, False
    candidate.checked_in_at, candidate.checked_in_by = timezone.now(), by
    candidate.save(update_fields=["checked_in_at", "checked_in_by"])
    return candidate, True


# --- Computer-based tests ------------------------------------------------------------------------


def ensure_setter(user, exam):
    """Only the course lecturer (or a super admin) writes and sees a CBT's questions and answers."""
    if not results.is_lecturer(user, exam.offering):
        raise PermissionDenied("Only the course lecturer can set this exam's questions.")


def questions_locked(exam):
    return exam.attempts.exists() or timezone.now() >= exam.starts_at


def ensure_unlocked(exam):
    if questions_locked(exam):
        raise ValidationError("The exam has started, so its questions can no longer be changed.")


@transaction.atomic
def save_question(exam, data, question=None):
    """Create or replace a question with its options. Exactly one option must be correct."""
    ensure_unlocked(exam)
    choices = data["choices"]
    if sum(1 for c in choices if c["is_correct"]) != 1:
        raise ValidationError({"choices": "Mark exactly one option as the correct answer."})
    if question is None:
        last = exam.questions.order_by("-order").values_list("order", flat=True).first() or 0
        question = Question(exam=exam, order=last + 1)
    question.text, question.marks = data["text"], data["marks"]
    question.save()
    question.choices.all().delete()
    Choice.objects.bulk_create(
        Choice(question=question, text=c["text"], is_correct=c["is_correct"], order=i) for i, c in enumerate(choices)
    )
    return question


def start_attempt(exam, student, ip_address=None):
    """Start (or resume) a student's CBT. Their paper is drawn and shuffled once, here."""
    code = exam.offering.course.code
    if not exam.is_cbt or exam.status != Exam.Status.PUBLISHED:
        raise ValidationError("This exam isn't a computer-based test on the timetable.")
    existing = Attempt.objects.filter(exam=exam, student=student).first()
    if existing:
        existing = finalize_if_expired(existing)
        if existing.is_open:
            return existing
        raise ValidationError(f"You have already submitted the {code} exam.")
    now = timezone.now()
    if now < exam.starts_at:
        raise ValidationError(f"The {code} exam starts at {local(exam.starts_at):%H:%M} on {exam.date:%d %B}.")
    if now > exam.entry_closes_at:
        raise ValidationError(f"Entry to the {code} exam closed at {local(exam.entry_closes_at):%H:%M}.")
    status = eligibility(student, exam)
    if not status["eligible"]:
        raise ValidationError(f"You may not sit {code}: {' '.join(status['reasons'])}")

    questions = list(exam.questions.prefetch_related("choices"))
    if not questions:
        raise ValidationError("This exam has no questions yet. Tell the invigilator.")
    rng = random.SystemRandom()
    rng.shuffle(questions)
    if exam.questions_per_candidate:
        questions = questions[: exam.questions_per_candidate]
    choice_order = {}
    for q in questions:
        ids = [c.pk for c in q.choices.all()]
        rng.shuffle(ids)
        choice_order[str(q.pk)] = ids
    try:
        with transaction.atomic():
            return Attempt.objects.create(
                exam=exam,
                student=student,
                started_at=now,
                deadline=now + timedelta(minutes=exam.duration_minutes),
                question_ids=[q.pk for q in questions],
                choice_order=choice_order,
                max_score=sum(q.marks for q in questions),
                ip_address=ip_address,
            )
    except IntegrityError:  # two tabs pressed Start at once
        return Attempt.objects.get(exam=exam, student=student)


def _time_is_up(attempt):
    return timezone.now() > attempt.deadline + timedelta(seconds=settings.EXAM_ANSWER_GRACE_SECONDS)


@transaction.atomic
def finalize(attempt, status=Attempt.Status.SUBMITTED):
    """Close an attempt and mark it. Safe to call more than once."""
    attempt = Attempt.objects.select_for_update().get(pk=attempt.pk)
    if not attempt.is_open:
        return attempt
    marks = dict(Question.objects.filter(pk__in=attempt.question_ids).values_list("pk", "marks"))
    correct = set(
        Choice.objects.filter(question_id__in=attempt.question_ids, is_correct=True).values_list("pk", flat=True)
    )
    score = sum(marks.get(a.question_id, 0) for a in attempt.answers.all() if a.choice_id in correct)
    attempt.status, attempt.submitted_at, attempt.score = status, timezone.now(), Decimal(score)
    attempt.save(update_fields=["status", "submitted_at", "score"])
    return attempt


def finalize_if_expired(attempt):
    if attempt.is_open and _time_is_up(attempt):
        return finalize(attempt, Attempt.Status.TIMED_OUT)
    return attempt


def close_expired_attempts(exam=None):
    """Submit every attempt whose time has run out (the student closed the page, lost power...)."""
    attempts = Attempt.objects.filter(status=Attempt.Status.IN_PROGRESS)
    if exam is not None:
        attempts = attempts.filter(exam=exam)
    return sum(1 for a in attempts if not finalize_if_expired(a).is_open)


def save_answer(attempt, question_id, choice_id):
    attempt = finalize_if_expired(attempt)
    if not attempt.is_open:
        raise ValidationError("Time is up. Your exam has been submitted.")
    if question_id not in attempt.question_ids:
        raise ValidationError("That question isn't on your paper.")
    if choice_id is not None and choice_id not in attempt.choice_order.get(str(question_id), []):
        raise ValidationError("That option doesn't belong to the question.")
    Answer.objects.update_or_create(attempt=attempt, question_id=question_id, defaults={"choice_id": choice_id})


MAX_EVENTS_PER_ATTEMPT = 500


def record_event(attempt, kind):
    if not attempt.is_open or attempt.events.count() >= MAX_EVENTS_PER_ATTEMPT:
        return attempt
    AttemptEvent.objects.create(attempt=attempt, kind=kind)
    if kind in (AttemptEvent.Kind.LEFT_PAGE, AttemptEvent.Kind.FULLSCREEN_EXIT):
        Attempt.objects.filter(pk=attempt.pk).update(focus_losses=attempt.focus_losses + 1)
        attempt.refresh_from_db(fields=["focus_losses"])
    return attempt


def scaled_score(attempt):
    """Marks obtained, scaled to the examination's share of the course total (70)."""
    if attempt.score is None or not attempt.max_score:
        return None
    return (attempt.score * EXAM_MAX / attempt.max_score).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


@transaction.atomic
def release_scores(exam, by):
    """Copy CBT scores (scaled to 70) into the course's result sheet as examination scores."""
    ensure_setter(by, exam)
    if not exam.is_cbt:
        raise ValidationError("Only computer-based tests have scores to release.")
    close_expired_attempts(exam)
    writing = exam.attempts.filter(status=Attempt.Status.IN_PROGRESS).count()
    if writing:
        raise ValidationError(f"{writing} candidate{'s are' if writing != 1 else ' is'} still writing.")
    attempts = {a.student_id: a for a in exam.attempts.all()}
    enrollments = list(results.registered(exam.offering).filter(student_id__in=attempts))
    if any(e.result_status not in results.EDITABLE for e in enrollments):
        raise ValidationError("The results for this course have already been submitted, so scores can't be released.")
    rows = [{"enrollment": e.pk, "exam_score": scaled_score(attempts[e.student_id])} for e in enrollments]
    if rows:
        results.enter_scores(exam.offering, rows, by)
    exam.scores_released_at = timezone.now()
    exam.save(update_fields=["scores_released_at", "updated_at"])
    absent = results.registered(exam.offering).exclude(student_id__in=attempts).count()
    return {"released": len(rows), "absent": absent}
