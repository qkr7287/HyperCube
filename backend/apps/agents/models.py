import uuid

from django.conf import settings
from django.db import models


class Agent(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hostname = models.CharField(max_length=255, unique=True)
    ip_address = models.GenericIPAddressField()
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.APPROVED,
    )
    token = models.CharField(max_length=500, blank=True, default="")
    registered_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "agents"
        ordering = ["-registered_at"]

    def __str__(self):
        return f"{self.hostname} ({self.ip_address}) - {self.get_status_display()}"


class ServerAssignment(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="server_assignments",
    )
    agent = models.ForeignKey(
        Agent,
        on_delete=models.CASCADE,
        related_name="server_assignments",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "server_assignments"
        unique_together = [("user", "agent")]

    def __str__(self):
        return f"{self.user.username} → {self.agent.hostname}"
