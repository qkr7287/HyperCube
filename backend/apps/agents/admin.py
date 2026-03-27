from django.contrib import admin

from .models import Agent, ServerAssignment


@admin.register(Agent)
class AgentAdmin(admin.ModelAdmin):
    list_display = ("hostname", "ip_address", "status", "registered_at", "approved_at")
    list_filter = ("status",)
    search_fields = ("hostname", "ip_address")
    readonly_fields = ("id", "registered_at")


@admin.register(ServerAssignment)
class ServerAssignmentAdmin(admin.ModelAdmin):
    list_display = ("user", "agent", "created_at")
    list_filter = ("agent",)
