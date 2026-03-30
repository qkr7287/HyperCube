from rest_framework.routers import DefaultRouter

from .viewsets import ContainerViewSet

router = DefaultRouter()
router.register("containers", ContainerViewSet)

urlpatterns = router.urls
