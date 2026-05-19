from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("containers", "0012_workspace_quota_metadata"),
    ]

    operations = [
        migrations.AddField(
            model_name="containertemplate",
            name="default_model_version_ids",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
