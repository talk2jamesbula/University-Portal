"""Result sheets: lecturers enter scores and submit; HODs, Deans and the Exams Office approve and publish."""

from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsMember
from apps.core.services import audit

from . import results
from .grading import CA_MAX, EXAM_MAX
from .models import CourseOffering, Enrollment, ResultAction, Semester
from .serializers import OfferingSerializer, RosterEntrySerializer
from .services import current_semester


class ScoreRowSerializer(serializers.Serializer):
    enrollment = serializers.IntegerField()
    ca_score = serializers.DecimalField(
        max_digits=4, decimal_places=1, min_value=0, max_value=CA_MAX, allow_null=True, required=False
    )
    exam_score = serializers.DecimalField(
        max_digits=4, decimal_places=1, min_value=0, max_value=EXAM_MAX, allow_null=True, required=False
    )


class ScoresSerializer(serializers.Serializer):
    scores = ScoreRowSerializer(many=True, allow_empty=False)


class NoteSerializer(serializers.Serializer):
    note = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")


class ResultActionSerializer(serializers.ModelSerializer):
    action_label = serializers.CharField(source="get_action_display", read_only=True)
    by_name = serializers.CharField(source="by.get_full_name", read_only=True, default=None)

    class Meta:
        model = ResultAction
        fields = ["id", "action", "action_label", "from_status", "to_status", "note", "by_name", "at"]


def _offering(pk, user):
    offering = get_object_or_404(
        CourseOffering.objects.select_related("course__department", "semester", "lecturer"), pk=pk
    )
    if not results.can_view(user, offering):
        raise PermissionDenied("You can't view the results for this course.")
    return offering


def sheet(offering, user):
    enrollments = (
        results.registered(offering).select_related("student__student_profile").order_by("student__university_id")
    )
    status = results.overall_status(e.result_status for e in enrollments)
    return {
        "offering": OfferingSerializer(offering).data,
        "status": status,
        "status_label": Enrollment.ResultStatus(status).label if status else None,
        "actions": results.allowed_actions(user, offering, status) if status else [],
        "ca_max": CA_MAX,
        "exam_max": EXAM_MAX,
        "rows": RosterEntrySerializer(enrollments, many=True).data,
        "history": ResultActionSerializer(offering.result_actions.select_related("by"), many=True).data,
    }


class ResultSheetListView(APIView):
    """Courses whose results the user teaches or reviews this semester (?semester=<id>&status=<status>)."""

    permission_classes = [IsMember]

    def get(self, request):
        semester_id = request.query_params.get("semester")
        semester = get_object_or_404(Semester, pk=semester_id) if semester_id else current_semester()
        if semester is None:
            raise ValidationError("There is no current semester.")
        rows = results.sheet_summaries(request.user, semester)
        wanted = request.query_params.get("status")
        if wanted == "mine":  # waiting for this user to act
            rows = [r for r in rows if {"submit", "approve"} & set(r["actions"])]
        elif wanted:
            rows = [r for r in rows if r["status"] == wanted]
        return Response({"semester": {"id": semester.pk, "name": semester.name}, "rows": rows})


class ResultSheetView(APIView):
    """GET a course's result sheet. PATCH {"scores": [...]} to enter or change scores (lecturer)."""

    permission_classes = [IsMember]

    def get(self, request, pk):
        return Response(sheet(_offering(pk, request.user), request.user))

    def patch(self, request, pk):
        offering = _offering(pk, request.user)
        serializer = ScoresSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        changed = results.enter_scores(offering, serializer.validated_data["scores"], request.user)
        audit(request, "results.scores", offering, f"Entered scores for {len(changed)} students in {offering}")
        return Response(sheet(offering, request.user))


class ResultSheetActionView(APIView):
    """POST {"note": ...} to submit, approve (at the current stage) or return a course's results."""

    permission_classes = [IsMember]
    ACTIONS = {"submit": results.submit, "approve": results.approve, "return": results.return_to_lecturer}

    def post(self, request, pk, action):
        if action not in self.ACTIONS:
            raise ValidationError(f"Unknown action {action}.")
        offering = _offering(pk, request.user)
        serializer = NoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        done = self.ACTIONS[action](offering, request.user, serializer.validated_data["note"].strip())
        audit(request, f"results.{done.action}", offering, f"{done.get_action_display()}: {offering}")
        return Response(sheet(offering, request.user))
