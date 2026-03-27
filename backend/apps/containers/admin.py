from django.contrib import admin

from .models import Container


@admin.register(Container)
class ContainerAdmin(admin.ModelAdmin):
    list_display = ("name", "container_id", "image", "agent", "status", "last_seen")
    list_filter = ("status", "agent")
    search_fields = ("name", "container_id", "image")
