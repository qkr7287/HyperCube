from rest_framework.routers import DefaultRouter

from .viewsets import AgentViewSet

router = DefaultRouter()
router.register("agents", AgentViewSet)

urlpatterns = router.urls
