#!/usr/bin/env python3
"""Validate every gql`...` document in operations.ts against the real schema.

Catches field-name mismatches (e.g. submitKYC vs submitKyc) before deployment.
Usage: cd backend && DATABASE_URL=sqlite:////tmp/bt.sqlite3 DJANGO_ENV=test \
       .venv/bin/python ../scripts/vps/validate_operations.py
"""
import os
import re
import sys

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
os.environ["DJANGO_ENV"] = "test"
django.setup()

from graphql import build_schema, parse, validate  # noqa: E402
from graphql_api.schema import schema as strawberry_schema  # noqa: E402

SDL = str(strawberry_schema.as_str())
GRAPHQL_SCHEMA = build_schema(SDL)

OPS_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "src", "graphql", "operations.ts")
with open(OPS_PATH) as f:
    content = f.read()

docs = re.findall(r"gql`\s*(.*?)\s*`", content, re.DOTALL)
print(f"Found {len(docs)} GraphQL documents in operations.ts\n")

bad = 0
for i, doc in enumerate(docs):
    name_m = re.search(r"(query|mutation|subscription)\s+(\w+)", doc)
    label = name_m.group(2) if name_m else f"doc#{i+1}"
    try:
        errors = validate(GRAPHQL_SCHEMA, parse(doc))
    except Exception as exc:
        print(f"INVALID SYNTAX [{label}]: {exc}")
        bad += 1
        continue
    if errors:
        bad += 1
        print(f"SCHEMA MISMATCH [{label}]:")
        for e in errors:
            print(f"   {e.message}")

print(f"\n{'ALL OPERATIONS VALID' if bad == 0 else f'{bad} documents with errors'}")
sys.exit(1 if bad else 0)
