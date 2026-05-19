# Generated for GPU ML Workspace Track 1.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("agents", "0006_agentstatusevent"),
    ]

    operations = [
        migrations.CreateModel(
            name="GpuDevice",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("index", models.PositiveSmallIntegerField()),
                ("vendor", models.CharField(default="NVIDIA", max_length=32)),
                ("name", models.CharField(max_length=160)),
                ("uuid", models.CharField(max_length=96, unique=True)),
                ("pci_bus_id", models.CharField(blank=True, default="", max_length=64)),
                ("total_memory_mb", models.PositiveIntegerField()),
                ("driver_version", models.CharField(blank=True, default="", max_length=64)),
                ("cuda_version", models.CharField(blank=True, default="", max_length=64)),
                ("mig_capable", models.BooleanField(default=False)),
                ("mig_enabled", models.BooleanField(default=False)),
                (
                    "status",
                    models.CharField(
                        choices=[("available", "Available"), ("offline", "Offline"), ("error", "Error")],
                        default="available",
                        max_length=16,
                    ),
                ),
                ("last_seen_at", models.DateTimeField(blank=True, null=True)),
                (
                    "agent",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="gpu_devices",
                        to="agents.agent",
                    ),
                ),
            ],
            options={
                "ordering": ["agent_id", "index"],
                "unique_together": {("agent", "index")},
            },
        ),
        migrations.CreateModel(
            name="GpuSlice",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("kind", models.CharField(choices=[("full", "Full GPU"), ("mig", "MIG")], max_length=16)),
                ("device_id", models.CharField(max_length=128, unique=True)),
                ("label", models.CharField(blank=True, default="", max_length=128)),
                ("mig_profile", models.CharField(blank=True, default="", max_length=64)),
                ("memory_mb", models.PositiveIntegerField()),
                ("allow_shared", models.BooleanField(default=False)),
                (
                    "status",
                    models.CharField(
                        choices=[("available", "Available"), ("offline", "Offline"), ("error", "Error")],
                        default="available",
                        max_length=16,
                    ),
                ),
                ("last_seen_at", models.DateTimeField(blank=True, null=True)),
                (
                    "gpu",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="slices",
                        to="agents.gpudevice",
                    ),
                ),
            ],
            options={
                "ordering": ["gpu_id", "kind", "device_id"],
            },
        ),
    ]
