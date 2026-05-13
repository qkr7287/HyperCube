from rest_framework.routers import DefaultRouter

from .viewsets import (
    ContainerRequestViewSet,
    ContainerTemplateViewSet,
    ContainerViewSet,
    MyContainerViewSet,
    WorkspaceViewSet,
)

router = DefaultRouter()
router.register("containers", ContainerViewSet)
router.register("my-containers", MyContainerViewSet, basename="mycontainer")
router.register("workspaces", WorkspaceViewSet, basename="workspace")
router.register("templates", ContainerTemplateViewSet, basename="containertemplate")
router.register("requests", ContainerRequestViewSet, basename="containerrequest")

urlpatterns = router.urls
