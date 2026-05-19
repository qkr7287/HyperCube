from django.db import migrations, models


def backfill_snapshot_names(apps, schema_editor):
    ContainerRequest = apps.get_model("containers", "ContainerRequest")
    qs = ContainerRequest.objects.filter(
        action="delete", target_container__isnull=False
    ).select_related("target_container")
    for req in qs.iterator():
        name = getattr(req.target_container, "name", "") or ""
        if name and not req.target_container_snapshot_name:
            req.target_container_snapshot_name = name
            req.save(update_fields=["target_container_snapshot_name"])


def noop_reverse(apps, schema_editor):
    return


class Migration(migrations.Migration):
    dependencies = [
        ("containers", "0008_rename_consolesession_indexes"),
    ]

    operations = [
        migrations.AddField(
            model_name="containerrequest",
            name="target_container_snapshot_name",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.RunPython(backfill_snapshot_names, noop_reverse),
    ]
