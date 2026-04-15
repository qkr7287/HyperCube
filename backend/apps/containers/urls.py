from rest_framework.routers import DefaultRouter

from .viewsets import ContainerRequestViewSet, ContainerTemplateViewSet, ContainerViewSet

router = DefaultRouter()
router.register("containers", ContainerViewSet)
router.register("templates", ContainerTemplateViewSet, basename="containertemplate")
router.register("requests", ContainerRequestViewSet, basename="containerrequest")

urlpatterns = router.urls
