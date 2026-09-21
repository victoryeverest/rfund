"""Ledger posting engine — all money movement goes through here (§3, §14–§16, §57).

Design:
  - `post_transaction` is the ONLY way money moves. It:
      1. validates balance (debits == credits), currencies, account status
      2. locks all affected account rows (select_for_update, deterministic order)
      3. creates the transaction + entries + updates balance projections
         in ONE database transaction
      4. honors idempotency keys — replays return the original transaction
  - `reverse_transaction` creates a compensating transaction (never edits).
  - `verify_balances` recomputes every projection from entries (audit).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.core.errors import (
    Conflict,
    IdempotencyConflict,
    InvalidStateTransition,
    PermissionDenied,
    ValidationFailed,
)
from apps.core.middleware import get_request_id
from apps.core.money import D, money
from apps.core.references import next_reference
from apps.ledger.models import (
    BalanceSnapshot,
    LedgerAccount,
    LedgerEntry,
    LedgerTransaction,
)
from apps.audit.models import AuditAction, record_audit

logger = logging.getLogger("rfund.ledger")


# ---------------------------------------------------------------------------
# Chart of accounts bootstrap
# ---------------------------------------------------------------------------
CORE_ACCOUNTS = [
    # (code, name, type, allow_negative)
    ("SETTLEMENT", "Payment provider settlement", "ASSET", True),
    ("CASH_IN_HAND", "Agent cash in hand (aggregate)", "ASSET", True),
    ("AGENT_FLOAT", "Agent float liability", "LIABILITY", True),
    ("SAVINGS_POOL", "Customer savings pool (control)", "LIABILITY", False),
    ("LOAN_PRINCIPAL", "Loans receivable - principal", "ASSET", True),
    ("INTEREST_INCOME", "Interest income", "INCOME", False),
    ("FEE_INCOME", "Fee income", "INCOME", False),
    ("PENALTY_INCOME", "Penalty income", "INCOME", False),
    ("OPERATING_EXPENSE", "Operating expenses", "EXPENSE", True),
    ("COMMISSION_EXPENSE", "Agent commission expense", "EXPENSE", True),
    ("OPENING_EQUITY", "Opening equity", "EQUITY", True),
]


def ensure_core_accounts() -> None:
    for code, name, type_, allow_negative in CORE_ACCOUNTS:
        LedgerAccount.objects.get_or_create(
            code=code,
            defaults={
                "name": name,
                "type": type_,
                "allow_negative": allow_negative,
            },
        )


# ---------------------------------------------------------------------------
# Posting
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class EntrySpec:
    account: str | LedgerAccount
    direction: LedgerEntry.Direction
    amount: Decimal | int | str
    metadata: dict | None = None


def _resolve_account(account: str | LedgerAccount) -> LedgerAccount:
    if isinstance(account, LedgerAccount):
        return account
    acct = LedgerAccount.objects.filter(code=account).first()
    if acct is None:
        raise ValidationFailed(f"Ledger account {account!r} does not exist.")
    return acct


def _account_code(account: str | LedgerAccount) -> str:
    return account.code if isinstance(account, LedgerAccount) else account


def validate_balance(entries: list[EntrySpec]) -> Decimal:
    """sum(debits) must equal sum(credits) (§3.3). Returns the total."""
    debits = Decimal("0")
    credits = Decimal("0")
    for e in entries:
        amount = money(e.amount)
        if amount <= 0:
            raise ValidationFailed("Every ledger entry amount must be greater than zero.")
        if e.direction == LedgerEntry.Direction.DEBIT:
            debits += amount
        else:
            credits += amount
    if len(entries) < 2:
        raise ValidationFailed("A ledger transaction needs at least two entries.")
    if debits != credits:
        raise ValidationFailed(
            "The transaction is not balanced: total debits must equal total credits."
        )
    if debits == 0:
        raise ValidationFailed("A ledger transaction must move a positive amount.")
    return debits


def _signed_effect(account: LedgerAccount, entry: LedgerEntry) -> Decimal:
    """Effect of an entry on the account's natural balance sign."""
    debit_positive = account.type in (
        LedgerAccount.Type.ASSET,
        LedgerAccount.Type.EXPENSE,
    )
    if entry.direction == LedgerEntry.Direction.DEBIT:
        return entry.amount if debit_positive else -entry.amount
    return -entry.amount if debit_positive else entry.amount


def _apply_to_balance(account: LedgerAccount, effect: Decimal) -> None:
    new_balance = account.balance + effect
    if new_balance < 0 and not account.allow_negative:
        raise ValidationFailed(
            f"Account {account.code} cannot go negative "
            f"(attempted balance: {new_balance})."
        )
    account.balance = new_balance


def get_by_idempotency_key(key: str) -> LedgerTransaction | None:
    if not key:
        return None
    return (
        LedgerTransaction.objects.filter(idempotency_key=key)
        .prefetch_related("entries__account")
        .first()
    )


def idempotency_fingerprint(entries: list[EntrySpec], txn_type: str, currency: str) -> str:
    """Stable description of the financial effect — replays must match exactly."""
    parts = [txn_type, currency]
    for e in sorted(entries, key=lambda x: (_account_code(x.account), x.direction)):
        parts.append(f"{_account_code(e.account)}:{e.direction}:{money(e.amount)}")
    return "|".join(parts)


@transaction.atomic
def post_transaction(
    *,
    txn_type: str,
    description: str = "",
    currency: str = "NGN",
    entries: list[EntrySpec],
    created_by=None,
    external_reference: str = "",
    idempotency_key: str = "",
    reversal_of: LedgerTransaction | None = None,
    audit_reason: str = "",
) -> LedgerTransaction:
    """Post a balanced transaction atomically. The money-movement gateway."""
    # ---- Idempotency (§3.5) --------------------------------------------
    if idempotency_key:
        existing = get_by_idempotency_key(idempotency_key)
        if existing is not None:
            fingerprint = idempotency_fingerprint(entries, txn_type, currency)
            stored = (existing.description or "").split(" #idem:", 1)
            stored_fp = _stored_fingerprint(existing)
            if stored_fp and stored_fp != fingerprint:
                raise IdempotencyConflict(
                    "This request was already processed with different details."
                )
            logger.info(
                "ledger_idempotent_replay",
                extra={"event": "ledger_idempotent_replay", "reference": existing.reference},
            )
            return existing

    if currency not in ("NGN", "USD", "EUR", "GBP"):
        raise ValidationFailed(f"Unsupported currency {currency!r}.")

    # ---- Validate the entry set (§3.3) ----------------------------------
    total = validate_balance(entries)
    if reversal_of is not None:
        if reversal_of.status != LedgerTransaction.Status.POSTED:
            raise InvalidStateTransition("Only posted transactions can be reversed.")
        if reversal_of.reversals.filter(status=LedgerTransaction.Status.POSTED).exists():
            raise Conflict("This transaction has already been reversed.")

    # ---- Resolve + lock accounts (§57: row-level locking) ---------------
    codes = sorted({_account_code(e.account) for e in entries})
    locked = {}
    for code in codes:
        acct = LedgerAccount.objects.select_for_update().filter(code=code).first()
        if acct is None:
            raise ValidationFailed(f"Ledger account {code!r} does not exist.")
        if acct.status != LedgerAccount.Status.ACTIVE:
            raise InvalidStateTransition(f"Account {code} is not active.")
        if acct.currency != currency:
            raise ValidationFailed(
                f"Account {code} holds {acct.currency}; cannot post {currency}."
            )
        locked[code] = acct

    # ---- Create + post ----------------------------------------------------
    txn = LedgerTransaction(
        reference=next_reference("LED"),
        transaction_type=txn_type,
        status=LedgerTransaction.Status.VALIDATING,
        currency=currency,
        description=description,
        external_reference=external_reference,
        idempotency_key=idempotency_key,
        created_by=created_by,
        posted_by=created_by,
        reversal_of=reversal_of,
    )
    # Store fingerprint inside description tail for idempotency conflict checks
    if idempotency_key:
        fingerprint = idempotency_fingerprint(entries, txn_type, currency)
        txn.description = f"{description} #idem:{fingerprint}".strip()

    effects: dict[str, Decimal] = {}
    entry_rows: list[LedgerEntry] = []
    for e in entries:
        acct = locked[_account_code(e.account)]
        amount = money(e.amount)
        entry = LedgerEntry(
            transaction=txn,
            account=acct,
            direction=e.direction,
            amount=amount,
            currency=currency,
            metadata=e.metadata or {},
        )
        entry_rows.append(entry)
        effects.setdefault(acct.code, Decimal("0"))
        effects[acct.code] += _signed_effect(acct, entry)

    # Apply balance effects with negativity guards (spec §82)
    for code, effect in effects.items():
        _apply_to_balance(locked[code], effect)

    txn.status = LedgerTransaction.Status.POSTED
    txn.posted_at = timezone.now()
    txn.save()
    for entry in entry_rows:
        entry.save()

    now = timezone.now()
    for code in effects:
        acct = locked[code]
        acct.last_posted_at = now
        acct.save(update_fields=["balance", "last_posted_at", "updated_at"])

    record_audit(
        action=AuditAction.CREATE,
        resource_type="ledger_transaction",
        resource_id=str(txn.pk),
        actor=created_by,
        after={
            "reference": txn.reference,
            "type": txn_type,
            "amount": str(total),
            "currency": currency,
            "accounts": sorted(effects.keys()),
        },
        reason=audit_reason,
        request_id=get_request_id(),
    )
    logger.info(
        "ledger_posted",
        extra={
            "event": "ledger_posted",
            "reference": txn.reference,
            "operation": txn_type,
            "status": "POSTED",
            "actor": str(created_by) if created_by else "system",
        },
    )
    return txn


def _stored_fingerprint(txn: LedgerTransaction) -> str | None:
    if not txn.description or "#idem:" not in txn.description:
        return None
    return txn.description.split(" #idem:", 1)[1]


@transaction.atomic
def reverse_transaction(
    transaction: LedgerTransaction,
    *,
    reversed_by=None,
    reason: str,
    idempotency_key: str = "",
) -> LedgerTransaction:
    """Create the compensating transaction. Original stays untouched (§3.1)."""
    if not reason or not reason.strip():
        raise ValidationFailed("A reversal reason is required.")
    if transaction.status != LedgerTransaction.Status.POSTED:
        raise InvalidStateTransition("Only posted transactions can be reversed.")
    if transaction.transaction_type == LedgerTransaction.Type.REVERSAL:
        raise InvalidStateTransition("A reversal cannot itself be reversed.")
    if transaction.reversals.filter(status=LedgerTransaction.Status.POSTED).exists():
        raise Conflict("This transaction has already been reversed.")

    entries = list(transaction.entries.select_related("account"))
    opposite = {
        LedgerEntry.Direction.DEBIT: LedgerEntry.Direction.CREDIT,
        LedgerEntry.Direction.CREDIT: LedgerEntry.Direction.DEBIT,
    }
    specs = [
        EntrySpec(
            account=e.account.code,
            direction=opposite[e.direction],
            amount=e.amount,
            metadata={"reversal_of_entry": str(e.pk)},
        )
        for e in entries
    ]
    reversal = post_transaction(
        txn_type=LedgerTransaction.Type.REVERSAL,
        description=f"Reversal of {transaction.reference}: {reason[:180]}",
        currency=transaction.currency,
        entries=specs,
        created_by=reversed_by,
        external_reference=transaction.reference,
        idempotency_key=idempotency_key or f"reversal:{transaction.reference}",
        reversal_of=transaction,
        audit_reason=reason,
    )
    record_audit(
        action=AuditAction.REVERSE,
        resource_type="ledger_transaction",
        resource_id=str(transaction.pk),
        actor=reversed_by,
        after={"reversal_reference": reversal.reference},
        reason=reason,
        request_id=get_request_id(),
    )
    return reversal


# ---------------------------------------------------------------------------
# Accounts management
# ---------------------------------------------------------------------------
@transaction.atomic
def create_account(
    *,
    code: str,
    name: str,
    type: str,
    currency: str = "NGN",
    allow_negative: bool = False,
    holder_customer=None,
    holder_agent=None,
    opening_balance: Decimal | None = None,
    created_by=None,
) -> LedgerAccount:
    code = code.strip().upper()
    if not code or not code.replace("_", "").isalnum():
        raise ValidationFailed("Account code must be alphanumeric/underscore.")
    if LedgerAccount.objects.filter(code=code).exists():
        raise Conflict(f"Ledger account {code} already exists.")
    account = LedgerAccount(
        code=code,
        name=name,
        type=type,
        currency=currency,
        allow_negative=allow_negative,
        holder_customer=holder_customer,
        holder_agent=holder_agent,
    )
    account.full_clean()
    account.save()
    if opening_balance is not None and D(opening_balance) != 0:
        # Opening balances are posted as ledger transactions against equity.
        amount = money(opening_balance)
        debit_positive = account.type in (
            LedgerAccount.Type.ASSET,
            LedgerAccount.Type.EXPENSE,
        )
        entries = [
            EntrySpec(
                account=account,
                direction=(
                    LedgerEntry.Direction.DEBIT if (amount > 0) == debit_positive
                    else LedgerEntry.Direction.CREDIT
                ),
                amount=abs(amount),
            ),
            EntrySpec(
                account="OPENING_EQUITY",
                direction=(
                    LedgerEntry.Direction.CREDIT if (amount > 0) == debit_positive
                    else LedgerEntry.Direction.DEBIT
                ),
                amount=abs(amount),
            ),
        ]
        post_transaction(
            txn_type=LedgerTransaction.Type.OPENING,
            description=f"Opening balance for {code}",
            currency=currency,
            entries=entries,
            created_by=created_by,
        )
    record_audit(
        action=AuditAction.CREATE,
        resource_type="ledger_account",
        resource_id=str(account.pk),
        actor=created_by,
        after={"code": code, "type": type},
        request_id=get_request_id(),
    )
    return account


def account_balance(code: str) -> Decimal:
    acct = LedgerAccount.objects.filter(code=code).first()
    if acct is None:
        raise ValidationFailed(f"Ledger account {code!r} does not exist.")
    return acct.balance


def customer_savings_balance(customer) -> Decimal:
    """Sum of the customer's savings-product control accounts (2dp)."""
    from apps.core.money import money as _money

    total = Decimal("0")
    accounts = LedgerAccount.objects.filter(holder_customer=customer)
    for acct in accounts:
        total += acct.balance
    return _money(total)


def snapshot_all_balances() -> int:
    """Persist BalanceSnapshots for every account (Celery beat job)."""
    count = 0
    for account in LedgerAccount.objects.all():
        entry_count = account.entries.count()
        BalanceSnapshot.objects.update_or_create(
            account=account,
            as_of=timezone.now().replace(microsecond=0),
            defaults={"balance": account.balance, "entry_count": entry_count},
        )
        count += 1
    return count


def verify_balances(account_codes: list[str] | None = None) -> dict[str, Decimal]:
    """Recompute projections from entries; raise on drift (audit job)."""
    qs = LedgerAccount.objects.all()
    if account_codes:
        qs = qs.filter(code__in=account_codes)
    drift: dict[str, Decimal] = {}
    for account in qs.prefetch_related("entries"):
        computed = account.computed_balance()
        if computed != account.balance:
            drift[account.code] = account.balance - computed
    if drift:
        logger.error("ledger_balance_drift", extra={"structured": {"drift": {k: str(v) for k, v in drift.items()}}})
        raise Conflict(
            f"Ledger balance drift detected: {drift}. Entries are authoritative."
        )
    return {}
