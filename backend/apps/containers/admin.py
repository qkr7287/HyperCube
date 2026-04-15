from django.contrib import admin
from django.utils.html import format_html
from unfold.admin import ModelAdmin

from .models import Container, ContainerRequest, ContainerTemplate


@admin.register(Container)
class ContainerAdmin(ModelAdmin):
    list_display = ("name", "short_id", "image", "agent", "colored_status", "last_seen")
    list_filter = ("status", "agent")
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
    list_display = ("name", "kind", "image", "created_by", "updated_at")
    list_filter = ("kind",)
    search_fields = ("name", "description", "image")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(ContainerRequest)
class ContainerRequestAdmin(ModelAdmin):
    list_display = ("short_id", "requester", "action", "colored_status", "template", "target_agent", "created_at")
    list_filter = ("action", "status", "target_agent")
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
