import django.db.models.deletion
import uuid

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("containers", "0013_template_default_models"),
        ("models_catalog", "0002_model_prepare"),
    ]

    operations = [
        migrations.CreateModel(
            name="ModelUploadRequest",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=160)),
                ("slug", models.SlugField(blank=True, default="", max_length=180)),
                ("description", models.TextField(blank=True, default="")),
                ("framework", models.CharField(blank=True, default="", max_length=64)),
                ("task", models.CharField(blank=True, default="", max_length=64)),
                ("tags", models.JSONField(blank=True, default=list)),
                ("version", models.CharField(default="v1", max_length=80)),
                ("template_name", models.CharField(blank=True, default="", max_length=100)),
                ("template_description", models.TextField(blank=True, default="")),
                (
                    "base_image",
                    models.CharField(default="hypercube/ml-pytorch-jupyter:cuda12.4-airgap", max_length=255),
                ),
                ("requires_gpu", models.BooleanField(default=True)),
                ("workspace_kind", models.CharField(blank=True, default="jupyter", max_length=32)),
                ("workspace_port", models.PositiveIntegerField(default=8888)),
                ("default_max_runtime_hours", models.PositiveIntegerField(blank=True, default=24, null=True)),
                ("min_cpu_percent", models.PositiveIntegerField(default=100)),
                ("min_memory_mb", models.PositiveIntegerField(default=2048)),
                ("min_workspace_gb", models.PositiveIntegerField(default=10)),
                ("original_filename", models.CharField(blank=True, default="", max_length=255)),
                ("upload_storage_path", models.CharField(blank=True, default="", max_length=512)),
                ("size_bytes", models.BigIntegerField(default=0)),
                ("sha256", models.CharField(blank=True, default="", max_length=64)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("approved", "Approved"),
                            ("rejected", "Rejected"),
                            ("failed", "Failed"),
                        ],
                        default="pending",
                        max_length=16,
                    ),
                ),
                ("review_note", models.TextField(blank=True, default="")),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_asset",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="source_upload_requests",
                        to="models_catalog.modelasset",
                    ),
                ),
                (
                    "created_template",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="source_model_upload_requests",
                        to="containers.containertemplate",
                    ),
                ),
                (
                    "created_version",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="source_upload_requests",
                        to="models_catalog.modelversion",
                    ),
                ),
                (
                    "requester",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="model_upload_requests",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "reviewer",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="reviewed_model_upload_requests",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="modeluploadrequest",
            index=models.Index(fields=["requester", "status"], name="models_cata_request_6d403d_idx"),
        ),
        migrations.AddIndex(
            model_name="modeluploadrequest",
            index=models.Index(fields=["status", "-created_at"], name="models_cata_status_48aaae_idx"),
        ),
        migrations.AddIndex(
            model_name="modeluploadrequest",
            index=models.Index(fields=["slug"], name="models_cata_slug_9a8f04_idx"),
        ),
    ]
