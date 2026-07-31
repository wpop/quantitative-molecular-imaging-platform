#!/usr/bin/env python
"""Command-line utility for administrative Django tasks."""

from __future__ import annotations

import os
import sys

from django.core.management import execute_from_command_line


def main() -> None:
    """Run Django management commands with the development settings by default."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
