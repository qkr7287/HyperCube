from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from apps.agents.models import ServerAssignment

from .models import CustomUser


class ServerAssignmentInline(admin.TabularInline):
    """User 편집 화면에서 서버 할당을 인라인 편집"""

    model = ServerAssignment
    extra = 0
    autocomplete_fields = ("agent",)


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ("username", "email", "role", "is_active", "date_joined")
    list_filter = ("role", "is_active", "is_staff")
    fieldsets = UserAdmin.fieldsets + (
        ("Role", {"fields": ("role",)}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Role", {"fields": ("role",)}),
    )
    inlines = [ServerAssignmentInline]
