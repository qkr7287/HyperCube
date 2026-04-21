from rest_framework.permissions import BasePermission

# 2단계 role 모델 (admin / user) 이후:
# - IsAdmin: 운영자 전용 (서버 모니터링, 요청 승인/반려, 템플릿 관리, /dev 접근)
# - IsAuthenticated: 로그인한 모든 사용자 (자기 컨테이너 요청/조회)
#
# 과거 3단계 (super_admin / server_admin / viewer) 시절의 별칭은 하위 호환용으로 유지.


class IsAdmin(BasePermission):
    """admin 전용"""

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == "admin"
        )


class IsAuthenticatedUser(BasePermission):
    """로그인한 모든 사용자 (admin + user)"""

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated


# ---- 하위 호환 별칭 (기존 코드 레퍼런스용; 점진 교체) ----
IsSuperAdmin = IsAdmin
IsServerAdminOrAbove = IsAdmin
IsViewer = IsAuthenticatedUser
