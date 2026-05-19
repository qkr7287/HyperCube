# Generated for GPU ML Workspace Track 4b.

import django.db.models.deletion
from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("agents", "0007_gpu_inventory"),
        ("containers", "0006_workspace_and_jupyter"),
        ("models_catalog", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ModelVersionCache",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("missing", "Missing"),
                            ("preparing", "Preparing"),
                            ("ready", "Ready"),
                            ("failed", "Failed"),
                        ],
                        default="missing",
                        max_length=16,
                    ),
                ),
                ("cache_path", models.CharField(blank=True, default="", max_length=512)),
                ("size_bytes", models.BigIntegerField(default=0)),
                ("sha256", models.CharField(blank=True, default="", max_length=64)),
                ("last_verified_at", models.DateTimeField(blank=True, null=True)),
                ("lease_expires_at", models.DateTimeField(blank=True, null=True)),
                ("last_error", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "agent",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="model_version_caches",
                        to="agents.agent",
                    ),
                ),
                (
                    "version",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="agent_caches",
                        to="models_catalog.modelversion",
                    ),
                ),
            ],
            options={
                "indexes": [
                    models.Index(fields=["agent", "status"], name="mvcache_agent_status_idx"),
                    models.Index(fields=["version", "status"], name="mvcache_version_status_idx"),
                    models.Index(fields=["lease_expires_at"], name="mvcache_lease_expires_idx"),
                ],
                "unique_together": {("agent", "version")},
            },
        ),
        migrations.CreateModel(
            name="ModelPrepareJob",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("queued", "Queued"),
                            ("dispatched", "Dispatched"),
                            ("preparing", "Preparing"),
                            ("ready", "Ready"),
                            ("failed", "Failed"),
                            ("stale", "Stale"),
                        ],
                        default="queued",
                        max_length=16,
                    ),
                ),
                (
                    "transfer_mode",
                    models.CharField(
                        choices=[
                            ("backend_stream", "Backend stream"),
                            ("preseeded", "Preseeded"),
                            ("nas_copy", "NAS copy"),
                        ],
                        default="backend_stream",
                        max_length=24,
                    ),
                ),
                ("progress_percent", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("progress_message", models.TextField(blank=True, default="")),
                ("bytes_total", models.BigIntegerField(default=0)),
                ("bytes_done", models.BigIntegerField(default=0)),
                ("lease_expires_at", models.DateTimeField(blank=True, null=True)),
                ("dispatched_at", models.DateTimeField(blank=True, null=True)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("failed_at", models.DateTimeField(blank=True, null=True)),
                ("error", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "agent",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="model_prepare_jobs",
                        to="agents.agent",
                    ),
                ),
                (
                    "cache",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="prepare_jobs",
                        to="models_catalog.modelversioncache",
                    ),
                ),
                (
                    "version",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="prepare_jobs",
                        to="models_catalog.modelversion",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["agent", "version", "status"], name="mpjob_agent_ver_status_idx"),
                    models.Index(fields=["status", "lease_expires_at"], name="mpjob_status_lease_idx"),
                    models.Index(fields=["created_at"], name="mpjob_created_at_idx"),
                ],
            },
        ),
        migrations.AddField(
            model_name="modelpreparejob",
            name="waiting_requests",
            field=models.ManyToManyField(
                blank=True,
                related_name="model_prepare_jobs",
                to="containers.containerrequest",
            ),
        ),
    ]
