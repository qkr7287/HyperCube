from django.db import migrations, models


def seed_template_weights(apps, schema_editor):
    ContainerTemplate = apps.get_model("containers", "ContainerTemplate")
    defaults = {
        "cpu_weight": 1.0,
        "ram_weight": 1.0,
        "disk_weight": 1.0,
        "min_cpu_percent": 100,
        "min_memory_mb": 2048,
        "min_workspace_gb": 10,
    }

    known_templates = [
        "PyTorch Jupyter GPU Workspace",
        "TensorFlow Jupyter GPU Workspace",
        "CUDA code-server Workspace",
    ]
    ContainerTemplate.objects.filter(name__in=known_templates).update(**defaults)
    ContainerTemplate.objects.filter(name__icontains="PyTorch Jupyter").update(**defaults)

    ContainerTemplate.objects.filter(name__icontains="vLLM").update(
        cpu_weight=1.5,
        ram_weight=1.0,
        disk_weight=0.5,
        min_cpu_percent=100,
        min_memory_mb=4096,
        min_workspace_gb=10,
    )


def noop_reverse(apps, schema_editor):
    return


class Migration(migrations.Migration):
    dependencies = [
        ("containers", "0009_request_target_container_snapshot_name"),
    ]

    operations = [
        migrations.AddField(
            model_name="containertemplate",
            name="cpu_weight",
            field=models.FloatField(default=1.0),
        ),
        migrations.AddField(
            model_name="containertemplate",
            name="ram_weight",
            field=models.FloatField(default=1.0),
        ),
        migrations.AddField(
            model_name="containertemplate",
            name="disk_weight",
            field=models.FloatField(default=1.0),
        ),
        migrations.AddField(
            model_name="containertemplate",
            name="min_cpu_percent",
            field=models.PositiveIntegerField(default=100),
        ),
        migrations.AddField(
            model_name="containertemplate",
            name="min_memory_mb",
            field=models.PositiveIntegerField(default=2048),
        ),
        migrations.AddField(
            model_name="containertemplate",
            name="min_workspace_gb",
            field=models.PositiveIntegerField(default=10),
        ),
        migrations.RunPython(seed_template_weights, noop_reverse),
    ]
