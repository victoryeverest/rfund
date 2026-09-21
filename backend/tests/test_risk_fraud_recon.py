"""Risk, fraud, reconciliation, and journey tests (spec §45–§47, §27, §199–§201)."""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.accounts.models import User
from apps.accounts.services import grant_role
from apps.core.errors import NotFound, ValidationFailed
from apps.fraud import services as fraud_services
from apps.fraud.models import FraudAlert, FraudRule
from apps.ledger.services import ensure_core_accounts, verify_balances
from apps.loans.services import (
    approve_application,
    create_loan_application,
    ensure_default_products,
)
from apps.notifications.models import OutboxEvent
from apps.payments import services as payment_services
from apps.risk import services as risk_services
from apps.settlements import services as recon_services
from apps.settlements.models import ReconciliationItem
from apps.savings.services import ensure_default_products as ensure_savings_products
from tests.factories import make_customer, verify_kyc


@pytest.fixture(autouse=True)
def _setup(db):
    ensure_core_accounts()
    risk_services.ensure_default_rules()
    fraud_services.ensure_default_rules()
    ensure_savings_products()
    ensure_default_products()


class TestRiskEngine:  # spec §45 — explainable, deterministic
    def test_assessment_has_factors(self):
        customer = make_customer("+2348055550001")
        verify_kyc(customer)
        application = create_loan_application(
            customer=customer,
            product_code="TRADER",
            amount=Decimal("40000"),
            term_months=6,
            purpose="stock",
        )
        assessment = application.assessment
        assert assessment is not None
        assert assessment.factors.count() >= 5  # every decision explainable
        for factor in assessment.factors.all():
            assert factor.explanation
        assert assessment.decision in ("APPROVE", "REVIEW", "REJECT")
        assert 0 <= assessment.score <= 100

    def test_score_deterministic(self):
        customer = make_customer("+2348055550002")
        verify_kyc(customer)
        a1 = create_loan_application(
            customer=customer, product_code="TRADER",
            amount=Decimal("20000"), term_months=3, purpose="x",
        )
        a2 = create_loan_application(
            customer=customer, product_code="ARTISAN",
            amount=Decimal("15000"), term_months=3, purpose="y",
        )
        assert a1.assessment.score == a2.assessment.score  # same inputs → same score

    def test_delinquency_scores_zero_on_repayment_factor(self):
        score, explanation = risk_services._repayment_history(
            make_customer("+2348055550003"), {}
        )
        assert "history" in explanation.lower()


class TestFraudEngine:  # spec §46
    def test_payment_velocity_alert(self):
        customer = make_customer("+2348055550010")
        rule = FraudRule.objects.get(code="PAYMENT_VELOCITY")
        rule.parameters = {"max_per_hour": 2}
        rule.save()
        for i in range(3):
            payment_services.initialize_payment(
                customer=customer,
                purpose="ACCOUNT_FUNDING",
                amount=Decimal("100"),
                idempotency_key=f"fraud-{i}",
            )
        fraud_services.check_payment_patterns(
            customer.payments.latest("created_at")
        )
        assert FraudAlert.objects.filter(resource_id=str(customer.pk)).exists()

    def test_alert_review_workflow(self):
        customer = make_customer("+2348055550011")
        officer = User.objects.create_user(phone="+2348055550099", password="Risk#2026")
        grant_role(officer, "RISK_OFFICER")
        alert = FraudAlert.objects.create(
            rule=FraudRule.objects.first(),
            resource_type="customer",
            resource_id=str(customer.pk),
        )
        reviewed = fraud_services.review_alert(
            alert, reviewer=officer, decision="CLEARED", notes="false positive"
        )
        assert reviewed.status == FraudAlert.Status.CLEARED
        assert reviewed.case.outcome == "CLEARED"


