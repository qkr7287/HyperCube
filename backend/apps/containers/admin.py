from django.contrib import admin
from django.utils.html import format_html
from unfold.admin import ModelAdmin

from .models import (
    Container,
    ContainerRequest,
    ContainerRequestGpuSlice,
    ContainerTemplate,
    GpuAllocation,
)


@admin.register(Container)
class ContainerAdmin(ModelAdmin):
    list_display = ("name", "short_id", "image", "agent", "colored_status", "workspace_enabled", "last_seen")
    list_filter = ("status", "agent", "workspace_enabled", "workspace_kind")
    search_fields = ("name", "container_id", "image")

    @admin.display(description="ID")
    def short_id(self, obj):
        return obj.container_id[:12]

    @admin.display(description="Status", ordering="status")
    def colored_status(self, obj):
        colors = {
            "running": "#22c55e",
            "exited": "#ef4444",
            "stopped": "#ef4444",
            "paused": "#f59e0b",
            "created": "#6b7280",
            "restarting": "#3b82f6",
            "dead": "#991b1b",
        }
        color = colors.get(obj.status, "#6b7280")
        return format_html(
            '<span style="color:{}; font-weight:bold;">{}</span>',
            color,
            obj.get_status_display(),
        )


@admin.register(ContainerTemplate)
class ContainerTemplateAdmin(ModelAdmin):
    list_display = ("name", "kind", "category", "requires_gpu", "workspace_enabled", "image", "created_by", "updated_at")
    list_filter = ("kind", "category", "requires_gpu", "workspace_enabled", "workspace_kind")
    search_fields = ("name", "description", "image")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(ContainerRequest)
class ContainerRequestAdmin(ModelAdmin):
    list_display = ("short_id", "requester", "action", "colored_status", "template", "target_agent", "workspace_enabled_snapshot", "created_at")
    list_filter = ("action", "status", "target_agent", "workspace_enabled_snapshot", "workspace_kind_snapshot")
    search_fields = ("custom_name", "requester__username")
    readonly_fields = (
        "id",
        "requester",
        "created_at",
        "updated_at",
        "progress_message",
        "progress_percent",
        "deployment_log",
    )
    date_hierarchy = "created_at"

    @admin.display(description="ID")
    def short_id(self, obj):
        return str(obj.id)[:8]

    @admin.display(description="Status", ordering="status")
    def colored_status(self, obj):
        colors = {
            "pending": "#f59e0b",
            "approved": "#3b82f6",
            "deploying": "#8b5cf6",
            "deployed": "#22c55e",
            "failed": "#ef4444",
            "rejected": "#6b7280",
        }
        color = colors.get(obj.status, "#6b7280")
        return format_html(
            '<span style="color:{}; font-weight:bold;">{}</span>',
            color,
            obj.get_status_display(),
        )


@admin.register(ContainerRequestGpuSlice)
class ContainerRequestGpuSliceAdmin(ModelAdmin):
    list_display = ("request", "slice", "created_at")
    search_fields = ("request__id", "slice__device_id")
    readonly_fields = ("created_at",)


@admin.register(GpuAllocation)
class GpuAllocationAdmin(ModelAdmin):
    list_display = (
        "slice",
        "container_request",
        "container",
        "status",
        "share_mode",
        "reserved_until",
        "activated_at",
        "released_at",
        "failed_at",
    )
    list_filter = ("status", "share_mode")
    search_fields = ("slice__device_id", "container_request__id", "container__container_id")
    readonly_fields = ("requested_at",)
