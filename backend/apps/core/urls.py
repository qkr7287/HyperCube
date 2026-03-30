from rest_framework.routers import DefaultRouter

from .viewsets import AlertRuleViewSet, AuditLogViewSet, TemplateViewSet

router = DefaultRouter()
router.register("templates", TemplateViewSet)
router.register("alert-rules", AlertRuleViewSet)
router.register("audit-logs", AuditLogViewSet)

urlpatterns = router.urls
