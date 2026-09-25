from django.contrib.auth import get_user_model
from django.db.models import Count
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from apps.core.services import audit, client_ip

from .avatars import AvatarError, process_avatar
from .models import LoginEvent, Role, RoleAssignment, StudentProfile
from .permissions import IsMember, IsStudent, Requires
from .rbac import PERMISSIONS
from .serializers import (
    ChangePasswordSerializer,
    DirectorySerializer,
    LoginEventSerializer,
    MeSerializer,
    OwnStudentProfileSerializer,
    RoleAssignmentSerializer,
    RoleSerializer,
    UserSerializer,
)

User = get_user_model()


class LoginView(TokenObtainPairView):
    """JWT sign-in that records every attempt in the login history."""

    def post(self, request, *args, **kwargs):
        username = str(request.data.get("username", ""))[:150]
        successful = False
        try:
            # A wrong password raises here, so the attempt is recorded in `finally`.
            response = super().post(request, *args, **kwargs)
            successful = response.status_code == status.HTTP_200_OK
            return response
        finally:
            user = User.objects.filter(username=username).first()
            LoginEvent.objects.create(
                user=user,
                username=username,
                successful=successful,
                ip_address=client_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", "")[:255],
            )
            if successful and user:
                user.last_login = timezone.now()
                user.save(update_fields=["last_login"])


class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = MeSerializer

    def get_object(self):
        return User.objects.select_related("student_profile__programme__department__faculty", "staff_profile").get(
            pk=self.request.user.pk
        )


class MyStudentProfileView(generics.RetrieveUpdateAPIView):
    """The student's own record. Only contact, next-of-kin and emergency details are editable."""

    serializer_class = OwnStudentProfileSerializer
    permission_classes = [IsStudent]

    def get_object(self):
        return get_object_or_404(StudentProfile, user=self.request.user)


def save_avatar_upload(user, request):
    """Process the "avatar" file in the request and make it `user`'s photo."""
    upload = request.FILES.get("avatar")
    if not upload:
        raise ValidationError({"avatar": "Choose an image to upload."})
    try:
        content = process_avatar(upload)
    except AvatarError as exc:
        raise ValidationError({"avatar": str(exc)}) from exc
    user.set_avatar(content)


class AvatarView(APIView):
    """Upload (POST, multipart field "avatar") or remove (DELETE) the signed-in user's photo."""

    parser_classes = [MultiPartParser]

    def post(self, request):
        save_avatar_upload(request.user, request)
        return Response(MeSerializer(request.user).data)

    def delete(self, request):
        request.user.set_avatar(None)
        return Response(MeSerializer(request.user).data)


class ChangePasswordView(APIView):
    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data["new_password"])
        request.user.save(update_fields=["password"])
        audit(request, "account.password_change", request.user, "Changed their password")
        return Response(status=status.HTTP_204_NO_CONTENT)


class MyLoginHistoryView(generics.ListAPIView):
    serializer_class = LoginEventSerializer

    def get_queryset(self):
        return LoginEvent.objects.filter(user=self.request.user)[:20]

    def paginate_queryset(self, queryset):
        return None


class UserViewSet(viewsets.ModelViewSet):
    """User management for the Registry and super admins."""

    queryset = User.objects.select_related("department")
    serializer_class = UserSerializer
    permission_classes = [Requires("users.manage")]
    filterset_fields = ["role", "department", "is_active"]
    search_fields = ["username", "first_name", "last_name", "email", "university_id"]
    ordering_fields = ["last_name", "date_joined", "university_id"]

    def perform_create(self, serializer):
        user = serializer.save()
        audit(self.request, "user.create", user, f"Created {user.get_role_display().lower()} account {user.username}")

    def perform_update(self, serializer):
        user = serializer.save()
        audit(self.request, "user.update", user, f"Updated account {user.username}")

    @action(detail=True, methods=["post", "delete"], parser_classes=[MultiPartParser])
    def avatar(self, request, pk=None):
        """The Registry sets or removes a user's official photo (e.g. for the website)."""
        user = self.get_object()
        if request.method == "DELETE":
            user.set_avatar(None)
            audit(request, "user.photo_remove", user, f"Removed the photo of {user}")
        else:
            save_avatar_upload(user, request)
            audit(request, "user.photo_upload", user, f"Uploaded a photo for {user}")
        return Response(UserSerializer(user).data)


class RoleViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
    """Staff roles and their permissions. Permissions are editable; roles come from rbac.DEFAULT_ROLES."""

    queryset = Role.objects.annotate(holders=Count("assignments"))
    serializer_class = RoleSerializer
    permission_classes = [Requires("roles.manage")]
    pagination_class = None

    def perform_update(self, serializer):
        role = serializer.save()
        audit(self.request, "role.update", role, f"Changed permissions of {role.name}")


class RoleAssignmentViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    queryset = RoleAssignment.objects.select_related("user", "role", "faculty", "department")
    serializer_class = RoleAssignmentSerializer
    permission_classes = [Requires("roles.manage")]
    filterset_fields = ["user", "role", "faculty", "department"]

    def perform_create(self, serializer):
        assignment = serializer.save()
        audit(self.request, "role.assign", assignment, f"Appointed {assignment}")

    def perform_destroy(self, instance):
        audit(self.request, "role.revoke", instance, f"Removed appointment {instance}")
        instance.delete()


class PermissionCatalogView(APIView):
    permission_classes = [Requires("roles.manage")]

    def get(self, request):
        return Response([{"code": code, "description": text} for code, text in PERMISSIONS.items()])


class LoginHistoryView(generics.ListAPIView):
    """Everyone's sign-in attempts, for security review."""

    queryset = LoginEvent.objects.select_related("user")
    serializer_class = LoginEventSerializer
    permission_classes = [Requires("audit.view")]
    filterset_fields = ["successful", "user"]
    search_fields = ["username", "ip_address"]


class DirectoryView(generics.ListAPIView):
    """Staff directory visible to students and staff."""

    permission_classes = [IsMember]

    serializer_class = DirectorySerializer
    filterset_fields = ["department"]
    search_fields = ["first_name", "last_name", "email", "department__name", "staff_profile__designation"]

    def get_queryset(self):
        return User.objects.filter(is_active=True, role=User.Role.STAFF).select_related("department", "staff_profile")
