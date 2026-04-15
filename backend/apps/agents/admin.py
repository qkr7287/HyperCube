from django.contrib import admin
from django.utils.html import format_html
from unfold.admin import ModelAdmin

from .models import Agent, ServerAssignment

admin.site.site_header = "HyperCube Admin"
admin.site.site_title = "HyperCube"
admin.site.index_title = "Dashboard"


@admin.register(Agent)
class AgentAdmin(ModelAdmin):
    list_display = ("hostname", "ip_address", "colored_status", "registered_at", "approved_at")
    list_filter = ("status",)
    search_fields = ("hostname", "ip_address")
    readonly_fields = ("id", "registered_at")

    @admin.display(description="Status", ordering="status")
    def colored_status(self, obj):
        colors = {
            "approved": "#22c55e",
            "pending": "#f59e0b",
            "rejected": "#ef4444",
        }
        color = colors.get(obj.status, "#6b7280")
        return format_html(
            '<span style="color:{}; font-weight:bold;">{}</span>',
            color,
            obj.get_status_display(),
        )


@admin.register(ServerAssignment)
class ServerAssignmentAdmin(ModelAdmin):
    list_display = ("user", "agent", "created_at")
    list_filter = ("agent",)
    autocomplete_fields = ("user", "agent")
