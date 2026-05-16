from django.db import migrations, models


class Migration(migrations.Migration):
    """Rename LVM thin pool capacity to workspace quota pool (XFS prjquota).

    The original 0008_agent_capacity migration added `lvm_pool_size_gb` along
    with the rest of the host capacity columns. The deployment plan moved
    from LVM thin to XFS project quota on a loop-mounted file (option 4b),
    so the same column is reused under the more accurate name and three
    quota-specific columns are added.
    """

    dependencies = [
        ("agents", "0008_agent_capacity"),
    ]

    operations = [
        migrations.RenameField(
            model_name="agent",
            old_name="lvm_pool_size_gb",
            new_name="workspace_pool_total_gb",
        ),
        migrations.AddField(
            model_name="agent",
            name="workspace_pool_free_gb",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="agent",
            name="workspace_pool_mount",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="agent",
            name="workspace_hard_enforcement",
            field=models.BooleanField(default=False),
        ),
    ]
