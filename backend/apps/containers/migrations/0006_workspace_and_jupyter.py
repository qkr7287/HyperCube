# Generated for GPU ML Workspace Track 3.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("containers", "0005_gpu_allocation"),
    ]

    operations = [
        migrations.AddField(
            model_name="containertemplate",
            name="category",
            field=models.CharField(
                choices=[("general", "General"), ("ml", "ML")],
                default="general",
                max_length=24,
            ),
        ),
        migrations.AddField(
            model_name="containertemplate",
            name="requires_gpu",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="containertemplate",
            name="workspace_enabled",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="containertemplate",
            name="workspace_kind",
            field=models.CharField(
                blank=True,
                choices=[
                    ("jupyter", "Jupyter"),
                    ("code-server", "code-server"),
                    ("api", "API"),
                ],
                default="",
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="containertemplate",
            name="workspace_port",
            field=models.PositiveIntegerField(blank=True, default=8888, null=True),
        ),
        migrations.AddField(
            model_name="containertemplate",
            name="default_workdir",
            field=models.CharField(blank=True, default="/workspace", max_length=255),
        ),
        migrations.AddField(
            model_name="containertemplate",
            name="network_policy",
            field=models.CharField(
                choices=[
                    ("internal_only", "Internal only"),
                    ("none", "None"),
                    ("custom", "Custom"),
                ],
                default="internal_only",
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="containertemplate",
            name="default_max_runtime_hours",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="containerrequest",
            name="model_version_ids",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="containerrequest",
            name="workspace_enabled_snapshot",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="containerrequest",
            name="workspace_kind_snapshot",
            field=models.CharField(blank=True, default="", max_length=32),
        ),
        migrations.AddField(
            model_name="containerrequest",
            name="requested_max_runtime_hours",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="containerrequest",
            name="prepare_job_ids",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="containerrequest",
            name="deployment_phase",
            field=models.CharField(blank=True, default="", max_length=32),
        ),
        migrations.AddField(
            model_name="containerrequest",
            name="workspace_token_ref",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.AddField(
            model_name="containerrequest",
            name="workspace_token_expires_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="container",
            name="mounted_model_version_ids",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="container",
            name="workspace_enabled",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="container",
            name="workspace_kind",
            field=models.CharField(blank=True, default="", max_length=32),
        ),
        migrations.AddField(
            model_name="container",
            name="workspace_internal_port",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="container",
            name="workspace_host_port",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="container",
            name="workspace_base_url",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="container",
            name="workspace_health",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="container",
            name="workspace_max_runtime_hours",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="container",
            name="workspace_runtime_expires_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="container",
            name="workspace_token_ref",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.AddField(
            model_name="container",
            name="workspace_token_expires_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
