"""Agent application services (spec §29–§34, §58, §146).

Every operation:
  - validates agent status + device + limits (race-safe via select_for_update)
  - posts through the ledger
  - is idempotent
  - emits notifications via the outbox
"""

from __future__ import annotations

import logging
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.audit.models import AuditAction, record_audit
from apps.core.errors import (
    Conflict,
    InsufficientFunds,
    InvalidStateTransition,
    LimitExceeded,
    NotFound,
    ValidationFailed,
)
from apps.core.middleware import get_request_id
from apps.core.money import money
from apps.core.references import next_reference
from apps.ledger.services import EntrySpec, post_transaction
from apps.notifications.services import emit_event

from .models import (
    Agent,
    AgentDevice,
    AgentFloatMovement,
    AgentLimit,
    AgentSettlement,
    AgentTransaction,
    AgentTerritory,
    CommissionRule,
    CommissionTransaction,
)

logger = logging.getLogger("rfund.agents")


def get_agent_by_user(user) -> Agent:
    agent = Agent.objects.select_related("limits", "territory").filter(user=user).first()
    if agent is None:
        raise NotFound("Agent profile not found.")
    return agent


@transaction.atomic
def register_agent(
    *,
    user,
    territory_code: str,
    business_name: str = "",
    phone: str = "",
    limits: dict | None = None,
    registered_by=None,
) -> Agent:
    territory = AgentTerritory.objects.filter(code=territory_code).first()
    if territory is None:
        raise ValidationFailed("Unknown territory.")
    if Agent.objects.filter(user=user).exists():
        raise Conflict("This user already has an agent profile.")
    count = Agent.objects.count()
    agent = Agent.objects.create(
        agent_code=f"AG-{count + 1:05d}",
        user=user,
        territory=territory,
        business_name=business_name,
        phone=phone or user.phone,
    )
    AgentLimit.objects.create(agent=agent, **(limits or {}))
    record_audit(
        action=AuditAction.CREATE,
        resource_type="agent",
        resource_id=str(agent.pk),
        actor=registered_by or user,
        after={"agent_code": agent.agent_code},
        request_id=get_request_id(),
    )
    return agent


def register_device(agent: Agent, *, fingerprint: str, device_name: str = "",
                    os_version: str = "", app_version: str = "") -> AgentDevice:
    device, _ = AgentDevice.objects.get_or_create(
        fingerprint=fingerprint,
        defaults={
            "agent": agent,
            "device_name": device_name,
            "os_version": os_version,
            "app_version": app_version,
            "last_seen": timezone.now(),
        },
    )
    if device.agent_id != agent.pk:
        raise Conflict("This device is registered to a different agent.")
    return device


def _validate_agent_ready(agent: Agent, device: AgentDevice | None) -> None:
    if agent.status != Agent.Status.ACTIVE:
        raise InvalidStateTransition("This agent account is not active.")
    if device is not None and device.status != AgentDevice.Status.ACTIVE:
        # A deactivated device must NEVER transact (§30)
        raise InvalidStateTransition("This device has been disabled.")


def _daily_total(agent: Agent, txn_type: str) -> Decimal:
    start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    agg = AgentTransaction.objects.filter(
        agent=agent,
        txn_type=txn_type,
        status=AgentTransaction.Status.SUCCESS,
        performed_at__gte=start,
    ).aggregate(total=Sum("amount"))
    return agg["total"] or Decimal("0")


