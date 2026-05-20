from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("containers", "0017_template_data_mount_path"),
    ]

    operations = [
        # default 만 internal_only -> none 으로 변경. 기존 row 는 건드리지
        # 않는다 — 같은 docker daemon 에서 internal_only 로 동작하는 dev
        # 템플릿을 깨뜨리지 않기 위함.
        migrations.AlterField(
            model_name="containertemplate",
            name="network_policy",
            field=models.CharField(
                choices=[
                    ("internal_only", "Internal only"),
                    ("none", "None"),
                    ("custom", "Custom"),
                ],
                default="none",
                max_length=32,
            ),
        ),
    ]
