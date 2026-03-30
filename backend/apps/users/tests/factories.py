from apps.users.models import CustomUser


def create_user(role="viewer", **kwargs):
    defaults = {
        "username": f"testuser_{role}",
        "password": "testpass123",
        "role": role,
    }
    defaults.update(kwargs)
    return CustomUser.objects.create_user(**defaults)
