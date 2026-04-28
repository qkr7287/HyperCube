from rest_framework.routers import DefaultRouter

from .viewsets import ContainerMetricsViewSet, StackMetricsViewSet, SystemMetricsViewSet

router = DefaultRouter()
router.register("metrics/system", SystemMetricsViewSet, basename="system-metrics")
router.register("metrics/containers", ContainerMetricsViewSet, basename="container-metrics")
router.register("metrics/stacks", StackMetricsViewSet, basename="stack-metrics")

urlpatterns = router.urls
