from apps.agents.models import Agent
from apps.containers.models import Container
from apps.users.models import CustomUser


def create_user(role="user", **kwargs):
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


def create_container(agent=None, **kwargs):
    if agent is None:
        agent = create_agent()
    defaults = {
        "container_id": "abc123def456",
        "name": "test-container",
        "image": "nginx:latest",
        "agent": agent,
        "status": Container.Status.RUNNING,
    }
    defaults.update(kwargs)
    return Container.objects.create(**defaults)
