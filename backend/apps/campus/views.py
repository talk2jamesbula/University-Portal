from django.utils import timezone
from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import SAFE_METHODS

from apps.accounts.permissions import ReadOnlyOrRequires

from .models import Event
from .selectors import visible_announcements
from .serializers import AnnouncementSerializer, EventSerializer


class AnnouncementViewSet(viewsets.ModelViewSet):
    serializer_class = AnnouncementSerializer
    filterset_fields = ["priority", "offering", "department", "audience"]
    search_fields = ["title", "body"]

    def get_queryset(self):
        return visible_announcements(self.request.user)

    def check_permissions(self, request):
        super().check_permissions(request)
        if request.method not in SAFE_METHODS and not request.user.is_staff_member and not request.user.is_super_admin:
            raise PermissionDenied("Only staff can post announcements.")

    def check_object_permissions(self, request, obj):
        super().check_object_permissions(request, obj)
        editing = request.method not in SAFE_METHODS
        if editing and not request.user.has_permission("communications.send") and obj.author_id != request.user.id:
            raise PermissionDenied("You can only edit your own announcements.")

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)


class EventViewSet(viewsets.ModelViewSet):
    serializer_class = EventSerializer
    permission_classes = [ReadOnlyOrRequires("communications.send")]
    filterset_fields = ["category"]
    search_fields = ["title", "description", "location"]

    def get_queryset(self):
        qs = Event.objects.all()
        if self.request.query_params.get("upcoming") == "true":
            qs = qs.filter(starts_at__gte=timezone.now())
        return qs
