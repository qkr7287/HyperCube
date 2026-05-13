# Generated for GPU ML Workspace Track 2.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("agents", "0007_gpu_inventory"),
        ("containers", "0004_consolesession"),
    ]

    operations = [
        migrations.AddField(
            model_name="container",
            name="allocated_gpu_slice_ids",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="containerrequest",
            name="gpu_share_ok",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="containerrequest",
            name="gpu_slice_ids_snapshot",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.CreateModel(
            name="ContainerRequestGpuSlice",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "request",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="gpu_slice_selections",
                        to="containers.containerrequest",
                    ),
                ),
                (
                    "slice",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="request_selections",
                        to="agents.gpuslice",
                    ),
                ),
            ],
            options={
                "indexes": [
                    models.Index(fields=["request", "slice"], name="containers__request_4393a5_idx"),
                ],
                "unique_together": {("request", "slice")},
            },
        ),
        migrations.CreateModel(
            name="GpuAllocation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("reserved", "Reserved"),
                            ("active", "Active"),
                            ("released", "Released"),
                            ("failed", "Failed"),
                        ],
                        default="reserved",
                        max_length=16,
                    ),
                ),
                (
                    "share_mode",
                    models.CharField(
                        choices=[("exclusive", "Exclusive"), ("shared", "Shared")],
                        default="exclusive",
                        max_length=16,
                    ),
                ),
                ("requested_at", models.DateTimeField(auto_now_add=True)),
                ("reserved_until", models.DateTimeField(blank=True, null=True)),
                ("activated_at", models.DateTimeField(blank=True, null=True)),
                ("released_at", models.DateTimeField(blank=True, null=True)),
                ("failed_at", models.DateTimeField(blank=True, null=True)),
                ("failure_reason", models.TextField(blank=True, default="")),
                (
                    "container",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="gpu_allocations",
                        to="containers.container",
                    ),
                ),
                (
                    "container_request",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="gpu_allocations",
                        to="containers.containerrequest",
                    ),
                ),
                (
                    "slice",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="allocations",
                        to="agents.gpuslice",
                    ),
                ),
            ],
            options={
                "indexes": [
                    models.Index(fields=["slice", "status"], name="containers__slice_i_5d23cd_idx"),
                    models.Index(fields=["container_request", "status"], name="containers__contain_c2e70f_idx"),
                    models.Index(fields=["container", "status"], name="containers__contain_a47d6a_idx"),
                ],
            },
        ),
    ]
