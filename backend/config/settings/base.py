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
    "apps.metrics",
    "apps.models_catalog",
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

# Cache (Redis DB 2 — DB 0 channels, DB 1 metrics raw cache, DB 2 view cache)
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": config("CACHE_REDIS_URL", default="redis://redis:6379/2"),
        "TIMEOUT": 60,
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
# Expiration is effectively disabled during development by setting very
# long lifetimes. Original production values are preserved below for
# easy restoration — swap the active block back when re-enabling.
SIMPLE_JWT = {
    # --- Expiration disabled (dev) ---
    "ACCESS_TOKEN_LIFETIME": timedelta(days=365 * 10),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=365 * 10),
    # --- Production values (re-enable by swapping the two lines above) ---
    # "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    # "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
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
        # 5s cadence so the 1분/10분 trend charts actually have a dozen+
        # points. DB cost scales linearly (6× the rows vs 30s); at 3 agents
        # that's ~360k rows/week, well inside Postgres comfort.
        "schedule": 5.0,
    },
    "cleanup-old-metrics": {
        "task": "apps.metrics.tasks.cleanup_old_metrics",
        "schedule": crontab(hour=3, minute=0),
    },
    # 1h/24h/7d range 차트의 사전 집계. 매번 raw 위에서 GROUP BY 하면 28일 ×10M+
    # rows 라 30s+ 걸려서 hourly/daily rollup 테이블로 누적. viewset 이 bucket 크기
    # 보고 rollup 직접 읽음 → 첫 호출도 100ms 미만.
    "compute-metrics-rollups-hourly": {
        "task": "apps.metrics.tasks.compute_metrics_rollups",
        "schedule": 300.0,
        "kwargs": {"bucket_seconds": 3600, "lookback_buckets": 3},
    },
    "compute-metrics-rollups-daily": {
        "task": "apps.metrics.tasks.compute_metrics_rollups",
        "schedule": 1800.0,
        "kwargs": {"bucket_seconds": 86400, "lookback_buckets": 3},
    },
    "detect-offline-agents": {
        "task": "apps.agents.tasks.detect_offline_agents",
        "schedule": 30.0,
    },
    "refresh-gpu-inventories": {
        "task": "apps.agents.tasks.refresh_gpu_inventories",
        "schedule": 60.0,
    },
    "cleanup-expired-gpu-reservations": {
        "task": "apps.containers.tasks.cleanup_expired_gpu_reservations_task",
        "schedule": 60.0,
    },
    "cleanup-stale-model-prepare-jobs": {
        "task": "apps.models_catalog.tasks.cleanup_stale_model_prepare_jobs_task",
        "schedule": 60.0,
    },
    "archive-dormant-agents": {
        "task": "apps.agents.tasks.archive_dormant_agents",
        "schedule": crontab(hour=3, minute=30),
    },
    "delete-archived-agents": {
        "task": "apps.agents.tasks.delete_archived_agents",
        "schedule": crontab(hour=4, minute=0),
    },
}

# Redis cache (직접 접근, Channel Layer와 분리: DB 1)
REDIS_CACHE_URL = config("REDIS_CACHE_URL", default="redis://redis:6379/1")
METRICS_RETENTION_DAYS = config("METRICS_RETENTION_DAYS", default=7, cast=int)
WORKSPACE_TOKEN_TTL_SECONDS = config("WORKSPACE_TOKEN_TTL_SECONDS", default=86400, cast=int)
# 300s — 60s 는 Web UI 버튼 클릭과 새 탭 로드 사이에 만료될 만큼 짧다.
WORKSPACE_TICKET_TTL_SECONDS = config("WORKSPACE_TICKET_TTL_SECONDS", default=300, cast=int)
WORKSPACE_SESSION_TTL_SECONDS = config("WORKSPACE_SESSION_TTL_SECONDS", default=28800, cast=int)
HC_GPU_SHARED_MODE_ENABLED = config("HC_GPU_SHARED_MODE_ENABLED", default=False, cast=bool)
HC_MAX_ACTIVE_WORKSPACES_PER_USER = config("HC_MAX_ACTIVE_WORKSPACES_PER_USER", default=2, cast=int)
HC_MAX_ACTIVE_GPU_SLICES_PER_USER = config("HC_MAX_ACTIVE_GPU_SLICES_PER_USER", default=1, cast=int)
HC_MAX_WORKSPACE_RUNTIME_HOURS = config("HC_MAX_WORKSPACE_RUNTIME_HOURS", default=72, cast=int)
HC_MODEL_STORAGE_DIR = config("HC_MODEL_STORAGE_DIR", default=str(BASE_DIR / "model-assets"))
HC_MODEL_IMPORT_DIR = config("HC_MODEL_IMPORT_DIR", default=str(BASE_DIR / "model-import"))
MODEL_PREPARE_LEASE_SECONDS = config("MODEL_PREPARE_LEASE_SECONDS", default=86400, cast=int)
# 마지막 progress 후 이 시간만큼 무응답이면 prepare job 을 stuck 으로 보고
# 재시도/실패 처리한다. LEASE(전체 데드라인) 와 별개의 짧은 watchdog.
MODEL_PREPARE_PROGRESS_TIMEOUT_SECONDS = config(
    "MODEL_PREPARE_PROGRESS_TIMEOUT_SECONDS", default=900, cast=int
)
# progress timeout 으로 stuck 판정 시 재dispatch 최대 횟수. 초과하면 FAILED.
MODEL_PREPARE_MAX_ATTEMPTS = config("MODEL_PREPARE_MAX_ATTEMPTS", default=3, cast=int)

# Workspace proxy forwards arbitrary multipart/binary bodies (image uploads to
# the auto-launched gradio app, JupyterLab file drops, etc). The 2.5MB default
# trips RequestDataTooBig the moment a user drops a photo into the AI UI, so
# raise the limit to a value that comfortably covers normal multimodal inputs.
# File-handler still spills to disk past FILE_UPLOAD_MAX_MEMORY_SIZE.
DATA_UPLOAD_MAX_MEMORY_SIZE = config(
    "DATA_UPLOAD_MAX_MEMORY_SIZE", default=200 * 1024 * 1024, cast=int
)
FILE_UPLOAD_MAX_MEMORY_SIZE = config(
    "FILE_UPLOAD_MAX_MEMORY_SIZE", default=5 * 1024 * 1024, cast=int
)

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
