from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import ContainerMetricsHistory, SystemMetricsHistory


@admin.register(SystemMetricsHistory)
class SystemMetricsHistoryAdmin(ModelAdmin):
    list_display = ("agent", "cpu_usage", "memory_usage", "disk_usage", "recorded_at")
    list_filter = ("agent",)
    readonly_fields = ("id", "raw_data", "recorded_at")
    date_hierarchy = "recorded_at"
    search_fields = ("agent__hostname",)


@admin.register(ContainerMetricsHistory)
class ContainerMetricsHistoryAdmin(ModelAdmin):
    list_display = (
        "short_container_id",
        "agent",
        "cpu_usage",
        "memory_percent",
        "recorded_at",
    )
    list_filter = ("agent",)
    readonly_fields = ("id", "raw_data", "recorded_at")
    date_hierarchy = "recorded_at"
    search_fields = ("container_id", "agent__hostname")

    @admin.display(description="Container")
    def short_container_id(self, obj):
        return obj.container_id[:12]
