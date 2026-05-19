from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import ModelAsset, ModelPrepareJob, ModelUploadRequest, ModelVersion, ModelVersionCache


@admin.register(ModelAsset)
class ModelAssetAdmin(ModelAdmin):
    list_display = ("name", "slug", "owner", "visibility", "framework", "task", "created_at")
    list_filter = ("visibility", "framework", "task")
    search_fields = ("name", "slug", "description", "owner__username")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(ModelVersion)
class ModelVersionAdmin(ModelAdmin):
    list_display = ("asset", "version", "status", "size_bytes", "sha256", "created_at")
    list_filter = ("status",)
    search_fields = ("asset__name", "asset__slug", "version", "sha256", "original_filename")
    readonly_fields = ("id", "storage_path", "size_bytes", "sha256", "created_at")


@admin.register(ModelUploadRequest)
class ModelUploadRequestAdmin(ModelAdmin):
    list_display = ("name", "version", "requester", "status", "size_bytes", "created_template", "created_at")
    list_filter = ("status", "framework", "task", "requires_gpu")
    search_fields = ("name", "slug", "description", "requester__username", "original_filename", "sha256")
    readonly_fields = (
        "id",
        "original_filename",
        "upload_storage_path",
        "size_bytes",
        "sha256",
        "created_asset",
        "created_version",
        "created_template",
        "created_at",
        "updated_at",
    )


@admin.register(ModelVersionCache)
class ModelVersionCacheAdmin(ModelAdmin):
    list_display = ("version", "agent", "status", "size_bytes", "last_verified_at", "updated_at")
    list_filter = ("status", "agent")
    search_fields = ("version__asset__name", "version__asset__slug", "version__version", "agent__hostname", "cache_path")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(ModelPrepareJob)
class ModelPrepareJobAdmin(ModelAdmin):
    list_display = ("version", "agent", "status", "progress_percent", "transfer_mode", "created_at", "updated_at")
    list_filter = ("status", "transfer_mode", "agent")
    search_fields = ("version__asset__name", "version__asset__slug", "version__version", "agent__hostname", "error")
    readonly_fields = ("id", "created_at", "updated_at")
