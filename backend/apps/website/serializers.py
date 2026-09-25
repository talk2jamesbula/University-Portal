from rest_framework import serializers

from apps.academics.models import Department, Faculty, Programme, ProgrammeCourse
from apps.campus.models import Announcement, Event

from .models import ContactMessage


class PublicProgrammeSerializer(serializers.ModelSerializer):
    title = serializers.CharField(read_only=True)
    degree_label = serializers.CharField(source="get_degree_display", read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True)
    faculty_name = serializers.CharField(source="department.faculty.name", read_only=True)

    class Meta:
        model = Programme
        fields = [
            "code",
            "name",
            "title",
            "degree",
            "degree_label",
            "duration_years",
            "description",
            "department_name",
            "faculty_name",
        ]


class PublicDepartmentSerializer(serializers.ModelSerializer):
    programmes = serializers.SerializerMethodField()

    class Meta:
        model = Department
        fields = ["code", "name", "description", "programmes"]

    def get_programmes(self, obj):
        return PublicProgrammeSerializer([p for p in obj.programmes.all() if p.is_active], many=True).data


class PublicFacultySerializer(serializers.ModelSerializer):
    departments = PublicDepartmentSerializer(many=True, read_only=True)

    class Meta:
        model = Faculty
        fields = ["code", "name", "description", "departments"]


class CurriculumCourseSerializer(serializers.ModelSerializer):
    code = serializers.CharField(source="course.code")
    title = serializers.CharField(source="course.title")
    units = serializers.IntegerField(source="course.units")

    class Meta:
        model = ProgrammeCourse
        fields = ["code", "title", "units", "is_compulsory"]


class PublicNewsSerializer(serializers.ModelSerializer):
    summary = serializers.SerializerMethodField()

    class Meta:
        model = Announcement
        fields = ["id", "title", "summary", "body", "priority", "created_at"]

    def get_summary(self, obj):
        text = " ".join(obj.body.split())
        return text if len(text) <= 180 else text[:177].rsplit(" ", 1)[0] + "…"


class PublicEventSerializer(serializers.ModelSerializer):
    category_label = serializers.CharField(source="get_category_display", read_only=True)

    class Meta:
        model = Event
        fields = ["id", "title", "description", "category", "category_label", "location", "starts_at", "ends_at"]


class ContactMessageSerializer(serializers.ModelSerializer):
    # Honeypot: a hidden field real visitors leave empty; bots tend to fill it in.
    website = serializers.CharField(required=False, allow_blank=True, write_only=True)

    class Meta:
        model = ContactMessage
        fields = ["name", "email", "phone", "topic", "subject", "message", "website"]

    def validate_website(self, value):
        if value:
            raise serializers.ValidationError("Leave this field empty.")
        return value

    def validate_message(self, value):
        if len(value.strip()) < 10:
            raise serializers.ValidationError("Please write a little more so we can help.")
        return value.strip()

    def create(self, validated_data):
        validated_data.pop("website", None)
        return super().create(validated_data)


class ChatMessageSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=["user", "assistant"])
    content = serializers.CharField(max_length=2000, trim_whitespace=True)


class ChatSerializer(serializers.Serializer):
    """A conversation so far (the browser keeps it; nothing is stored on the server)."""

    messages = ChatMessageSerializer(many=True, allow_empty=False)

    def validate_messages(self, value):
        value = value[-12:]  # recent context is enough, and keeps requests small
        while value and value[0]["role"] != "user":
            value = value[1:]
        if not value or value[-1]["role"] != "user":
            raise serializers.ValidationError("The last message must be a question.")
        if len(value[-1]["content"]) > 500:
            raise serializers.ValidationError("Please keep your question under 500 characters.")
        return value
