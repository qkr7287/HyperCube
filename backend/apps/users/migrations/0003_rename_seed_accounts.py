"""Reshuffle seeded accounts to (admin, user1, user2).

기존(0002): admin / agics / agics1
새(0003): admin / user1 / user2

- admin: 비밀번호를 새 안전망 값으로 갱신
- agics → user1로 rename + role 강등(admin → user) (FK 보존)
- agics1 → user2로 rename (이미 user role)
- 만약 user1/user2가 다른 사정으로 이미 존재하면 손대지 않음
"""

from django.db import migrations


def rename_seeded_accounts(apps, schema_editor):
    import sys
    if "test" in sys.argv:
        return

    User = apps.get_model("users", "CustomUser")
    from django.contrib.auth.hashers import make_password

    # admin 비밀번호 갱신 (계정 자체는 유지)
    admin = User.objects.filter(username="admin").first()
    if admin:
        admin.password = make_password("agucs12!@")
        admin.role = "admin"
        admin.is_staff = True
        admin.is_superuser = True
        admin.is_active = True
        admin.save()

    # agics → user1
    if not User.objects.filter(username="user1").exists():
        agics = User.objects.filter(username="agics").first()
        if agics:
            agics.username = "user1"
            agics.role = "user"
            agics.is_staff = False
            agics.is_superuser = False
            agics.password = make_password("agics12!@")
            agics.save()
        else:
            User.objects.create(
                username="user1",
                password=make_password("agics12!@"),
                role="user",
                is_staff=False,
                is_superuser=False,
                is_active=True,
            )

    # agics1 → user2
    if not User.objects.filter(username="user2").exists():
        agics1 = User.objects.filter(username="agics1").first()
        if agics1:
            agics1.username = "user2"
            agics1.role = "user"
            agics1.is_staff = False
            agics1.is_superuser = False
            agics1.password = make_password("agics12!@")
            agics1.save()
        else:
            User.objects.create(
                username="user2",
                password=make_password("agics12!@"),
                role="user",
                is_staff=False,
                is_superuser=False,
                is_active=True,
            )


def reverse_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0002_simplify_role"),
    ]

    operations = [
        migrations.RunPython(rename_seeded_accounts, reverse_noop),
    ]
