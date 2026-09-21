"""Focused concurrency probe for next_reference (temporary debug script)."""

import os
import sys

os.environ["DJANGO_ENV"] = "test"
os.environ["DATABASE_URL"] = os.environ.get(
    "PROBE_DB", "postgres://rfund:rfund@127.0.0.1:5432/rfund"
)

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.test.utils import setup_test_environment, get_runner
from django.conf import settings

setup_test_environment()
runner = get_runner(settings)()
old_config = runner.setup_databases()

from concurrent.futures import ThreadPoolExecutor

from django.db import connections, transaction

from apps.core.references import next_reference
from apps.ledger.models import LedgerAccount
from apps.ledger.services import ensure_core_accounts

ensure_core_accounts()


def gen(_):
    try:
        with transaction.atomic():
            LedgerAccount.objects.select_for_update().get(code="SAVINGS_POOL")
            return next_reference("PRB")
    finally:
        # Close THIS thread's connection so teardown can drop the DB.
        connections.close_all()


with ThreadPoolExecutor(max_workers=8) as pool:
    refs = list(pool.map(gen, range(20)))

print("refs:", sorted(refs))
print("unique:", len(set(refs)), "of", len(refs))
runner.teardown_databases(old_config)
print("teardown OK")
