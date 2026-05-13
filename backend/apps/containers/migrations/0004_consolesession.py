from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("containers", "0003_containerevent"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ConsoleSession",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("exec_id", models.CharField(max_length=64, unique=True)),
                ("cmd", models.JSONField(blank=True, default=list)),
                ("user_param", models.CharField(blank=True, default="", max_length=64)),
                ("tty", models.BooleanField(default=True)),
                ("opened_at", models.DateTimeField(auto_now_add=True)),
                ("closed_at", models.DateTimeField(blank=True, null=True)),
                ("duration_seconds", models.PositiveIntegerField(blank=True, null=True)),
                ("exit_code", models.IntegerField(blank=True, null=True)),
                ("close_reason", models.CharField(blank=True, default="", max_length=32)),
                (
                    "container",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="console_sessions",
                        to="containers.container",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="console_sessions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "console_sessions",
                "ordering": ["-opened_at"],
                "indexes": [
                    models.Index(fields=["user", "-opened_at"], name="console_ses_user_idx"),
                    models.Index(fields=["container", "-opened_at"], name="console_ses_cont_idx"),
                ],
            },
        ),
    ]
