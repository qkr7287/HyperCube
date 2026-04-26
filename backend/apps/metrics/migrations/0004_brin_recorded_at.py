from django.db import migrations


class Migration(migrations.Migration):
    """Time-series read 최적화. recorded_at에 BRIN 인덱스를 추가해 24h/7d
    range로 수백만 row를 GROUP BY 할 때 sequential scan 대신 page-range
    scan을 쓰도록 한다. append-only timeseries에 매우 효과적."""

    dependencies = [
        ("metrics", "0003_cpu_usage_nullable"),
    ]

    operations = [
        migrations.RunSQL(
            sql=(
                "CREATE INDEX IF NOT EXISTS "
                "system_metrics_history_recorded_brin "
                "ON system_metrics_history USING BRIN (recorded_at);"
            ),
            reverse_sql=(
                "DROP INDEX IF EXISTS system_metrics_history_recorded_brin;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "CREATE INDEX IF NOT EXISTS "
                "container_metrics_history_recorded_brin "
                "ON container_metrics_history USING BRIN (recorded_at);"
            ),
            reverse_sql=(
                "DROP INDEX IF EXISTS container_metrics_history_recorded_brin;"
            ),
        ),
    ]
