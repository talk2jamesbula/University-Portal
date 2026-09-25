from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers

from .models import AttendanceCorrection, AttendanceRecord, AttendanceSession


class SessionSerializer(serializers.ModelSerializer):
    course_code = serializers.CharField(source="offering.course.code", read_only=True)
    course_title = serializers.CharField(source="offering.course.title", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    checkin_closes_at = serializers.DateTimeField(read_only=True)
    attended_count = serializers.IntegerField(read_only=True, default=None)
    record_count = serializers.IntegerField(read_only=True, default=None)

    class Meta:
        model = AttendanceSession
        fields = [
            "id",
            "offering",
            "course_code",
            "course_title",
            "date",
            "start_time",
            "topic",
            "status",
            "status_label",
            "checkin_minutes",
            "late_after_minutes",
            "opened_at",
            "closed_at",
            "checkin_closes_at",
            "attended_count",
            "record_count",
            "created_at",
        ]
        read_only_fields = ["status", "opened_at", "closed_at", "created_at"]
        extra_kwargs = {
            "checkin_minutes": {"min_value": 1, "max_value": 180},
            "late_after_minutes": {"min_value": 0, "max_value": 180},
        }

    def validate_date(self, value):
        if value > timezone.localdate() + timedelta(days=60):
            raise serializers.ValidationError("Sessions can be scheduled up to 60 days ahead.")
        return value

    def validate(self, attrs):
        offering = attrs.get("offering", getattr(self.instance, "offering", None))
        date = attrs.get("date")
        if offering and date and not (offering.semester.start_date <= date <= offering.semester.end_date):
            raise serializers.ValidationError({"date": f"The date must fall within {offering.semester}."})
        return attrs


class RecordSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.get_full_name", read_only=True)
    matric_number = serializers.CharField(source="student.university_id", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    method_label = serializers.CharField(source="get_method_display", read_only=True)
    pending_correction = serializers.SerializerMethodField()

    class Meta:
        model = AttendanceRecord
        fields = [
            "id",
            "student",
            "student_name",
            "matric_number",
            "status",
            "status_label",
            "method",
            "method_label",
            "marked_at",
            "flagged",
            "flag_reason",
            "pending_correction",
        ]

    def get_pending_correction(self, obj):
        pending = [c for c in obj.corrections.all() if c.status == AttendanceCorrection.Status.PENDING]
        return {"id": pending[0].id, "to_status": pending[0].to_status} if pending else None


class CorrectionSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="record.student.get_full_name", read_only=True)
    matric_number = serializers.CharField(source="record.student.university_id", read_only=True)
    course_code = serializers.CharField(source="record.session.offering.course.code", read_only=True)
    session_date = serializers.DateField(source="record.session.date", read_only=True)
    session_id = serializers.IntegerField(source="record.session_id", read_only=True)
    requested_by_name = serializers.CharField(source="requested_by.get_full_name", read_only=True, default=None)
    decided_by_name = serializers.CharField(source="decided_by.get_full_name", read_only=True, default=None)
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = AttendanceCorrection
        fields = [
            "id",
            "student_name",
            "matric_number",
            "course_code",
            "session_date",
            "session_id",
            "from_status",
            "to_status",
            "reason",
            "status",
            "status_label",
            "requested_by_name",
            "decided_by_name",
            "decision_note",
            "created_at",
            "decided_at",
        ]


class MarkSerializer(serializers.Serializer):
    student = serializers.IntegerField()
    status = serializers.ChoiceField(choices=AttendanceRecord.Status.choices)


class CorrectionRequestSerializer(serializers.Serializer):
    to_status = serializers.ChoiceField(choices=AttendanceRecord.Status.choices)
    reason = serializers.CharField(min_length=5, max_length=300)


class DecisionSerializer(serializers.Serializer):
    approve = serializers.BooleanField()
    note = serializers.CharField(max_length=300, required=False, allow_blank=True, default="")


class CheckInSerializer(serializers.Serializer):
    session = serializers.IntegerField(required=False)
    token = serializers.CharField(max_length=32, required=False, allow_blank=True, default="")
    code = serializers.RegexField(
        r"^\d{6}$",
        required=False,
        allow_blank=True,
        default="",
        error_messages={"invalid": "Enter the 6-digit code shown in class."},
    )
    device_id = serializers.CharField(max_length=64, required=False, allow_blank=True, default="")

    def validate(self, attrs):
        if not (attrs["token"] or attrs["code"]):
            raise serializers.ValidationError("Scan the QR code or enter the 6-digit code.")
        if attrs["token"] and not attrs.get("session"):
            raise serializers.ValidationError("The QR link is incomplete. Scan it again.")
        return attrs
