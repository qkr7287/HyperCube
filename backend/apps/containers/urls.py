from django.urls import path
from rest_framework.routers import DefaultRouter

from .viewsets import (
    ContainerRequestViewSet,
    ContainerTemplateViewSet,
    ContainerViewSet,
    LauncherRecipeListView,
    MyContainerViewSet,
    WorkspaceViewSet,
)

router = DefaultRouter()
router.register("containers", ContainerViewSet)
router.register("my-containers", MyContainerViewSet, basename="mycontainer")
router.register("workspaces", WorkspaceViewSet, basename="workspace")
router.register("templates", ContainerTemplateViewSet, basename="containertemplate")
router.register("requests", ContainerRequestViewSet, basename="containerrequest")

urlpatterns = router.urls + [
    path("launcher-recipes/", LauncherRecipeListView.as_view(), name="launcher-recipes"),
]
