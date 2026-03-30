from rest_framework.routers import DefaultRouter

from .viewsets import AgentViewSet, ServerAssignmentViewSet

router = DefaultRouter()
router.register("agents", AgentViewSet)
router.register("server-assignments", ServerAssignmentViewSet)

urlpatterns = router.urls
