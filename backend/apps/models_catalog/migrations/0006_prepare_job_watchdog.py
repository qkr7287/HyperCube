from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("models_catalog", "0005_request_launcher_overrides"),
    ]

    operations = [
        migrations.AddField(
            model_name="modelpreparejob",
            name="last_progress_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="modelpreparejob",
            name="attempt_count",
            field=models.PositiveSmallIntegerField(default=0),
        ),
    ]
