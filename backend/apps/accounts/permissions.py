"""DRF permission classes built on the RBAC permission codes in accounts.rbac."""

from rest_framework.permissions import SAFE_METHODS, BasePermission


def _signed_in(request):
    return bool(request.user and request.user.is_authenticated)


class IsStudent(BasePermission):
    message = "Only students can do this."

    def has_permission(self, request, view):
        return _signed_in(request) and request.user.is_student


class IsApplicant(BasePermission):
    message = "Only applicants can do this."

    def has_permission(self, request, view):
        return _signed_in(request) and request.user.is_applicant


class IsMember(BasePermission):
    """Students, staff and admins: members of the university, not applicants."""

    message = "This is only available to students and staff."

    def has_permission(self, request, view):
        return _signed_in(request) and not request.user.is_applicant


class IsSuperAdmin(BasePermission):
    def has_permission(self, request, view):
        return _signed_in(request) and request.user.is_super_admin


def Requires(*codes):
    """Permission class granting access to users holding any of the permission codes.

    permission_classes = [Requires("finance.manage")]
    """

    class _Requires(BasePermission):
        message = "You don't have permission to do this."

        def has_permission(self, request, view):
            return _signed_in(request) and request.user.has_permission(*codes)

    _Requires.__name__ = f"Requires({', '.join(codes)})"
    return _Requires


def ReadOnlyOrRequires(*codes):
    """Any signed-in user may read; writing needs one of the permission codes."""

    class _ReadOnlyOrRequires(BasePermission):
        def has_permission(self, request, view):
            if not _signed_in(request):
                return False
            return request.method in SAFE_METHODS or request.user.has_permission(*codes)

    _ReadOnlyOrRequires.__name__ = f"ReadOnlyOrRequires({', '.join(codes)})"
    return _ReadOnlyOrRequires


def StudentOrRequires(*codes):
    """Students (for their own records) or staff holding one of the permission codes."""

    class _StudentOrRequires(BasePermission):
        message = "This is only available to the student and authorised staff."

        def has_permission(self, request, view):
            return _signed_in(request) and (request.user.is_student or request.user.has_permission(*codes))

    _StudentOrRequires.__name__ = f"StudentOrRequires({', '.join(codes)})"
    return _StudentOrRequires
