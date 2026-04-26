from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("metrics", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="containermetricshistory",
            name="cpu_usage_raw",
            field=models.FloatField(
                blank=True,
                null=True,
                help_text="Docker stats raw 코어 합산 % (정보 보존용). Agent v2 이상에서 채움.",
            ),
        ),
        migrations.AddField(
            model_name="containermetricshistory",
            name="cpu_cores_quota",
            field=models.FloatField(
                blank=True,
                null=True,
                help_text="이 컨테이너에 허용된 논리 코어 수. cgroup 한도 또는 호스트 코어 수.",
            ),
        ),
        migrations.AlterField(
            model_name="containermetricshistory",
            name="cpu_usage",
            field=models.FloatField(
                help_text=(
                    "컨테이너 CPU 사용률. 신규 Agent는 0~100 정규화 값(usage_pct)을 저장하고, "
                    "구버전 Agent는 Docker stats raw(코어 합산 %) 그대로 저장. 표시는 항상 0-100을 가정."
                )
            ),
        ),
    ]