@transaction.atomic
def agent_cash_collection(
    *,
    agent: Agent,
    customer,
    amount,
    purpose: str = "SAVINGS_CONTRIBUTION",
    target: dict | None = None,
    device: AgentDevice | None = None,
    idempotency_key: str = "",
    client_reference: str = "",
) -> AgentTransaction:
    """Customer → agent cash → RFUND savings (§31 flow)."""
    amount = money(amount)
    if amount <= 0:
        raise ValidationFailed("Amount must be greater than zero.")
    _validate_agent_ready(agent, device)

    if idempotency_key:
        existing = AgentTransaction.objects.filter(idempotency_key=idempotency_key).first()
        if existing is not None:
            if existing.amount != amount or existing.customer_id != customer.pk:
                raise Conflict("Idempotency key reused with different details.")
            return existing

    # Lock the agent row FIRST so limit checks are serialized under
    # concurrency (§58) — computing totals before locking is a TOCTOU race.
    Agent.objects.select_for_update().get(pk=agent.pk)

    limits, _created = AgentLimit.objects.get_or_create(agent=agent)
    if amount > limits.single_transaction_limit:
        raise LimitExceeded(
            f"Amount exceeds the single transaction limit (₦{limits.single_transaction_limit:,.0f})."
        )
    if _daily_total(agent, AgentTransaction.Type.CASH_COLLECTION) + amount > limits.daily_cash_in_limit:
        raise LimitExceeded("Daily cash collection limit reached.")
    month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    monthly = AgentTransaction.objects.filter(
        agent=agent, status=AgentTransaction.Status.SUCCESS, performed_at__gte=month_start
    ).aggregate(total=Sum("amount"))["total"] or Decimal("0")
    if monthly + amount > limits.monthly_limit:
        raise LimitExceeded("Monthly transaction limit reached.")

    opening = _agent_cash_balance(agent)
    txn = AgentTransaction(
        reference=next_reference("AGC"),
        agent=agent,
        customer=customer,
        txn_type=AgentTransaction.Type.CASH_COLLECTION,
        amount=amount,
        status=AgentTransaction.Status.VALIDATED,
        device=device,
        idempotency_key=idempotency_key,
        client_reference=client_reference,
        purpose=purpose,
        target=target or {},
    )
    ledger_txn = post_transaction(
        txn_type="AGENT_CASH_COLLECTION",
        description=f"Agent collection {txn.reference} for customer {customer.customer_reference}",
        currency="NGN",
        entries=[
            EntrySpec(account="CASH_IN_HAND", direction="DEBIT", amount=amount,
                      metadata={"agent": agent.agent_code, "txn": "pending"}),
            EntrySpec(account="SAVINGS_POOL", direction="CREDIT", amount=amount,
                      metadata={"customer": str(customer.pk)}),
        ],
        created_by=agent.user,
        external_reference=txn.reference,
        idempotency_key=f"agentcoll:{idempotency_key or txn.reference}",
    )
    txn.ledger_transaction = ledger_txn
    txn.status = AgentTransaction.Status.SUCCESS
    txn.save()
    AgentFloatMovement.objects.create(
        agent=agent,
        transaction=txn,
        direction=AgentFloatMovement.Direction.IN,
        amount=amount,
        opening_balance=opening,
        closing_balance=money(opening + amount),
    )
    _accrue_commission(txn)
    # Route the money to the savings domain (same effect as a payment)
    _apply_agent_target(txn)
    emit_event("SAVINGS_PAYMENT_RECEIVED", {
        "customer_id": str(customer.pk),
        "amount": str(amount),
        "agent_reference": txn.reference,
    })
    record_audit(
        action=AuditAction.CREATE,
        resource_type="agent_transaction",
        resource_id=str(txn.pk),
        actor=agent.user,
        after={"reference": txn.reference, "amount": str(amount)},
        request_id=get_request_id(),
    )
    return txn


def _apply_agent_target(txn: AgentTransaction) -> None:
    """Route agent-collected money to its domain target."""
    target = txn.target or {}
    if txn.purpose == "SAVINGS_CONTRIBUTION" and target.get("plan_id"):
        from apps.savings.models import SavingsContribution, SavingsPlan
        from apps.payments.models import Payment

        plan = SavingsPlan.objects.get(pk=target["plan_id"])
        # Agent collections are recorded like payments for uniform history
        payment = Payment.objects.create(
            reference=next_reference("PAY"),
            customer=txn.customer,
            purpose=Payment.Purpose.SAVINGS_CONTRIBUTION,
            amount=txn.amount,
            status=Payment.Status.SUCCESS,
            method=Payment.Method.AGENT_CASH,
            provider="agent",
            provider_reference=txn.reference,
            target=target,
            completed_at=timezone.now(),
            ledger_transaction=txn.ledger_transaction,
            idempotency_key=f"agent:{txn.reference}",
        )
        from apps.savings.services import apply_contribution_to_plan

        apply_contribution_to_plan(payment, txn.ledger_transaction)


def _agent_cash_balance(agent: Agent) -> Decimal:
    from apps.ledger.models import LedgerAccount

    acct = LedgerAccount.objects.filter(code="CASH_IN_HAND").first()
    if acct is None:
        return Decimal("0")
    return acct.balance  # aggregate across agents; per-agent via float movements


def agent_float_balance(agent: Agent) -> Decimal:
    """Per-agent collected-not-settled amount (float ledger §32)."""
    movements_in = AgentFloatMovement.objects.filter(
        agent=agent, direction=AgentFloatMovement.Direction.IN
    ).aggregate(total=Sum("amount"))["total"] or Decimal("0")
    movements_out = AgentFloatMovement.objects.filter(
        agent=agent, direction=AgentFloatMovement.Direction.OUT
    ).exclude(settlement__isnull=False).aggregate(total=Sum("amount"))["total"] or Decimal("0")
    settled_out = AgentFloatMovement.objects.filter(
        agent=agent, direction=AgentFloatMovement.Direction.OUT,
        settlement__status=AgentSettlement.Status.SETTLED,
    ).aggregate(total=Sum("amount"))["total"] or Decimal("0")
    return money(movements_in - movements_out - settled_out)


