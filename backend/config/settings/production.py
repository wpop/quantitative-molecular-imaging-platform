"""Production settings for deployed backend environments."""

from __future__ import annotations

import os

from django.core.exceptions import ImproperlyConfigured

from .base import *

DEBUG = False

_secret_key = os.environ.get("DJANGO_SECRET_KEY")
if not _secret_key:
    message = "DJANGO_SECRET_KEY must be set in production."
    raise ImproperlyConfigured(message)
SECRET_KEY = _secret_key

ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",")
    if host.strip()
]

CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",")
    if origin.strip()
]

SECURE_SSL_REDIRECT = os.environ.get("DJANGO_SECURE_SSL_REDIRECT", "true").lower() == "true"
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_SECURE_HSTS_SECONDS", "31536000"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
