from apps.agents.models import Agent
from apps.core.models import AlertRule, AuditLog, Template
from apps.users.models import CustomUser


def create_user(role="viewer", **kwargs):
    defaults = {
        "username": f"testuser_{role}",
        "password": "testpass123",
        "role": role,
    }
    defaults.update(kwargs)
    return CustomUser.objects.create_user(**defaults)


def create_template(user=None, **kwargs):
    if user is None:
        user = create_user(role="server_admin", username="tpl_creator")
    defaults = {
        "name": "Test Template",
        "category": "web",
        "config": {"image": "nginx:latest", "ports": ["80:80"]},
        "created_by": user,
    }
    defaults.update(kwargs)
    return Template.objects.create(**defaults)


def create_alert_rule(**kwargs):
    defaults = {
        "metric": AlertRule.Metric.CPU,
        "threshold": 80.0,
        "action": "notify",
    }
    defaults.update(kwargs)
    return AlertRule.objects.create(**defaults)


def create_audit_log(user=None, **kwargs):
    defaults = {
        "user": user,
        "action": "test_action",
        "target": "test_target",
    }
    defaults.update(kwargs)
    return AuditLog.objects.create(**defaults)
