from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("agents", "0007_gpu_inventory"),
    ]

    operations = [
        migrations.AddField(
            model_name="agent",
            name="cpu_cores",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="agent",
            name="cpu_model",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="agent",
            name="ram_total_mb",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="agent",
            name="disk_total_gb",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="agent",
            name="lvm_pool_size_gb",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="agent",
            name="nic_speed_mbps",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="agent",
            name="filesystem",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.AddField(
            model_name="agent",
            name="target_users",
            field=models.PositiveIntegerField(default=4),
        ),
        migrations.AddField(
            model_name="agent",
            name="safety_margin",
            field=models.FloatField(default=0.8),
        ),
        migrations.AddField(
            model_name="agent",
            name="capacity_updated_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
