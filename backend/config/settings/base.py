"""Django base settings for HyperCube backend."""

from datetime import timedelta
from pathlib import Path

from celery.schedules import crontab
from decouple import config

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = config("DJANGO_SECRET_KEY", default="dev-insecure-key-change-in-production")

ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="*", cast=lambda v: v.split(","))

INSTALLED_APPS = [
    # django-unfold는 admin보다 먼저 등록되어야 함
    "unfold",
    "unfold.contrib.filters",
    "unfold.contrib.forms",
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third party
    "rest_framework",
    "django_filters",
    "drf_spectacular",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "channels",
    # Local apps
    "apps.common",
    "apps.users",
    "apps.agents",
    "apps.containers",
    "apps.core",
    "apps.metrics",
]

AUTH_USER_MODEL = "users.CustomUser"

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    # whitenoise: ASGI(uvicorn) 환경에서 admin static 서빙
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# Database
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": config("DB_NAME", default="hypercube"),
        "USER": config("DB_USER", default="hypercube"),
        "PASSWORD": config("DB_PASSWORD", default="hypercube"),
        "HOST": config("DB_HOST", default="postgres"),
        "PORT": config("DB_PORT", default="5432"),
    }
}

# Channel Layer (Redis)
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [config("REDIS_URL", default="redis://redis:6379/0")],
        },
    },
}

# REST Framework
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "apps.common.renderers.EnvelopeJSONRenderer",
    ],
    "DEFAULT_PAGINATION_CLASS": "apps.common.pagination.StandardPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

# Simple JWT
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "TOKEN_OBTAIN_SERIALIZER": "apps.users.token_serializers.CustomTokenObtainPairSerializer",
}

# drf-spectacular
SPECTACULAR_SETTINGS = {
    "TITLE": "HyperCube API",
    "DESCRIPTION": "Docker Container Monitoring Platform API",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SERVE_PERMISSIONS": ["rest_framework.permissions.AllowAny"],
    "SCHEMA_PATH_PREFIX": "/api/",
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Seoul"
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedStaticFilesStorage"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Celery
CELERY_BROKER_URL = config("CELERY_BROKER_URL", default="redis://redis:6379/1")
CELERY_RESULT_BACKEND = config("CELERY_RESULT_BACKEND", default="redis://redis:6379/1")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_BEAT_SCHEDULE = {
    "flush-metrics-to-db": {
        "task": "apps.metrics.tasks.flush_metrics_to_db",
        "schedule": 30.0,
    },
    "cleanup-old-metrics": {
        "task": "apps.metrics.tasks.cleanup_old_metrics",
        "schedule": crontab(hour=3, minute=0),
    },
}

# Redis cache (직접 접근, Channel Layer와 분리: DB 1)
REDIS_CACHE_URL = config("REDIS_CACHE_URL", default="redis://redis:6379/1")
METRICS_RETENTION_DAYS = config("METRICS_RETENTION_DAYS", default=7, cast=int)

# django-unfold (Admin 테마)
UNFOLD = {
    "SITE_TITLE": "HyperCube Admin",
    "SITE_HEADER": "HyperCube",
    "SITE_SUBHEADER": "Container Monitoring Platform",
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": True,
    "THEME": "dark",
    "COLORS": {
        "primary": {
            "50": "236 254 255",
            "100": "207 250 254",
            "200": "165 243 252",
            "300": "103 232 249",
            "400": "34 211 238",
            "500": "48 213 200",   # accent
            "600": "8 145 178",
            "700": "14 116 144",
            "800": "21 94 117",
            "900": "22 78 99",
            "950": "8 51 68",
        },
    },
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": True,
    },
}
