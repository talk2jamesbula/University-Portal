from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.academics.models import CourseOffering, Enrollment, Semester
from apps.academics.services import current_semester
from apps.accounts.permissions import IsMember, IsStudent, Requires
from apps.core.services import audit, client_ip
from apps.finance.views.common import pdf_response

from . import services
from .documents import card_number, exam_card_pdf
from .models import Attempt, Exam, Question, Venue
from .serializers import (
    AnswerSerializer,
    AttemptSummarySerializer,
    CheckInSerializer,
    EventSerializer,
    ExamSerializer,
    ExamSettingsSerializer,
    PublishSerializer,
    QuestionSerializer,
    VenueSerializer,
    WaiverSerializer,
)

User = get_user_model()
MANAGE = "exams.manage"


def _semester(request):
    semester_id = request.query_params.get("semester") or request.data.get("semester")
    semester = get_object_or_404(Semester, pk=semester_id) if semester_id else current_semester()
    if semester is None:
        raise ValidationError("There is no current semester.")
    return semester


def _student_brief(student):
    profile = getattr(student, "student_profile", None)
    return {
        "id": student.pk,
        "name": student.get_full_name(),
        "matric_number": student.university_id,
        "avatar_url": student.avatar_url,
        "programme": profile.programme.title if profile else None,
        "level": profile.level if profile else None,
    }


def _exam_brief(exam):
    return {
        "id": exam.pk,
        "code": exam.offering.course.code,
        "title": exam.offering.course.title,
        "date": exam.date,
        "start_time": exam.start_time,
        "duration_minutes": exam.duration_minutes,
        "mode": exam.mode,
        "mode_label": exam.get_mode_display(),
        "starts_at": exam.starts_at,
        "entry_closes_at": exam.entry_closes_at,
    }


def _seat(candidate):
    return {
        "venue": candidate.venue.name if candidate and candidate.venue else None,
        "venue_location": candidate.venue.location if candidate and candidate.venue else None,
        "seat_number": candidate.seat_number if candidate else None,
        "checked_in_at": candidate.checked_in_at if candidate else None,
        "waiver_reason": candidate.waiver_reason if candidate and candidate.waived else "",
    }


def _eligibility(row):
    return {"eligible": row["eligible"], "reasons": row["reasons"], "waived": row["waived"]}


# --- Exams Office: venues and the timetable ------------------------------------------------------


class VenueViewSet(viewsets.ModelViewSet):
    serializer_class = VenueSerializer
    pagination_class = None
    filterset_fields = ["is_active", "is_cbt_centre"]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsMember()]
        return [Requires(MANAGE)()]

    def get_queryset(self):
        return Venue.objects.all()

    def perform_create(self, serializer):
        venue = serializer.save()
        audit(self.request, "exams.venue_create", venue, f"Created exam venue {venue}")

    def perform_update(self, serializer):
        venue = serializer.save()
        audit(self.request, "exams.venue_update", venue, f"Updated exam venue {venue}")

    def perform_destroy(self, venue):
        if venue.exams.exists():
            raise ValidationError(f"{venue} is used on the timetable. Mark it inactive instead.")
        audit(self.request, "exams.venue_delete", None, f"Deleted exam venue {venue}")
        venue.delete()


