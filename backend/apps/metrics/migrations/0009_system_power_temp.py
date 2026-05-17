from django.db import migrations, models


class Migration(migrations.Migration):
    """호스트 자원 부담 (Level 2: Fan + RAPL + nvidia-smi) 위한 전력/온도 컬럼 추가.

    Agent 가 raw_data 에 cpu.packagePowerW / cpu.tempC / gpu[].powerDrawW /
    gpu[].temperatureC 를 보내기 시작하면 tasks._collect_system_metrics 가
    이 컬럼들로 mapping 한다. 미수집 호스트는 null 유지.

    Nullable 이라 backfill 불필요.
    """

    dependencies = [
        ("metrics", "0008_alter_containermetricshistory_gpu_usage_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="systemmetricshistory",
            name="gpu_power_w",
            field=models.FloatField(
                null=True,
                blank=True,
                help_text="GPU 전체 전력 합산 (W). nvidia-smi power.draw 합. 다중 GPU 합산.",
            ),
        ),
        migrations.AddField(
            model_name="systemmetricshistory",
            name="cpu_power_w",
            field=models.FloatField(
                null=True,
                blank=True,
                help_text=(
                    "CPU package 평균 전력 (W). Intel/AMD RAPL energy_uj 차분으로 계산. "
                    "multi-socket 합산. RAPL 미지원 / 권한 없음 시 null."
                ),
            ),
        ),
        migrations.AddField(
            model_name="systemmetricshistory",
            name="cpu_temp_c",
            field=models.FloatField(
                null=True,
                blank=True,
                help_text=(
                    "CPU package 온도 (°C). thermal_zone (x86_pkg_temp/coretemp/k10temp) 우선. "
                    "센서 없으면 null."
                ),
            ),
        ),
    ]
