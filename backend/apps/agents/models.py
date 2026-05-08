import uuid

from django.db import models


class AgentStatusEvent(models.Model):
    """Persistent log of agent online/offline transitions.

    Backend pushes a Channels-layer event for every transition, but that
    is volatile — if no browser tab is subscribed at the moment of the
    event (e.g. the whole stack just rebooted, or the operator was
    asleep) the event is lost and the dashboard's "최근 상태 변화" panel
    has no idea anything happened. This table is the durable record so
    the panel can replay the last N transitions on mount and 1/N agent
    outages don't disappear silently.

    Why a separate table instead of bolting onto Agent: a single agent
    flips state many times over its lifetime, so the history is
    inherently 1:N. Keeping it append-only also makes the SLA queries
    ("how many minutes was server_63_dev offline yesterday?") trivial.
    """

    class Status(models.TextChoices):
        ONLINE = "online", "Online"
        OFFLINE = "offline", "Offline"

    id = models.BigAutoField(primary_key=True)
    agent = models.ForeignKey(
        "agents.Agent",
        on_delete=models.CASCADE,
        related_name="status_events",
    )
    # Snapshot of the hostname AT TRANSITION TIME so the history stays
    # readable even if the agent is later renamed or hard-deleted via
    # cascade is unlikely (CASCADE drops history along with the agent).
    hostname = models.CharField(max_length=255)
    status = models.CharField(max_length=10, choices=Status.choices)
    occurred_at = models.DateTimeField(db_index=True)
    # For online events, how long the previous offline gap was (seconds).
    # For offline events, null. Lets the UI render "재연결 (12분 끊김)"
    # without doing pairwise queries on the client.
    previous_offline_seconds = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "agent_status_events"
        ordering = ["-occurred_at"]
        indexes = [
            models.Index(fields=["-occurred_at"]),
            models.Index(fields=["agent", "-occurred_at"]),
        ]

    def __str__(self):
        return f"{self.hostname} {self.status} @ {self.occurred_at.isoformat()}"


class Agent(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        ARCHIVED = "archived", "Archived"

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
    last_seen_at = models.DateTimeField(null=True, blank=True, db_index=True)
    archived_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "agents"
        ordering = ["-registered_at"]

    def __str__(self):
        return f"{self.hostname} ({self.ip_address}) - {self.get_status_display()}"


