from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("models_catalog", "0003_model_upload_request"),
    ]

    operations = [
        migrations.AddField(
            model_name="modeluploadrequest",
            name="launcher_recipe_id",
            field=models.CharField(blank=True, default="none", max_length=64),
        ),
    ]
