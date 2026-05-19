from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("containers", "0014_drop_unused_seed_templates"),
    ]

    operations = [
        migrations.AddField(
            model_name="containertemplate",
            name="launcher_recipe_id",
            field=models.CharField(blank=True, default="none", max_length=64),
        ),
    ]
