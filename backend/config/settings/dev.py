"""Django development settings."""

from .base import *  # noqa: F401, F403

DEBUG = True

CORS_ALLOW_ALL_ORIGINS = True

INSTALLED_APPS += [  # noqa: F405
    "debug_toolbar",
    "apps.mock",
]

# Mock API: Phase 2(Agent)까지 Frontend 개발용 가짜 데이터 제공
MOCK_API_ENABLED = True

MIDDLEWARE.insert(0, "debug_toolbar.middleware.DebugToolbarMiddleware")  # noqa: F405

INTERNAL_IPS = ["127.0.0.1", "localhost"]

# Allow all hosts in dev
ALLOWED_HOSTS = ["*"]
