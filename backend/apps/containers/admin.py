from django.contrib import admin
from django.utils.html import format_html

from .models import Container


@admin.register(Container)
class ContainerAdmin(admin.ModelAdmin):
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
