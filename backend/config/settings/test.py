"""Test settings for local and continuous integration checks."""

from __future__ import annotations

from .base import *

DEBUG = False
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
