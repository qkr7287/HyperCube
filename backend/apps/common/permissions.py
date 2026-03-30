from rest_framework.permissions import BasePermission


class IsSuperAdmin(BasePermission):
    """super_admin 전용"""

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == "super_admin"
        )


class IsServerAdminOrAbove(BasePermission):
    """server_admin 이상"""

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role in ("super_admin", "server_admin")
        )


class IsViewer(BasePermission):
    """인증된 사용자 (viewer 이상)"""

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated
