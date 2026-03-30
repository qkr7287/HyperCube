from apps.agents.models import Agent
from apps.users.models import CustomUser


def create_user(role="viewer", **kwargs):
    defaults = {
        "username": f"testuser_{role}",
        "password": "testpass123",
        "role": role,
    }
    defaults.update(kwargs)
    return CustomUser.objects.create_user(**defaults)


def create_agent(**kwargs):
    defaults = {
        "hostname": "test-host",
        "ip_address": "192.168.1.1",
        "status": Agent.Status.APPROVED,
    }
    defaults.update(kwargs)
    return Agent.objects.create(**defaults)
