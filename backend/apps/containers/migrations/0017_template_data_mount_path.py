from django.db import migrations, models


def set_data_mount_paths(apps, schema_editor):
    """기존 템플릿의 data_mount_path 보정.

    필드 default 는 /workspace 라 ML 워크스페이스 템플릿은 그대로 두고,
    이미지로 식별되는 서비스 컨테이너만 표준 데이터 경로로 바꾼다.
    """
    ContainerTemplate = apps.get_model("containers", "ContainerTemplate")
    service_paths = [
        ("redis", "/data"),
        ("postgres", "/var/lib/postgresql/data"),
        ("mysql", "/var/lib/mysql"),
        ("mariadb", "/var/lib/mysql"),
        ("mongo", "/data/db"),
    ]
    for template in ContainerTemplate.objects.all():
        image = (template.image or "").lower()
        for needle, path in service_paths:
            if needle in image:
                template.data_mount_path = path
                template.save(update_fields=["data_mount_path"])
                break


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("containers", "0016_template_launcher_overrides"),
    ]

    operations = [
        migrations.AddField(
            model_name="containertemplate",
            name="data_mount_path",
            field=models.CharField(blank=True, default="/workspace", max_length=255),
        ),
        migrations.RunPython(set_data_mount_paths, noop_reverse),
    ]
