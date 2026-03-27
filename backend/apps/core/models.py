import uuid

from django.conf import settings
from django.db import models

from apps.agents.models import Agent


class Template(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    category = models.CharField(max_length=50)
    config = models.JSONField(default=dict, help_text="Docker container config (image, ports, volumes, env)")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="templates",
    )
    is_builtin = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "templates"
        ordering = ["category", "name"]

    def __str__(self):
        return f"{self.name} [{self.category}]"


class AlertRule(models.Model):
    class Metric(models.TextChoices):
        CPU = "cpu", "CPU"
        MEMORY = "memory", "Memory"
        DISK = "disk", "Disk"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agent = models.ForeignKey(
        Agent,
        on_delete=models.CASCADE,
        related_name="alert_rules",
        null=True,
        blank=True,
        help_text="Null means global rule",
    )
    metric = models.CharField(max_length=10, choices=Metric.choices)
    threshold = models.FloatField(help_text="Threshold percentage (e.g. 80.0)")
    action = models.CharField(max_length=50, default="notify")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "alert_rules"

    def __str__(self):
        scope = self.agent.hostname if self.agent else "Global"
        return f"{scope} - {self.get_metric_display()} > {self.threshold}%"


class AuditLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="audit_logs",
    )
    action = models.CharField(max_length=100)
    target = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "audit_logs"
        ordering = ["-timestamp"]

    def __str__(self):
        username = self.user.username if self.user else "System"
        return f"{username}: {self.action} → {self.target}"
