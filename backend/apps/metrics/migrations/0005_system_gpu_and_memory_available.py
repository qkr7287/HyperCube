from django.db import migrations, models


class Migration(migrations.Migration):
    """fleet GPU sparkline + Linux 정확한 메모리 사용률 위한 컬럼 추가.

    - memory_available: Linux MemAvailable (bytes). 정확한 사용률 산출용.
      Agent 가 보내기 시작하면 자동 채워짐. 구버전 Agent 는 null.
    - gpu_usage / gpu_count / gpu_memory_* / gpu_temperature_max: 다중 GPU 호스트도
      단일 컬럼으로 sparkline 가능하게 평균·합산·최대값 정규화 저장.

    모두 nullable 이라 backfill 불필요. 기존 raw_data 에 보관된 값으로 backfill 하려면
    별도 management command 작성 (선택).
    """

    dependencies = [
        ("metrics", "0004_brin_recorded_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="systemmetricshistory",
            name="memory_available",
            field=models.BigIntegerField(
                null=True,
                blank=True,
                help_text=(
                    "Linux MemAvailable (bytes). buffer/cache 를 사용으로 잘못 카운트하지 않도록 "
                    "정확한 메모리 사용률 = (total - available) / total. Agent v3+ 에서 채움. "
                    "구버전 Agent 는 null."
                ),
            ),
        ),
        migrations.AddField(
            model_name="systemmetricshistory",
            name="gpu_usage",
            field=models.FloatField(
                null=True,
                blank=True,
                help_text="GPU 사용률 (%) — 다중 GPU 평균. GPU 없으면 null.",
            ),
        ),
        migrations.AddField(
            model_name="systemmetricshistory",
            name="gpu_count",
            field=models.IntegerField(
                null=True,
                blank=True,
                help_text="장착 GPU 개수.",
            ),
        ),
        migrations.AddField(
            model_name="systemmetricshistory",
            name="gpu_memory_used",
            field=models.BigIntegerField(
                null=True,
                blank=True,
                help_text="GPU VRAM 사용 합산 (bytes).",
            ),
        ),
        migrations.AddField(
            model_name="systemmetricshistory",
            name="gpu_memory_total",
            field=models.BigIntegerField(
                null=True,
                blank=True,
                help_text="GPU VRAM 전체 합산 (bytes).",
            ),
        ),
        migrations.AddField(
            model_name="systemmetricshistory",
            name="gpu_temperature_max",
            field=models.FloatField(
                null=True,
                blank=True,
                help_text="GPU 최고 온도 (°C). 다중 GPU 중 가장 뜨거운 값.",
            ),
        ),
    ]
