from rest_framework import serializers

from .models import Announcement, Event


class AnnouncementSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source="author.get_full_name", read_only=True, default=None)
    course_code = serializers.CharField(source="offering.course.code", read_only=True, default=None)
    department_name = serializers.CharField(source="department.name", read_only=True, default=None)

    class Meta:
        model = Announcement
        fields = [
            "id",
            "title",
            "body",
            "audience",
            "priority",
            "offering",
            "course_code",
            "department",
            "department_name",
            "author",
            "author_name",
            "pinned",
            "is_public",
            "created_at",
        ]
        read_only_fields = ["author", "created_at"]

    def validate(self, attrs):
        """Lecturers post to courses they teach; broader announcements need communications.send."""
        user = self.context["request"].user
        if user.has_permission("communications.send"):
            return attrs
        offering = attrs.get("offering", getattr(self.instance, "offering", None))
        if offering is None or offering.lecturer_id != user.id:
            raise serializers.ValidationError({"offering": "You can only post announcements to courses you teach."})
        if attrs.get("pinned") or attrs.get("department") or attrs.get("is_public"):
            raise serializers.ValidationError(
                "Only communications staff can pin, post department-wide or publish to the website."
            )
        return attrs


class EventSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = ["id", "title", "description", "category", "location", "starts_at", "ends_at", "is_public"]

    def validate(self, attrs):
        starts = attrs.get("starts_at", getattr(self.instance, "starts_at", None))
        ends = attrs.get("ends_at", getattr(self.instance, "ends_at", None))
        if starts and ends and ends < starts:
            raise serializers.ValidationError({"ends_at": "Event cannot end before it starts."})
        return attrs
