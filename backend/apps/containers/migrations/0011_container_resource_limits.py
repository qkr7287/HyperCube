from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("containers", "0010_template_weights"),
    ]

    operations = [
        migrations.AddField(
            model_name="container",
            name="cpu_percent_limit",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="container",
            name="memory_mb_limit",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="container",
            name="workspace_gb_limit",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="container",
            name="workspace_device",
            field=models.CharField(blank=True, max_length=120, null=True),
        ),
        migrations.AddField(
            model_name="container",
            name="limit_updated_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="containerrequest",
            name="cpu_percent",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="containerrequest",
            name="memory_mb",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="containerrequest",
            name="workspace_gb",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
    ]
