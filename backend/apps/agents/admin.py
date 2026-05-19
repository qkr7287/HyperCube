from django.contrib import admin
from django.utils.html import format_html
from unfold.admin import ModelAdmin

from .models import Agent, GpuDevice, GpuSlice

admin.site.site_header = "HyperCube Admin"
admin.site.site_title = "HyperCube"
admin.site.index_title = "Dashboard"


@admin.register(Agent)
class AgentAdmin(ModelAdmin):
    list_display = (
        "hostname",
        "ip_address",
        "colored_status",
        "cpu_cores",
        "ram_total_mb",
        "workspace_pool_total_gb",
        "workspace_pool_free_gb",
        "workspace_hard_enforcement",
        "capacity_updated_at",
        "registered_at",
        "approved_at",
    )
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


@admin.register(GpuDevice)
class GpuDeviceAdmin(ModelAdmin):
    list_display = (
        "agent",
        "index",
        "name",
        "uuid",
        "total_memory_mb",
        "mig_enabled",
        "status",
        "last_seen_at",
    )
    list_filter = ("status", "vendor", "mig_enabled")
    search_fields = ("agent__hostname", "name", "uuid", "pci_bus_id")
    readonly_fields = ("last_seen_at",)


@admin.register(GpuSlice)
class GpuSliceAdmin(ModelAdmin):
    list_display = (
        "gpu",
        "kind",
        "device_id",
        "mig_profile",
        "memory_mb",
        "allow_shared",
        "status",
        "last_seen_at",
    )
    list_filter = ("kind", "status", "allow_shared")
    search_fields = ("gpu__agent__hostname", "gpu__name", "device_id", "mig_profile")
    readonly_fields = ("last_seen_at",)