class ExamViewSet(viewsets.ModelViewSet):
    """The exam timetable. The Exams Office schedules exams; course lecturers see theirs and set CBT questions."""

    serializer_class = ExamSerializer
    permission_classes = [IsMember]
    pagination_class = None

    def get_queryset(self):
        qs = (
            Exam.objects.select_related("offering__course__department", "offering__semester", "offering__lecturer")
            .prefetch_related("venues")
            .annotate(
                registered_count=Count(
                    "offering__enrollments",
                    filter=Q(offering__enrollments__status=Enrollment.Status.REGISTERED),
                    distinct=True,
                ),
                seated_count=Count("candidates", filter=Q(candidates__venue__isnull=False), distinct=True),
                question_count=Count("questions", distinct=True),
            )
            .order_by("date", "start_time", "offering__course__code")
        )
        user = self.request.user
        if not user.has_permission(MANAGE):
            qs = qs.filter(offering__lecturer=user)
        if self.action == "list":
            params = self.request.query_params
            if params.get("offering"):
                qs = qs.filter(offering_id=params["offering"])
            else:
                qs = qs.filter(offering__semester=_semester(self.request))
            for field in ("status", "mode", "date"):
                if params.get(field):
                    qs = qs.filter(**{field: params[field]})
            if params.get("mine") == "true":
                qs = qs.filter(offering__lecturer=user)
        return qs

    def _require_manager(self):
        if not self.request.user.has_permission(MANAGE):
            raise PermissionDenied("Only the Examinations Office can change the timetable.")

    def _fresh(self, exam):
        return self.get_queryset().get(pk=exam.pk)

    def perform_create(self, serializer):
        self._require_manager()
        exam = serializer.save(created_by=self.request.user)
        audit(self.request, "exams.create", exam, f"Scheduled {exam}")

    def update(self, request, *args, **kwargs):
        self._require_manager()
        exam = self.get_object()
        before = (exam.date, exam.start_time, sorted(v.pk for v in exam.venues.all()))
        serializer = self.get_serializer(exam, data=request.data, partial=kwargs.get("partial", False))
        serializer.is_valid(raise_exception=True)
        exam = serializer.save()
        if exam.status == Exam.Status.PUBLISHED and before[2] != sorted(v.pk for v in exam.venues.all()):
            services.allocate_seats(exam)
        services.announce_change(exam, before)
        audit(request, "exams.update", exam, f"Updated {exam}")
        return Response(self.get_serializer(self._fresh(exam)).data)

    def perform_destroy(self, exam):
        self._require_manager()
        if exam.status == Exam.Status.PUBLISHED:
            raise ValidationError("This exam is on the timetable and students have been told. Move it instead.")
        audit(self.request, "exams.delete", None, f"Deleted {exam}")
        exam.delete()

    # Timetable-wide

    @action(detail=False, methods=["get"])
    def problems(self, request):
        self._require_manager()
        return Response(services.timetable_problems(_semester(request)))

    @action(detail=False, methods=["get"])
    def unscheduled(self, request):
        """Courses offered in the semester that have no exam yet, for the scheduling form."""
        self._require_manager()
        offerings = (
            CourseOffering.objects.filter(semester=_semester(request), exam__isnull=True)
            .select_related("course", "lecturer")
            .annotate(registered=Count("enrollments", filter=Q(enrollments__status=Enrollment.Status.REGISTERED)))
            .order_by("course__code")
        )
        return Response(
            [
                {
                    "id": o.pk,
                    "code": o.course.code,
                    "title": o.course.title,
                    "lecturer_name": o.lecturer.get_full_name() if o.lecturer else None,
                    "registered_count": o.registered,
                }
                for o in offerings
            ]
        )

    @action(detail=False, methods=["post"])
    def publish(self, request):
        self._require_manager()
        serializer = PublishSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        drafts = Exam.objects.filter(
            offering__semester_id=serializer.validated_data["semester"], status=Exam.Status.DRAFT
        ).select_related("offering__course", "offering__semester")
        if "exams" in serializer.validated_data:
            drafts = drafts.filter(pk__in=serializer.validated_data["exams"])
        drafts = list(drafts)
        students = services.publish(drafts, request.user)
        audit(request, "exams.publish", None, f"Published {len(drafts)} exams to {students} students")
        return Response({"published": len(drafts), "students": students})

    # One exam

    @action(detail=True, methods=["post"], url_path="allocate-seats")
    def allocate_seats(self, request, pk=None):
        self._require_manager()
        exam = self.get_object()
        seated = services.allocate_seats(exam)
        audit(request, "exams.allocate", exam, f"Allocated {seated} seats for {exam}")
        return Response({"seated": seated, "exam": self.get_serializer(self._fresh(exam)).data})

    @action(detail=True, methods=["get"])
    def candidates(self, request, pk=None):
        exam = self.get_object()
        rows = services.roster(exam)
        return Response(
            {
                "exam": self.get_serializer(exam).data,
                "minimum_percent": settings.ATTENDANCE_MIN_PERCENT,
                "fees_rule": settings.EXAM_REQUIRE_FEES_CLEARED,
                "can_waive": request.user.has_permission(MANAGE),
                "rows": [
                    {
                        "student": _student_brief(r["student"]),
                        "attendance_percent": r["attendance_percent"],
                        **_eligibility(r),
                        **_seat(r["candidate"]),
                        "attempt_status": r["attempt"].status if r["attempt"] else None,
                    }
                    for r in rows
                ],
            }
        )

    @action(detail=True, methods=["post"])
    def waive(self, request, pk=None):
        self._require_manager()
        exam = self.get_object()
        serializer = WaiverSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        student = get_object_or_404(User, pk=data["student"], role=User.Role.STUDENT)
        candidate = services.set_waiver(exam, student, data["waived"], data["reason"], request.user)
        verb = "Waived" if candidate.waived else "Removed waiver of"
        audit(request, "exams.waiver", candidate, f"{verb} exam rules for {student} in {exam}: {data['reason']}")
        return Response({"waived": candidate.waived, "waiver_reason": candidate.waiver_reason})

    # The course lecturer: CBT questions and scores

    @action(detail=True, methods=["patch"], url_path="settings")
    def lecturer_settings(self, request, pk=None):
        exam = self.get_object()
        services.ensure_setter(request.user, exam)
        serializer = ExamSettingsSerializer(exam, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        if "questions_per_candidate" in serializer.validated_data:
            services.ensure_unlocked(exam)
        serializer.save()
        return Response(self.get_serializer(self._fresh(exam)).data)

    @action(detail=True, methods=["get", "post"])
    def questions(self, request, pk=None):
        exam = self.get_object()
        services.ensure_setter(request.user, exam)
        if request.method == "POST":
            serializer = QuestionSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            question = services.save_question(exam, serializer.validated_data)
            return Response(QuestionSerializer(question).data, status=status.HTTP_201_CREATED)
        return Response(
            {
                "locked": services.questions_locked(exam),
                "questions": QuestionSerializer(exam.questions.prefetch_related("choices"), many=True).data,
            }
        )

    @action(detail=True, methods=["get"])
    def attempts(self, request, pk=None):
        exam = self.get_object()
        services.close_expired_attempts(exam)
        attempts = exam.attempts.select_related("student").annotate(
            answered=Count("answers", filter=Q(answers__choice__isnull=False))
        )
        return Response(AttemptSummarySerializer(attempts, many=True).data)

    @action(detail=True, methods=["post"], url_path="release-scores")
    def release_scores(self, request, pk=None):
        exam = self.get_object()
        outcome = services.release_scores(exam, request.user)
        audit(request, "exams.release_scores", exam, f"Released CBT scores for {exam} ({outcome['released']})")
        return Response(outcome)


class QuestionView(APIView):
    """PUT to replace a CBT question (with its options); DELETE to remove it. Course lecturer only."""

    permission_classes = [IsMember]

    def _question(self, request, pk):
        question = get_object_or_404(Question.objects.select_related("exam__offering"), pk=pk)
        services.ensure_setter(request.user, question.exam)
        return question

    def put(self, request, pk):
        question = self._question(request, pk)
        serializer = QuestionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        question = services.save_question(question.exam, serializer.validated_data, question)
        return Response(QuestionSerializer(question).data)

    def delete(self, request, pk):
        question = self._question(request, pk)
        services.ensure_unlocked(question.exam)
        question.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# --- Students ------------------------------------------------------------------------------------


def _student_rows(rows):
    out = []
    for r in rows:
        exam, attempt = r["exam"], r["attempt"]
        now = timezone.now()
        out.append(
            {
                **_exam_brief(exam),
                **_eligibility(r),
                **_seat(r["candidate"]),
                "attendance_percent": r["attendance_percent"],
                "attempt": {"id": attempt.pk, "status": attempt.status, "status_label": attempt.get_status_display()}
                if attempt
                else None,
                "can_start": exam.is_cbt
                and r["eligible"]
                and exam.starts_at <= now <= exam.entry_closes_at
                and (attempt is None or attempt.is_open),
            }
        )
    return out


class MyExamsView(APIView):
    """A student's exam timetable this semester, with seats, eligibility and CBT status."""

    permission_classes = [IsStudent]

    def get(self, request):
        semester = _semester(request)
        rows = services.student_exams(request.user, semester)
        return Response(
            {
                "semester": {"id": semester.pk, "name": semester.name},
                "minimum_percent": settings.ATTENDANCE_MIN_PERCENT,
                "card_available": any(r["eligible"] for r in rows),
                "exams": _student_rows(rows),
            }
        )


def _card_response(request, student, semester):
    rows = [r for r in services.student_exams(student, semester) if r["eligible"]]
    if not rows:
        raise ValidationError("There are no examinations you're eligible to sit on the timetable yet.")
    token = services.card_token(student, semester)
    verify_url = f"{settings.PORTAL_URL.rstrip('/')}/portal/exams/verify?c={token}"
    content = exam_card_pdf(student, semester, rows, verify_url)
    audit(request, "exams.card", student, f"Issued exam card {card_number(student, semester)}")
    return pdf_response(content, f"exam-card-{semester.code}.pdf", request)


class MyExamCardView(APIView):
    permission_classes = [IsStudent]

    def get(self, request):
        return _card_response(request, request.user, _semester(request))


class StudentExamCardView(APIView):
    """The Exams Office prints a student's card for them."""

    permission_classes = [Requires(MANAGE)]

    def get(self, request, pk):
        student = get_object_or_404(User.objects.select_related("student_profile"), pk=pk, role=User.Role.STUDENT)
        return _card_response(request, student, _semester(request))


# --- Students: sitting a CBT ---------------------------------------------------------------------


def paper(attempt):
    """The candidate's paper: their questions and options in their own order, without the answers."""
    exam = attempt.exam
    data = {
        "id": attempt.pk,
        "exam": {**_exam_brief(exam), "instructions": exam.instructions},
        "status": attempt.status,
        "status_label": attempt.get_status_display(),
        "deadline": attempt.deadline,
        "server_time": timezone.now(),
        "focus_losses": attempt.focus_losses,
        "question_count": len(attempt.question_ids),
    }
    if not attempt.is_open:
        data["answered"] = attempt.answers.filter(choice__isnull=False).count()
        return data
    questions = {q.pk: q for q in Question.objects.filter(pk__in=attempt.question_ids).prefetch_related("choices")}
    answers = dict(attempt.answers.values_list("question_id", "choice_id"))
    data["questions"] = []
    for number, qid in enumerate(attempt.question_ids, 1):
        question = questions.get(qid)
        if question is None:
            continue
        choices = {c.pk: c for c in question.choices.all()}
        data["questions"].append(
            {
                "id": qid,
                "number": number,
                "text": question.text,
                "marks": question.marks,
                "choices": [
                    {"id": cid, "text": choices[cid].text} for cid in attempt.choice_order[str(qid)] if cid in choices
                ],
                "answer": answers.get(qid),
            }
        )
    return data


def _own_attempt(request, pk):
    attempt = get_object_or_404(Attempt.objects.select_related("exam__offering__course"), pk=pk, student=request.user)
    return services.finalize_if_expired(attempt)


class StartAttemptView(APIView):
    permission_classes = [IsStudent]

    def post(self, request, pk):
        exam = get_object_or_404(Exam.objects.select_related("offering__course", "offering__semester"), pk=pk)
        attempt = services.start_attempt(exam, request.user, client_ip(request))
        return Response(paper(attempt), status=status.HTTP_201_CREATED)


class AttemptView(APIView):
    permission_classes = [IsStudent]

    def get(self, request, pk):
        return Response(paper(_own_attempt(request, pk)))


class AnswerView(APIView):
    """Autosave one answer (choice may be null to clear it)."""

    permission_classes = [IsStudent]

    def put(self, request, pk):
        attempt = _own_attempt(request, pk)
        serializer = AnswerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.save_answer(attempt, serializer.validated_data["question"], serializer.validated_data["choice"])
        return Response({"saved": True, "server_time": timezone.now()})


class AttemptEventView(APIView):
    permission_classes = [IsStudent]

    def post(self, request, pk):
        serializer = EventSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        attempt = services.record_event(_own_attempt(request, pk), serializer.validated_data["kind"])
        return Response({"focus_losses": attempt.focus_losses})


class SubmitAttemptView(APIView):
    permission_classes = [IsStudent]

    def post(self, request, pk):
        attempt = services.finalize(_own_attempt(request, pk))
        audit(request, "exams.submit", attempt, f"Submitted {attempt.exam}")
        return Response(paper(attempt))


# --- Invigilators --------------------------------------------------------------------------------


class VerifyView(APIView):
    """Look up a candidate by exam card QR code (?code=) or matric number (?matric=)."""

    permission_classes = [Requires("exams.invigilate", MANAGE)]

    def get(self, request):
        code = request.query_params.get("code", "").strip()
        matric = request.query_params.get("matric", "").strip()
        students = User.objects.filter(role=User.Role.STUDENT).select_related("student_profile__programme")
        if code:
            student_id, semester_id = services.read_card_token(code)
            student = get_object_or_404(students, pk=student_id)
            semester = get_object_or_404(Semester, pk=semester_id)
        elif matric:
            student = students.filter(university_id__iexact=matric).first()
            if student is None:
                raise ValidationError(f"No student has the matric number {matric}.")
            semester = _semester(request)
        else:
            raise ValidationError("Scan the exam card or enter a matric number.")
        rows = services.student_exams(student, semester)
        today = timezone.localdate()
        return Response(
            {
                "student": _student_brief(student),
                "semester": {"id": semester.pk, "name": semester.name},
                "card_number": card_number(student, semester),
                "exams": [{**r, "is_today": r["date"] == today} for r in _student_rows(rows)],
            }
        )


class VerifyCheckInView(APIView):
    permission_classes = [Requires("exams.invigilate", MANAGE)]

    def post(self, request):
        serializer = CheckInSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        exam = get_object_or_404(Exam.objects.select_related("offering__course"), pk=serializer.validated_data["exam"])
        student = get_object_or_404(User, pk=serializer.validated_data["student"], role=User.Role.STUDENT)
        candidate, created = services.check_in(exam, student, request.user)
        if created:
            audit(request, "exams.check_in", candidate, f"Checked {student} in to {exam}")
        return Response(
            {"created": created, "checked_in_at": candidate.checked_in_at, **_seat(candidate)},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )
