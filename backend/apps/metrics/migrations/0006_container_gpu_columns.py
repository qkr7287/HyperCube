from django.db import migrations, models


class Migration(migrations.Migration):
    """컨테이너 단위 GPU 시계열을 컬럼으로 저장.

    Agent v3 의 container_metrics.gpu.{usage, memoryUsed, memoryTotal} 를 시계열로
    누적해 user/admin 대시보드의 GPU 그래프에 사용한다. raw_data 에 동일한 값이
    이미 보관되고 있지만, JSON 추출은 매 query 마다 비용이 들고 group-by aggregation
    이 어렵기 때문에 explicit column 으로 승격.

    모두 nullable 이라 backfill 불필요 — 기존 row 는 null 로 남고, migration 적용 이후
    수집되는 row 부터 채워진다.
    """

    dependencies = [
        ("metrics", "0005_system_gpu_and_memory_available"),
    ]

    operations = [
        migrations.AddField(
            model_name="containermetricshistory",
            name="gpu_usage",
            field=models.FloatField(
                null=True,
                blank=True,
                help_text=(
                    "컨테이너 GPU 사용률 (0~100, %). Agent 가 PID → 컨테이너 매핑으로 계산. "
                    "측정 불가 시 null."
                ),
            ),
        ),
        migrations.AddField(
            model_name="containermetricshistory",
            name="gpu_memory_used",
            field=models.BigIntegerField(
                null=True,
                blank=True,
                help_text="컨테이너 GPU 메모리 사용량 (bytes). 측정 불가 시 null.",
            ),
        ),
        migrations.AddField(
            model_name="containermetricshistory",
            name="gpu_memory_total",
            field=models.BigIntegerField(
                null=True,
                blank=True,
                help_text="컨테이너에 할당된 GPU 메모리 한도 (bytes). 측정 불가 시 null.",
            ),
        ),
    ]
