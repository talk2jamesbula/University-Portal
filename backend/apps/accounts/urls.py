from django.urls import path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    AvatarView,
    ChangePasswordView,
    DirectoryView,
    LoginHistoryView,
    LoginView,
    MeView,
    MyLoginHistoryView,
    MyStudentProfileView,
    PermissionCatalogView,
    RoleAssignmentViewSet,
    RoleViewSet,
    UserViewSet,
)

router = DefaultRouter()
router.register("users", UserViewSet)
router.register("roles", RoleViewSet)
router.register("role-assignments", RoleAssignmentViewSet)

urlpatterns = [
    path("auth/token/", LoginView.as_view(), name="token_obtain_pair"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("auth/me/", MeView.as_view(), name="me"),
    path("auth/me/student-profile/", MyStudentProfileView.as_view(), name="me-student-profile"),
    path("auth/me/avatar/", AvatarView.as_view(), name="me-avatar"),
    path("auth/me/logins/", MyLoginHistoryView.as_view(), name="me-logins"),
    path("auth/change-password/", ChangePasswordView.as_view(), name="change_password"),
    path("permissions/", PermissionCatalogView.as_view(), name="permissions"),
    path("login-history/", LoginHistoryView.as_view(), name="login-history"),
    path("directory/", DirectoryView.as_view(), name="directory"),
    *router.urls,
]
