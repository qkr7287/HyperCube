from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import AlertRule, AuditLog, Template


@admin.register(Template)
class TemplateAdmin(ModelAdmin):
    list_display = ("name", "category", "created_by", "is_builtin", "created_at")
    list_filter = ("category", "is_builtin")
    search_fields = ("name",)
    readonly_fields = ("created_at",)


@admin.register(AlertRule)
class AlertRuleAdmin(ModelAdmin):
    list_display = ("agent", "metric", "threshold", "action", "created_at")
    list_filter = ("metric", "agent")
    readonly_fields = ("created_at",)


@admin.register(AuditLog)
class AuditLogAdmin(ModelAdmin):
    list_display = ("user", "action", "target", "timestamp")
    list_filter = ("action",)
    search_fields = ("action", "target")
    readonly_fields = ("id", "user", "action", "target", "timestamp")
    date_hierarchy = "timestamp"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