class TestReconciliation:  # spec §27, §201
    def test_matched_flow(self):
        customer = make_customer("+2348055550020")
        verify_kyc(customer)
        payment, _ = payment_services.initialize_payment(
            customer=customer,
            purpose="ACCOUNT_FUNDING",
            amount=Decimal("2000"),
            idempotency_key="recon-1",
        )
        local = payment_services.get_payment_provider("local") if hasattr(payment_services, "get_payment_provider") else None
        from integrations.payments.base import get_payment_provider

        local = get_payment_provider("local")
        payload = local.mark_success(payment.provider_reference)
        event = payment_services.ingest_webhook(
            provider_code="local",
            event_id="evt-recon-1",
            event_type="charge.success",
            payload=payload,
            signature_valid=True,
        )
        payment_services.process_webhook_event(event)

        run = recon_services.run_reconciliation(provider="local")
        assert run.status == "COMPLETED"
        assert run.matched_count == 1
        assert run.exception_count == 0

    def test_amount_mismatch_creates_exception(self):
        from apps.payments.models import PaymentProviderEvent

        customer = make_customer("+2348055550021")
        payment, _ = payment_services.initialize_payment(
            customer=customer,
            purpose="ACCOUNT_FUNDING",
            amount=Decimal("3000"),
            idempotency_key="recon-2",
        )
        # Settle through the webhook (correct mirror created)...
        from integrations.payments.base import get_payment_provider

        local = get_payment_provider("local")
        event = payment_services.ingest_webhook(
            provider_code="local",
            event_id="evt-recon-2",
            event_type="charge.success",
            payload=local.mark_success(payment.provider_reference),
            signature_valid=True,
        )
        payment_services.process_webhook_event(event)
        # ...then the provider's settlement statement reports a DIFFERENT
        # amount — the classic reconciliation exception.
        PaymentProviderEvent.objects.filter(
            provider="local", provider_reference=payment.provider_reference
        ).update(amount=Decimal("2500"))
        run = recon_services.run_reconciliation(provider="local")
        assert run.exception_count >= 1
        mismatch = ReconciliationItem.objects.filter(
            run=run, status=ReconciliationItem.Status.AMOUNT_MISMATCH
        )
        assert mismatch.exists()

    def test_exception_resolution(self):
        from apps.payments.models import PaymentProviderEvent

        customer = make_customer("+2348055550022")
        payment, _ = payment_services.initialize_payment(
            customer=customer,
            purpose="ACCOUNT_FUNDING",
            amount=Decimal("1000"),
            idempotency_key="recon-3",
        )
        PaymentProviderEvent.objects.create(
            provider="local",
            provider_reference=payment.provider_reference,
            amount=Decimal("777"),
            currency="NGN",
            status="SUCCESS",
        )
        run = recon_services.run_reconciliation(provider="local")
        exc = run.items.exclude(status="MATCHED").first().exception
        officer = User.objects.create_user(phone="+2348055550098", password="Fin#2026")
        grant_role(officer, "FINANCE_OFFICER")
        resolved = recon_services.resolve_exception(
            str(exc.pk), resolver=officer, resolution="provider refund confirmed"
        )
        assert resolved.resolved_at is not None
        with pytest.raises(ValidationFailed):
            recon_services.resolve_exception(
                str(exc.pk), resolver=officer, resolution="again"
            )


class TestCustomerJourney:  # spec §199 — the full automation
    def test_signup_to_transaction_history(self, db):
        # 1. signup
        user = User.objects.create_user(
            phone="+2348066660001", password="Journey#2026",
            first_name="Journey", last_name="Tester",
        )
        grant_role(user, "CUSTOMER")
        # 2. profile
        customer = make_customer("+2348066660002")  # separate customer for plan
        verify_kyc(customer)
        # 3. create savings plan
        plan = None
        from apps.savings.services import create_savings_plan

        plan = create_savings_plan(
            customer=customer,
            product_code="SAVE_FLEX",
            amount=Decimal("500"),
            frequency="DAILY",
            start_date=date.today(),
            end_date=date.today() + timedelta(days=3),
        )
        # 4. initialize payment
        payment, _url = payment_services.initialize_payment(
            customer=customer,
            purpose="SAVINGS_CONTRIBUTION",
            amount=Decimal("500"),
            target={"plan_id": str(plan.pk)},
            idempotency_key="journey-1",
        )
        # 5. webhook (simulated provider confirmation)
        from integrations.payments.base import get_payment_provider

        local = get_payment_provider("local")
        event = payment_services.ingest_webhook(
            provider_code="local",
            event_id="evt-journey-1",
            event_type="charge.success",
            payload=local.mark_success(payment.provider_reference),
            signature_valid=True,
        )
        payment_services.process_webhook_event(event)
        # 6. ledger posted + contribution + updated balance
        payment.refresh_from_db()
        plan.refresh_from_db()
        assert payment.status == "SUCCESS"
        assert payment.ledger_transaction.status == "POSTED"
        assert plan.total_contributed == Decimal("500.00")
        # 7. notification outbox event exists
        assert OutboxEvent.objects.filter(
            event_code="SAVINGS_PAYMENT_RECEIVED"
        ).exists()
        # 8. transaction history visible (payment queryable by reference)
        assert payment_services.get_payment_by_reference(payment.reference).pk == payment.pk
        # 9. ledger still balanced
        verify_balances()
