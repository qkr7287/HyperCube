from django.db import migrations, models


class Migration(migrations.Migration):
    """Add XFS project quota metadata for per-container workspaces.

    `workspace_device` was originally `/dev/vg0/cid_<short>` from LVM thin;
    after the move to XFS prjquota on a loop file it stores the mount path
    (e.g. `/var/lib/hypercube/workspaces/<short>`) and the project id moves
    into its own column. Existing rows keep working — the agent re-reports
    them on the next `container_metrics` push.
    """

    dependencies = [
        ("containers", "0011_container_resource_limits"),
    ]

    operations = [
        migrations.AlterField(
            model_name="container",
            name="workspace_device",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="container",
            name="workspace_project_id",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
    ]
