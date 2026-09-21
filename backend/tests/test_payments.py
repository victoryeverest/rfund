"""Payments + webhook tests (spec §22–§28, §109, §151, §202)."""

import hashlib
import hmac
import json
from decimal import Decimal

import pytest

from apps.core.errors import Conflict
from apps.ledger.services import ensure_core_accounts, verify_balances
from apps.payments.models import Payment, PaymentWebhookEvent
from apps.payments.services import (
    initialize_payment,
    ingest_webhook,
    process_webhook_event,
    retry_failed_webhooks,
    settle_payment,
    verify_and_settle,
)
from apps.savings.services import create_savings_plan, ensure_default_products
from integrations.payments.base import get_payment_provider
from tests.factories import make_customer, verify_kyc


@pytest.fixture(autouse=True)
def _setup(db):
    ensure_core_accounts()
    ensure_default_products()


@pytest.fixture
def local_provider():
    return get_payment_provider("local")


def make_paid_payment(customer, amount="1000", purpose="ACCOUNT_FUNDING", key="k"):
    return initialize_payment(
        customer=customer,
        purpose=purpose,
        amount=Decimal(amount),
        idempotency_key=key,
    )


class TestInitialization:
    def test_initialization_pending_with_url(self, customer):
        payment, url = make_paid_payment(customer, key="init-1")
        assert payment.status == Payment.Status.PENDING
        assert payment.provider == "local"
        assert url  # authorization URL returned

    def test_idempotent_initialization(self, customer):
        p1, _ = make_paid_payment(customer, amount="500", key="dup-1")
        p2, _ = make_paid_payment(customer, amount="500", key="dup-1")
        assert p1.pk == p2.pk

    def test_idempotency_conflict_on_different_amount(self, customer):
        make_paid_payment(customer, amount="500", key="dup-2")
        from apps.core.errors import Conflict as C

        with pytest.raises(C):
            make_paid_payment(customer, amount="700", key="dup-2")

    def test_invalid_amount_rejected(self, customer):
        from apps.core.errors import ValidationFailed

        with pytest.raises(ValidationFailed):
            initialize_payment(
                customer=customer, purpose="ACCOUNT_FUNDING", amount=Decimal("0")
            )


class TestSettlement:
    def test_amount_mismatch_rejected(self, customer):
        payment, _url = make_paid_payment(customer, amount="1000", key="settle-1")
        with pytest.raises(Conflict, match="does not match"):
            settle_payment(
                payment,
                provider_reference=payment.provider_reference,
                amount=Decimal("999"),
                currency="NGN",
            )

    def test_settle_is_idempotent(self, customer):
        payment, _url = make_paid_payment(customer, amount="1000", key="settle-2")
        settled = settle_payment(
            payment,
            provider_reference=payment.provider_reference,
            amount=Decimal("1000"),
            currency="NGN",
        )
        again = settle_payment(
            payment,
            provider_reference=payment.provider_reference,
            amount=Decimal("1000"),
            currency="NGN",
        )
        assert settled.pk == again.pk
        assert Payment.objects.count() == 1
        verify_balances()  # no double credit


class TestWebhookPipeline:  # spec §25, §109, §202
    def _webhook(self, customer, key, amount="1500"):
        payment, _url = make_paid_payment(customer, amount=amount, key=key)
        local = get_payment_provider("local")
        payload = local.mark_success(payment.provider_reference)
        event = ingest_webhook(
            provider_code="local",
            event_id=f"evt-{key}",
            event_type="charge.success",
            payload=payload,
            signature_valid=True,
        )
        return payment, event

    def test_webhook_settles_payment_and_posts_ledger(self, customer):
        payment, event = self._webhook(customer, "wh-1")
        process_webhook_event(event)
        payment.refresh_from_db()
        assert payment.status == Payment.Status.SUCCESS
        assert payment.ledger_transaction is not None
        assert payment.ledger_transaction.status == "POSTED"

    def test_duplicate_webhook_exactly_once(self, customer):  # spec §202
        payment, event = self._webhook(customer, "wh-2")
        for _ in range(5):  # same event five times
            process_webhook_event(event)
        from apps.ledger.models import LedgerTransaction

        payment.refresh_from_db()
        assert payment.status == Payment.Status.SUCCESS
        assert LedgerTransaction.objects.count() == 1
        verify_balances()  # one credit only

    def test_unsigned_webhook_quarantined(self, customer):
        payment, _url = make_paid_payment(customer, amount="500", key="wh-3")
        local = get_payment_provider("local")
        payload = local.mark_success(payment.provider_reference)
        event = ingest_webhook(
            provider_code="local",
            event_id="evt-bad-sig",
            event_type="charge.success",
            payload=payload,
            signature_valid=False,
        )
        processed = process_webhook_event(event)
        assert processed.processing_status == "FAILED"
        payment.refresh_from_db()
        assert payment.status == Payment.Status.PENDING  # no money moved

    def test_unknown_reference_records_failure(self, customer):
        event = ingest_webhook(
            provider_code="local",
            event_id="evt-unknown",
            event_type="charge.success",
            payload={"event": "charge.success", "data": {"reference": "nope", "amount": 100000}},
            signature_valid=True,
        )
        processed = process_webhook_event(event)
        assert processed.processing_status == "FAILED"
        assert "No payment matches" in processed.processing_error

    def test_retry_failed_webhooks(self, customer):
        payment, event = self._webhook(customer, "wh-4")
        payment.refresh_from_db()
        # First, make processing fail once by clearing the payment lookup
        event.processing_status = "FAILED"
        event.save()
        count = retry_failed_webhooks()
        assert count >= 1
        event.refresh_from_db()
        # It should either succeed now or record failure again — deterministic here:
        # the payment exists, so it settles.
        assert event.processing_status == "PROCESSED"


class TestPaystackSignature:
    def test_signature_verification(self, settings):
        settings.PAYSTACK_WEBHOOK_SECRET = "whsec_test"
        provider = get_payment_provider("paystack")
        body = json.dumps(
            {"event": "charge.success", "data": {"id": 123, "reference": "PS-1", "amount": 100000}}
        ).encode()
        good = hmac.new(b"whsec_test", body, hashlib.sha512).hexdigest()
        assert provider.verify_webhook_signature(payload_body=body, signature=good)
        assert not provider.verify_webhook_signature(payload_body=body, signature="bad")
        assert not provider.verify_webhook_signature(payload_body=body, signature="")

    def test_missing_secret_fails_closed(self, settings):
        settings.PAYSTACK_WEBHOOK_SECRET = ""
        provider = get_payment_provider("paystack")
        assert not provider.verify_webhook_signature(payload_body=b"x", signature="x")


class TestVerificationIsAuthoritative:  # spec §23
    def test_verify_and_settle(self, customer):
        payment, _url = make_paid_payment(customer, amount="1200", key="verify-1")
        result = verify_and_settle(payment)
        assert result.status == Payment.Status.SUCCESS

    def test_repeated_verify_safe(self, customer):
        payment, _url = make_paid_payment(customer, amount="1200", key="verify-2")
        verify_and_settle(payment)
        verify_and_settle(payment)
        from apps.ledger.models import LedgerTransaction

        assert LedgerTransaction.objects.count() == 1
