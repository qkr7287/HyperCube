# Generated for GPU ML Workspace Track 4a.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ModelAsset",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=160)),
                ("slug", models.SlugField(max_length=180, unique=True)),
                ("description", models.TextField(blank=True, default="")),
                (
                    "visibility",
                    models.CharField(
                        choices=[("private", "Private"), ("shared", "Shared")],
                        default="private",
                        max_length=16,
                    ),
                ),
                ("framework", models.CharField(blank=True, default="", max_length=64)),
                ("task", models.CharField(blank=True, default="", max_length=64)),
                ("tags", models.JSONField(blank=True, default=list)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "owner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="model_assets",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["name"],
                "indexes": [
                    models.Index(fields=["owner", "visibility"], name="models_cata_owner_i_05f7b8_idx"),
                    models.Index(fields=["framework", "task"], name="models_cata_framewo_ca5be4_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="ModelVersion",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("version", models.CharField(max_length=80)),
                ("original_filename", models.CharField(max_length=255)),
                ("storage_path", models.CharField(max_length=512)),
                ("size_bytes", models.BigIntegerField(default=0)),
                ("sha256", models.CharField(max_length=64)),
                (
                    "status",
                    models.CharField(
                        choices=[("available", "Available"), ("failed", "Failed")],
                        default="available",
                        max_length=16,
                    ),
                ),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "asset",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="versions",
                        to="models_catalog.modelasset",
                    ),
                ),
                (
                    "uploaded_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="uploaded_model_versions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["asset", "version"], name="models_cata_asset_i_642985_idx"),
                    models.Index(fields=["sha256"], name="models_cata_sha256_b05e1e_idx"),
                    models.Index(fields=["status"], name="models_cata_status_d61acf_idx"),
                ],
                "unique_together": {("asset", "version")},
            },
        ),
    ]
