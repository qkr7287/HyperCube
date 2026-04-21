from rest_framework.routers import DefaultRouter

from .viewsets import ContainerMetricsViewSet, SystemMetricsViewSet

router = DefaultRouter()
router.register("metrics/system", SystemMetricsViewSet, basename="system-metrics")
router.register("metrics/containers", ContainerMetricsViewSet, basename="container-metrics")

urlpatterns = router.urls
