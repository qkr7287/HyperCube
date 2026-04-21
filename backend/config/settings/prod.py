"""Production settings for HyperCube backend.

Loaded when DJANGO_SETTINGS_MODULE=config.settings.prod. Inherits from
base and tightens a small set of runtime-critical knobs. Anything
security-sensitive is driven by environment variables so the same image
can target multiple deployment environments.
"""

from decouple import Csv, config

from .base import *  # noqa: F401,F403

DEBUG = config("DEBUG", default=False, cast=bool)

ALLOWED_HOSTS = config(
    "DJANGO_ALLOWED_HOSTS",
    default="*",
    cast=Csv(),
)

CORS_ALLOWED_ORIGINS = config(
    "CORS_ALLOWED_ORIGINS",
    default="",
    cast=Csv(),
)
CORS_ALLOW_ALL_ORIGINS = config("CORS_ALLOW_ALL_ORIGINS", default=False, cast=bool)

CSRF_TRUSTED_ORIGINS = config(
    "CSRF_TRUSTED_ORIGINS",
    default="",
    cast=Csv(),
)

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