@transaction.atomic
def agent_customer_payout(
    *,
    agent: Agent,
    customer,
    amount,
    purpose: str = "SAVINGS_PAYOUT",
    device: AgentDevice | None = None,
    idempotency_key: str = "",
) -> AgentTransaction:
    """RFUND savings → customer cash via agent (§31)."""
    amount = money(amount)
    if amount <= 0:
        raise ValidationFailed("Amount must be greater than zero.")
    _validate_agent_ready(agent, device)
    if idempotency_key:
        existing = AgentTransaction.objects.filter(idempotency_key=idempotency_key).first()
        if existing is not None:
            return existing

    # Serialize payout limit checks the same way as collections (§58).
    Agent.objects.select_for_update().get(pk=agent.pk)
    limits, _ = AgentLimit.objects.get_or_create(agent=agent)
    if amount > limits.single_transaction_limit:
        raise LimitExceeded("Amount exceeds the single transaction limit.")
    if _daily_total(agent, AgentTransaction.Type.CUSTOMER_PAYOUT) + amount > limits.daily_payout_limit:
        raise LimitExceeded("Daily payout limit reached.")

    from apps.ledger.models import LedgerAccount
    from django.db.models import Sum

    savings_pool = LedgerAccount.objects.select_for_update().get(code="SAVINGS_POOL")
    if savings_pool.balance < amount and not savings_pool.allow_negative:
        raise InsufficientFunds()

    opening = _agent_cash_balance(agent)
    txn = AgentTransaction(
        reference=next_reference("AGP"),
        agent=agent,
        customer=customer,
        txn_type=AgentTransaction.Type.CUSTOMER_PAYOUT,
        amount=amount,
        status=AgentTransaction.Status.VALIDATED,
        device=device,
        idempotency_key=idempotency_key,
        purpose=purpose,
    )
    ledger_txn = post_transaction(
        txn_type="AGENT_PAYOUT",
        description=f"Agent payout {txn.reference} to customer {customer.customer_reference}",
        currency="NGN",
        entries=[
            EntrySpec(account="SAVINGS_POOL", direction="DEBIT", amount=amount,
                      metadata={"customer": str(customer.pk)}),
            EntrySpec(account="CASH_IN_HAND", direction="CREDIT", amount=amount,
                      metadata={"agent": agent.agent_code}),
        ],
        created_by=agent.user,
        external_reference=txn.reference,
        idempotency_key=f"agentpay:{idempotency_key or txn.reference}",
    )
    txn.ledger_transaction = ledger_txn
    txn.status = AgentTransaction.Status.SUCCESS
    txn.save()
    AgentFloatMovement.objects.create(
        agent=agent,
        transaction=txn,
        direction=AgentFloatMovement.Direction.OUT,
        amount=amount,
        opening_balance=opening,
        closing_balance=money(opening - amount),
    )
    emit_event("PAYOUT_COMPLETED", {
        "customer_id": str(customer.pk),
        "amount": str(amount),
        "agent_reference": txn.reference,
    })
    return txn


@transaction.atomic
def request_agent_settlement(agent: Agent, *, amount=None, requested_by=None) -> AgentSettlement:
    """Agent requests to hand over collected cash (§33 workflow)."""
    float_balance = agent_float_balance(agent)
    amount = money(amount or float_balance)
    if amount <= 0:
        raise InvalidStateTransition("There is nothing to settle.")
    if amount > float_balance:
        raise ValidationFailed("Settlement amount exceeds collected float.")
    settlement = AgentSettlement.objects.create(
        reference=next_reference("AGS"),
        agent=agent,
        amount=amount,
        status=AgentSettlement.Status.SETTLEMENT_REQUESTED,
        requested_by=requested_by or agent.user,
        requested_at=timezone.now(),
    )
    record_audit(
        action=AuditAction.CREATE,
        resource_type="agent_settlement",
        resource_id=str(settlement.pk),
        actor=requested_by or agent.user,
        after={"reference": settlement.reference, "amount": str(amount)},
        request_id=get_request_id(),
    )
    return settlement


@transaction.atomic
def review_agent_settlement(settlement: AgentSettlement, *, reviewer, approve: bool, reason: str = "") -> AgentSettlement:
    if settlement.status not in (
        AgentSettlement.Status.SETTLEMENT_REQUESTED,
        AgentSettlement.Status.UNDER_REVIEW,
    ):
        raise InvalidStateTransition("This settlement is not awaiting review.")
    if approve:
        settlement.status = AgentSettlement.Status.UNDER_REVIEW
        settlement.reviewed_by = reviewer
        settlement.save(update_fields=["status", "reviewed_by"])
    else:
        settlement.status = AgentSettlement.Status.REJECTED
        settlement.reviewed_by = reviewer
        settlement.reason = reason
        settlement.save(update_fields=["status", "reviewed_by", "reason"])
        record_audit(
            action=AuditAction.REJECT,
            resource_type="agent_settlement",
            resource_id=str(settlement.pk),
            actor=reviewer,
            reason=reason,
            request_id=get_request_id(),
        )
    return settlement


