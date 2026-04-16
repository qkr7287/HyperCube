"""Fix admin password typo from 0003 (agucs -> agics)."""

from django.db import migrations


def fix_admin_password(apps, schema_editor):
    import sys
    if "test" in sys.argv:
        return

    User = apps.get_model("users", "CustomUser")
    from django.contrib.auth.hashers import make_password

    admin = User.objects.filter(username="admin").first()
    if admin:
        admin.password = make_password("agics12!@")
        admin.save(update_fields=["password"])


def reverse_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0003_rename_seed_accounts"),
    ]

    operations = [
        migrations.RunPython(fix_admin_password, reverse_noop),
    ]
