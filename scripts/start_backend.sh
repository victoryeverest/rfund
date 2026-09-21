#!/bin/bash
# Start the RFUND Django backend for the sandbox (loopback only).
# PostgreSQL + Redis are expected at 127.0.0.1 (built from source in this sandbox).
export DJANGO_SETTINGS_MODULE=config.settings
export DJANGO_ENV=development
export DATABASE_URL="${RFUND_DATABASE_URL:-postgres://rfund:rfund@127.0.0.1:5432/rfund}"
export REDIS_URL="${RFUND_REDIS_URL:-redis://127.0.0.1:6379/0}"
export CELERY_BROKER_URL="$REDIS_URL"
export CELERY_RESULT_BACKEND="$REDIS_URL"
export ALLOW_LOCAL_PAYMENT_PROVIDER="${RFUND_ALLOW_LOCAL_PROVIDER:-true}"
export PAYMENT_PROVIDER="${RFUND_PAYMENT_PROVIDER:-local}"
export SMS_PROVIDER=console
export DJANGO_SECRET_KEY="${RFUND_DJANGO_SECRET_KEY:-sandbox-dev-only-key-change-me}"
export LOG_LEVEL=INFO

cd /home/z/my-project/backend
exec .venv/bin/python manage.py runserver 127.0.0.1:8000 --noreload
