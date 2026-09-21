import os

"""Test settings — fast, isolated, no external calls."""

from config.settings.base import *  # noqa: F401,F403

# Tests default to a file-backed SQLite DB unless DATABASE_URL is provided
# (CI provides PostgreSQL). Overridden per-test via pytest-django --db.
if not os.environ.get("DATABASE_URL"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "test_db.sqlite3",
            "ATOMIC_REQUESTS": False,
            # Threaded concurrency tests need lock-waiting, not instant failure.
            "OPTIONS": {"timeout": 30, "init_command": "PRAGMA busy_timeout=30000;"},
        }
    }

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
CELERY_TASK_ALWAYS_EAGER = True
PAYMENT_PROVIDER = os.environ.get("PAYMENT_PROVIDER", "local")
ALLOW_LOCAL_PAYMENT_PROVIDER = True
SMS_PROVIDER = os.environ.get("SMS_PROVIDER", "console")
LOG_LEVEL = "WARNING"
LOG_REQUESTS = False

# Threaded concurrency tests share the SQLite file across connections:
# WAL allows readers during writes; busy_timeout makes writers wait
# instead of failing. PostgreSQL (CI/production) handles this natively.
if DATABASES["default"]["ENGINE"].endswith("sqlite3"):
    DATABASES["default"].setdefault("OPTIONS", {})
    DATABASES["default"]["OPTIONS"].update(
        {
            "timeout": 60,
            "init_command": (
                "PRAGMA busy_timeout=60000;"
                " PRAGMA journal_mode=WAL;"
                " PRAGMA synchronous=NORMAL;"
            ),
        }
    )
