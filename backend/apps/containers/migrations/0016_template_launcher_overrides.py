from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("containers", "0015_template_launcher_recipe"),
    ]

    operations = [
        migrations.AddField(
            model_name="containertemplate",
            name="launcher_overrides",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
