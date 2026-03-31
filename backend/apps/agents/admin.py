from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html

from .models import Agent, ServerAssignment

admin.site.site_header = "HyperCube Admin"
admin.site.site_title = "HyperCube"
admin.site.index_title = "Dashboard"


@admin.register(Agent)
class AgentAdmin(admin.ModelAdmin):
    list_display = ("hostname", "ip_address", "colored_status", "registered_at", "approved_at")
    list_filter = ("status",)
    search_fields = ("hostname", "ip_address")
    readonly_fields = ("id", "registered_at")
    actions = ["approve_agents", "reject_agents"]

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

    @admin.action(description="Approve selected agents")
    def approve_agents(self, request, queryset):
        count = queryset.filter(status="pending").update(
            status="approved", approved_at=timezone.now()
        )
        self.message_user(request, f"{count} agent(s) approved.")

    @admin.action(description="Reject selected agents")
    def reject_agents(self, request, queryset):
        count = queryset.filter(status="pending").update(status="rejected")
        self.message_user(request, f"{count} agent(s) rejected.")


@admin.register(ServerAssignment)
class ServerAssignmentAdmin(admin.ModelAdmin):
    list_display = ("user", "agent", "created_at")
    list_filter = ("agent",)
    autocomplete_fields = ("user", "agent")
