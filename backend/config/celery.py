"""Celery application configuration for asynchronous backend work."""

from __future__ import annotations

import os

from celery import Celery  # type: ignore[import-untyped]

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

app = Celery("quantitative_molecular_imaging_backend")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
