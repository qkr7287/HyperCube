"""HyperCube URL configuration."""

from django.conf import settings
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.views import TokenRefreshView

from apps.users.token_views import CustomTokenObtainPairView, LogoutView


def health_check(request):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", health_check, name="health-check"),
    # API docs (Swagger UI)
    path("api/schema/", SpectacularAPIView.as_view(permission_classes=[AllowAny]), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema", permission_classes=[AllowAny]), name="swagger-ui"),
    # JWT auth
    path("api/auth/token/", CustomTokenObtainPairView.as_view(), name="token-obtain"),
    path("api/auth/token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("api/auth/logout/", LogoutView.as_view(), name="auth-logout"),
    # App APIs
    path("api/", include("apps.agents.urls")),
    path("api/", include("apps.containers.urls")),
    path("api/", include("apps.users.urls")),
    path("api/", include("apps.core.urls")),
]

# Mock API: /api/mock/ prefix로 실제 API와 충돌 방지
if getattr(settings, "MOCK_API_ENABLED", False):
    urlpatterns += [path("api/mock/", include("apps.mock.urls"))]

if settings.DEBUG:
    import debug_toolbar

    urlpatterns += [
        path("__debug__/", include(debug_toolbar.urls)),
    ]
