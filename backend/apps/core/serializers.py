from rest_framework import serializers

from .models import AuditLog, Notification


class NotificationSerializer(serializers.ModelSerializer):
    category_label = serializers.CharField(source="get_category_display", read_only=True)
    is_read = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = ["id", "category", "category_label", "title", "body", "link", "is_read", "read_at", "created_at"]
        read_only_fields = fields

    def get_is_read(self, obj):
        return obj.read_at is not None


class AuditLogSerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source="actor.get_full_name", read_only=True, default=None)

    class Meta:
        model = AuditLog
        fields = [
            "id",
            "actor",
            "actor_name",
            "action",
            "target_type",
            "target_id",
            "summary",
            "ip_address",
            "created_at",
        ]
        read_only_fields = fields
