from apps.agents.models import Agent
from apps.containers.models import Container, ContainerRequest, ContainerTemplate
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


def create_template(created_by, **kwargs):
    defaults = {
        "name": "Test Nginx",
        "kind": ContainerTemplate.Kind.SIMPLE,
        "image": "nginx:latest",
        "description": "test template",
    }
    defaults.update(kwargs)
    return ContainerTemplate.objects.create(created_by=created_by, **defaults)


def create_request(requester, template=None, target_agent=None, **kwargs):
    defaults = {
        "action": ContainerRequest.Action.CREATE,
        "status": ContainerRequest.Status.PENDING,
    }
    if template is not None:
        defaults["template"] = template
    if target_agent is not None:
        defaults["target_agent"] = target_agent
    defaults.update(kwargs)
    return ContainerRequest.objects.create(requester=requester, **defaults)