@transaction.atomic
def approve_agent_settlement(settlement: AgentSettlement, *, approver) -> AgentSettlement:
    """Finance officer approves: cash moves from agent to settlement account."""
    if settlement.status != AgentSettlement.Status.UNDER_REVIEW:
        raise InvalidStateTransition("Settlement must be under review before approval.")
    float_balance = agent_float_balance(settlement.agent)
    if float_balance < settlement.amount:
        raise InsufficientFunds("Agent float is less than the settlement amount.")

    ledger_txn = post_transaction(
        txn_type="AGENT_SETTLEMENT",
        description=f"Agent settlement {settlement.reference}",
        currency="NGN",
        entries=[
            EntrySpec(account="SETTLEMENT", direction="DEBIT", amount=settlement.amount,
                      metadata={"agent": settlement.agent.agent_code}),
            EntrySpec(account="CASH_IN_HAND", direction="CREDIT", amount=settlement.amount,
                      metadata={"agent": settlement.agent.agent_code}),
        ],
        created_by=approver,
        external_reference=settlement.reference,
        idempotency_key=f"agentsettle:{settlement.reference}",
    )
    opening = _agent_cash_balance(settlement.agent)
    AgentFloatMovement.objects.create(
        agent=settlement.agent,
        settlement=settlement,
        direction=AgentFloatMovement.Direction.OUT,
        amount=settlement.amount,
        opening_balance=opening,
        closing_balance=money(opening - settlement.amount),
    )
    settlement.ledger_transaction = ledger_txn
    settlement.status = AgentSettlement.Status.SETTLED
    settlement.settled_by = approver
    settlement.settled_at = timezone.now()
    settlement.save()
    record_audit(
        action=AuditAction.SETTLE,
        resource_type="agent_settlement",
        resource_id=str(settlement.pk),
        actor=approver,
        after={"reference": settlement.reference, "status": "SETTLED"},
        request_id=get_request_id(),
    )
    return settlement


def _accrue_commission(txn: AgentTransaction) -> None:
    """Commission accrual per active rules (§146). Posted at settlement."""
    from apps.core.money import D

    for rule in CommissionRule.objects.filter(active=True).filter(
        txn_type__in=["", txn.txn_type]
    ):
        amount = rule.compute(txn.amount)
        if amount > 0:
            CommissionTransaction.objects.get_or_create(
                agent=txn.agent, rule=rule, source=txn,
                defaults={"amount": amount},
            )


def settle_commissions(agent: Agent, *, settled_by) -> Decimal:
    """Pay accrued commissions — always through the ledger (§146)."""
    accrued = CommissionTransaction.objects.filter(
        agent=agent, status=CommissionTransaction.Status.ACCRUED
    )
    total = money(sum(c.amount for c in accrued) or Decimal("0"))
    if total <= 0:
        return Decimal("0")
    post_transaction(
        txn_type="COMMISSION",
        description=f"Commission payout for {agent.agent_code}",
        currency="NGN",
        entries=[
            EntrySpec(account="COMMISSION_EXPENSE", direction="DEBIT", amount=total,
                      metadata={"agent": agent.agent_code}),
            EntrySpec(account="SETTLEMENT", direction="CREDIT", amount=total,
                      metadata={"agent": agent.agent_code}),
        ],
        created_by=settled_by,
        idempotency_key=f"commission:{agent.agent_code}:{timezone.now():%Y%m%d%H%M}",
    )
    accrued.update(status=CommissionTransaction.Status.PAID)
    return total


@transaction.atomic
def set_agent_status(agent: Agent, new_status: str, *, actor=None, reason: str = "") -> Agent:
    if new_status not in Agent.Status.values:
        raise ValidationFailed("Invalid agent status.")
    if agent.status == new_status:
        return agent
    before = agent.status
    agent.status = new_status
    agent.save(update_fields=["status", "updated_at"])
    record_audit(
        action=AuditAction.SUSPEND if new_status == "SUSPENDED" else (
            AuditAction.REINSTATE if new_status == "ACTIVE" else AuditAction.UPDATE
        ),
        resource_type="agent",
        resource_id=str(agent.pk),
        actor=actor,
        before={"status": before},
        after={"status": new_status},
        reason=reason,
        request_id=get_request_id(),
    )
    return agent
