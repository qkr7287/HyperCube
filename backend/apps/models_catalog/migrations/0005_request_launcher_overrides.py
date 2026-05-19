from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("models_catalog", "0004_request_launcher_recipe"),
    ]

    operations = [
        migrations.AddField(
            model_name="modeluploadrequest",
            name="launcher_overrides",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
