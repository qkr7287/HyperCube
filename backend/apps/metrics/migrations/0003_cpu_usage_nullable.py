from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("metrics", "0002_container_cpu_normalization"),
    ]

    operations = [
        migrations.AlterField(
            model_name="containermetricshistory",
            name="cpu_usage",
            field=models.FloatField(
                null=True,
                blank=True,
                help_text=(
                    "컨테이너 CPU 사용률 (0~100 정규화). 신규 Agent의 cpu.usage_pct 값을 그대로 저장. "
                    "Agent가 cores_quota 결정 실패 시 null 저장됨. "
                    "구버전 Agent는 cpu.usage / cores 로 fallback 계산해 채움."
                ),
            ),
        ),
    ]
