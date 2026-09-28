#!/bin/sh
# Run the RFUND backend test suite on the VPS against PostgreSQL.
# Only DATABASE_URL is taken from rfund.env; provider/settings stay in test mode.
set -a
. /opt/rfund/rfund.env
set +a
unset DJANGO_SETTINGS_MODULE
unset PAYMENT_PROVIDER PAYSTACK_SECRET_KEY PAYSTACK_PUBLIC_KEY
export DJANGO_ENV=test
cd /opt/rfund/repo/backend
export PYTHONPATH=/opt/rfund/repo/backend
exec /opt/rfund/venv/bin/python -m pytest tests/ -q --tb=short
