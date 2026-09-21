"""Loan calculations (spec §39–§41, §81).

All financial math is Decimal, server-side, and tested:
  - flat interest: interest = principal × rate% × (term/12)
  - declining balance (reducing balance): per-period interest on the
    remaining principal, amortized with equal total installments
  - schedule generation on real calendar dates (relativedelta)
  - deterministic repayment allocation (penalty → fees → interest →
    principal, configurable per product §41)
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from dateutil.relativedelta import relativedelta

from apps.core.calendar_utils import add_calendar_step
from apps.core.money import D, allocate, money


def _monthly_rate(annual_rate_percent: Decimal) -> Decimal:
    """Annual percent → monthly fraction."""
    return D(annual_rate_percent) / Decimal("100") / Decimal("12")


def compute_flat_interest(principal, annual_rate_percent, term_months) -> Decimal:
    """Flat: interest charged on the full principal for the whole term."""
    principal = D(principal)
    rate = D(annual_rate_percent)
    term = D(term_months)
    return money(principal * rate / Decimal("100") * term / Decimal("12"))


def compute_declining_schedule(
    principal, annual_rate_percent, term_months
) -> list[dict]:
    """Equal-installment amortization on the declining balance.

    Returns per-period dicts: principal_due, interest_due, total_due.
    Final-period remainder is absorbed so the total is EXACT.
    """
    principal = D(principal)
    r = _monthly_rate(annual_rate_percent)
    n = D(term_months)
    if r == 0:
        per_principal = money(principal / n)
        schedule = [{"principal_due": per_principal, "interest_due": money(0)} for _ in range(int(n))]
        # exact remainder on the last installment
        shortfall = principal - sum(D(p["principal_due"]) for p in schedule)
        schedule[-1]["principal_due"] = money(schedule[-1]["principal_due"] + shortfall)
        for p in schedule:
            p["total_due"] = money(p["principal_due"] + p["interest_due"])
        return schedule
    factor = (1 + r) ** n
    installment = money(principal * r * factor / (factor - 1))
    balance = principal
    schedule: list[dict] = []
    for _ in range(int(n)):
        interest = money(balance * r)
        principal_part = money(installment - interest)
        if principal_part > balance:
            principal_part = balance
            installment_i = money(balance + interest)
        else:
            installment_i = installment
        schedule.append(
            {
                "principal_due": principal_part,
                "interest_due": interest,
                "total_due": installment_i,
            }
        )
        balance = money(balance - principal_part)
    # Absorb any 1-kobo rounding on the final line so totals are exact.
    if balance != 0:
        last = schedule[-1]
        last["principal_due"] = money(last["principal_due"] + balance)
        last["total_due"] = money(last["principal_due"] + last["interest_due"])
    for p in schedule:
        p["total_due"] = money(p["principal_due"] + p["interest_due"])
    return schedule


def compute_schedule(
    *,
    principal,
    annual_rate_percent,
    term_months,
    interest_method: str,
    first_payment_date: date,
    frequency: str = "MONTHLY",
) -> list[dict]:
    """Full repayment schedule with REAL calendar due dates (§40)."""
    if interest_method == "FLAT":
        total_interest = compute_flat_interest(principal, annual_rate_percent, term_months)
        per_interest = money(total_interest / D(term_months))
        per_principal = money(D(principal) / D(term_months))
        # exact remainders on the last installment
        p_short = D(principal) - per_principal * D(term_months)
        i_short = total_interest - per_interest * D(term_months)
        lines = []
        for i in range(term_months):
            lines.append(
                {
                    "principal_due": money(per_principal + (p_short if i == term_months - 1 else 0)),
                    "interest_due": money(per_interest + (i_short if i == term_months - 1 else 0)),
                }
            )
    elif interest_method == "DECLINING_BALANCE":
        lines = compute_declining_schedule(principal, annual_rate_percent, term_months)
    else:
        raise ValueError(f"Unsupported interest method {interest_method!r}")

    schedule = []
    current = first_payment_date
    anchor = first_payment_date
    for i, line in enumerate(lines):
        schedule.append(
            {
                "sequence": i + 1,
                "due_date": current,
                "principal_due": line["principal_due"],
                "interest_due": line["interest_due"],
                "fees_due": money(0),
                "penalty_due": money(0),
            }
        )
        current = add_calendar_step(anchor, current, frequency)
    return schedule


def compute_total_repayable(schedule: list[dict]) -> Decimal:
    return money(sum(D(item["total_due"] if "total_due" in item else
                       item["principal_due"] + item["interest_due"]) for item in schedule))


def allocate_repayment(
    *,
    amount,
    penalties_due=0,
    fees_due=0,
    interest_due=0,
    principal_due=0,
    order: list[str] | None = None,
) -> dict:
    """Deterministic allocation (§41). Default: PENALTY → FEES → INTEREST → PRINCIPAL."""
    order = order or ["PENALTY", "FEES", "INTEREST", "PRINCIPAL"]
    amount = money(amount)
    buckets = {
        "PENALTY": money(penalties_due),
        "FEES": money(fees_due),
        "INTEREST": money(interest_due),
        "PRINCIPAL": money(principal_due),
    }
    result = {"PENALTY": money(0), "FEES": money(0), "INTEREST": money(0), "PRINCIPAL": money(0)}
    remaining = amount
    for key in order:
        if key not in buckets:
            raise ValueError(f"Unknown allocation bucket {key!r}")
        take = min(remaining, buckets[key])
        result[key] = money(take)
        remaining = money(remaining - take)
    result["UNAPPLIED"] = remaining
    return result
