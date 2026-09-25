from datetime import timedelta

from rest_framework import serializers

from .models import Attempt, AttemptEvent, Exam, Venue
from .services import scaled_score


class VenueSerializer(serializers.ModelSerializer):
    class Meta:
        model = Venue
        fields = ["id", "code", "name", "capacity", "location", "is_cbt_centre", "is_active"]


class ExamSerializer(serializers.ModelSerializer):
    code = serializers.CharField(source="offering.course.code", read_only=True)
    title = serializers.CharField(source="offering.course.title", read_only=True)
    department = serializers.CharField(source="offering.course.department.name", read_only=True)
    semester = serializers.IntegerField(source="offering.semester_id", read_only=True)
    lecturer = serializers.IntegerField(source="offering.lecturer_id", read_only=True)
    lecturer_name = serializers.CharField(source="offering.lecturer.get_full_name", read_only=True, default=None)
    mode_label = serializers.CharField(source="get_mode_display", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    venue_details = VenueSerializer(source="venues", many=True, read_only=True)
    registered_count = serializers.IntegerField(read_only=True, default=None)
    seated_count = serializers.IntegerField(read_only=True, default=None)
    question_count = serializers.IntegerField(read_only=True, default=None)
    starts_at = serializers.DateTimeField(read_only=True)
    ends_at = serializers.DateTimeField(read_only=True)
    entry_closes_at = serializers.DateTimeField(read_only=True)

    class Meta:
        model = Exam
        fields = [
            "id",
            "offering",
            "code",
            "title",
            "department",
            "semester",
            "lecturer",
            "lecturer_name",
            "date",
            "start_time",
            "duration_minutes",
            "mode",
            "mode_label",
            "status",
            "status_label",
            "venues",
            "venue_details",
            "instructions",
            "questions_per_candidate",
            "late_entry_minutes",
            "registered_count",
            "seated_count",
            "question_count",
            "starts_at",
            "ends_at",
            "entry_closes_at",
            "scores_released_at",
        ]
        read_only_fields = ["status", "scores_released_at"]

    def validate(self, attrs):
        offering = attrs.get("offering", getattr(self.instance, "offering", None))
        date = attrs.get("date", getattr(self.instance, "date", None))
        if self.instance and "offering" in attrs and attrs["offering"] != self.instance.offering:
            raise serializers.ValidationError({"offering": "An exam can't be moved to another course."})
        if offering and date:
            semester = offering.semester
            if not (semester.start_date <= date <= semester.end_date + timedelta(days=60)):
                raise serializers.ValidationError({"date": f"The date must fall within {semester} or soon after it."})
        if self.instance and self.instance.attempts.exists():
            changed = [f for f in ("date", "start_time", "duration_minutes", "mode") if f in attrs]
            if any(attrs[f] != getattr(self.instance, f) for f in changed):
                raise serializers.ValidationError("Candidates have already started this CBT; its timing can't change.")
        return attrs


class ExamSettingsSerializer(serializers.ModelSerializer):
    """What the course lecturer may set on their own exam."""

    class Meta:
        model = Exam
        fields = ["instructions", "questions_per_candidate"]
        extra_kwargs = {"questions_per_candidate": {"min_value": 1}}


class ChoiceInputSerializer(serializers.Serializer):
    text = serializers.CharField(max_length=500)
    is_correct = serializers.BooleanField(default=False)


class QuestionSerializer(serializers.Serializer):
    """A question with its options, as the lecturer writes and sees it (answers included)."""

    id = serializers.IntegerField(read_only=True)
    order = serializers.IntegerField(read_only=True)
    text = serializers.CharField(max_length=5000)
    marks = serializers.IntegerField(min_value=1, max_value=20, default=1)
    choices = ChoiceInputSerializer(many=True, min_length=2, max_length=6)

    def to_representation(self, question):
        return {
            "id": question.pk,
            "order": question.order,
            "text": question.text,
            "marks": question.marks,
            "choices": [{"id": c.pk, "text": c.text, "is_correct": c.is_correct} for c in question.choices.all()],
        }


class WaiverSerializer(serializers.Serializer):
    student = serializers.IntegerField()
    waived = serializers.BooleanField()
    reason = serializers.CharField(max_length=300, required=False, allow_blank=True, default="")


class PublishSerializer(serializers.Serializer):
    semester = serializers.IntegerField()
    exams = serializers.ListField(child=serializers.IntegerField(), required=False)


class AnswerSerializer(serializers.Serializer):
    question = serializers.IntegerField()
    choice = serializers.IntegerField(allow_null=True)


class EventSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=AttemptEvent.Kind.choices)


class CheckInSerializer(serializers.Serializer):
    exam = serializers.IntegerField()
    student = serializers.IntegerField()


class AttemptSummarySerializer(serializers.ModelSerializer):
    """An attempt as the lecturer and Exams Office see it."""

    student_name = serializers.CharField(source="student.get_full_name", read_only=True)
    matric_number = serializers.CharField(source="student.university_id", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    flagged = serializers.BooleanField(read_only=True)
    answered = serializers.IntegerField(read_only=True, default=None)
    scaled_score = serializers.SerializerMethodField()

    class Meta:
        model = Attempt
        fields = [
            "id",
            "student",
            "student_name",
            "matric_number",
            "status",
            "status_label",
            "started_at",
            "submitted_at",
            "deadline",
            "score",
            "max_score",
            "scaled_score",
            "answered",
            "focus_losses",
            "flagged",
        ]

    def get_scaled_score(self, attempt):
        return scaled_score(attempt)
