"""Add stack label denormalization to ContainerMetricsHistory.

Stack rollup endpoints group millions of timeseries rows; doing that via a
join against the OLTP `containers` table is wasteful and also fragile if the
container record is deleted or relabelled. Storing the stack at write time
keeps history accurate to the moment of measurement (Prometheus / InfluxDB
pattern) and lets the rollup query stay on a single table.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("metrics", "0006_container_gpu_columns"),
    ]

    operations = [
        migrations.AddField(
            model_name="containermetricshistory",
            name="stack",
            field=models.CharField(
                max_length=128,
                default="Unmanaged",
                help_text=(
                    "Resolved stack bucket at write time. Mirrors frontend "
                    "resolveGroup priority chain: hypercube.stack → "
                    "com.docker.compose.project → working_dir folder → 'Unmanaged'."
                ),
            ),
        ),
        migrations.AddIndex(
            model_name="containermetricshistory",
            index=models.Index(
                fields=["agent", "stack", "-recorded_at"],
                name="cmhist_agent_stack_ts_idx",
            ),
        ),
    ]
