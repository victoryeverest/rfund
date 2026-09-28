#!/usr/bin/env python3
"""Send properly-signed charge.success webhooks for the E2E payments.

This is the exact HTTP Paystack performs after a hosted-checkout card charge
in test mode: POST charge.success with X-Paystack-Signature = HMAC-SHA512 of
the raw body using the secret key. Settles the payments through the full
signature -> ingest -> idempotent-process -> ledger -> domain-credit pipeline.
"""
import hashlib
import hmac
import json
import os
import time
import urllib.request

WEBHOOK = "https://testapi.inyene.com/payments/webhooks/paystack"
SECRET = os.environ["PAYSTACK_SECRET_KEY"]

state = json.load(open("/tmp/e2e_state.json"))

payments = [
    ("savings_payment_ref", 100000, "card"),
    ("loan_payment_ref", 500000, "card"),
    ("goal_payment_ref", 50000, "card"),
]

for key, kobo, channel in payments:
    ref = state.get(key)
    if not ref:
        print(f"SKIP {key} (missing)")
        continue
    payload = {
        "event": "charge.success",
        "data": {
            "id": int(time.time()) % 10**8 + payments.index((key, kobo, channel)),
            "reference": ref,
            "amount": kobo,
            "currency": "NGN",
            "status": "success",
            "paid_at": "2026-09-28T09:30:00.000Z",
            "channel": channel,
            "metadata": {"internal_reference": ref},
        },
    }
    raw = json.dumps(payload).encode()
    sig = hmac.new(SECRET.encode(), raw, hashlib.sha512).hexdigest()
    req = urllib.request.Request(
        WEBHOOK, data=raw,
        headers={"Content-Type": "application/json",
                 "X-Paystack-Signature": sig,
                 "User-Agent": "Paystack/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            print(f"{key} {ref}: HTTP {r.status} {r.read().decode()}")
    except urllib.error.HTTPError as e:
        print(f"{key} {ref}: HTTP {e.code} {e.read().decode()}")
