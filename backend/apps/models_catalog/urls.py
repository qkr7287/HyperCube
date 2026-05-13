from rest_framework.routers import DefaultRouter

from .viewsets import (
    ModelAssetViewSet,
    ModelPrepareJobViewSet,
    ModelVersionCacheViewSet,
    ModelVersionViewSet,
)

router = DefaultRouter()
router.register("model-assets", ModelAssetViewSet, basename="modelasset")
router.register("model-versions", ModelVersionViewSet, basename="modelversion")
router.register("model-version-caches", ModelVersionCacheViewSet, basename="modelversioncache")
router.register("model-prepare-jobs", ModelPrepareJobViewSet, basename="modelpreparejob")

urlpatterns = router.urls
