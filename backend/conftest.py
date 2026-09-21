"""Root conftest: force the test environment BEFORE pytest-django loads settings."""

import os

os.environ.setdefault("DJANGO_ENV", "test")
