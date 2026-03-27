from django.db import models

from apps.agents.models import Agent


class Container(models.Model):
    class Status(models.TextChoices):
        RUNNING = "running", "Running"
        STOPPED = "stopped", "Stopped"
        PAUSED = "paused", "Paused"
        EXITED = "exited", "Exited"
        CREATED = "created", "Created"
        RESTARTING = "restarting", "Restarting"
        DEAD = "dead", "Dead"

    container_id = models.CharField(max_length=64, primary_key=True)
    name = models.CharField(max_length=255)
    image = models.CharField(max_length=255)
    agent = models.ForeignKey(
        Agent,
        on_delete=models.CASCADE,
        related_name="containers",
    )
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.CREATED,
    )
    last_seen = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "containers"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.get_status_display()}) @ {self.agent.hostname}"
