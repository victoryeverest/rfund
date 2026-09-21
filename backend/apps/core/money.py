"""Money handling (spec §3.3, §3.4, §179).

Rules:
  - Python `Decimal` ONLY. Floats are forbidden for money.
  - Two decimal places (kobo-aware) for NGN; quantization helpers enforce it.
  - Every amount carries an explicit currency in the database.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Iterable

TWO_PLACES = Decimal("0.01")
ZERO = Decimal("0.00")


class MoneyError(ValueError):
    pass


def D(value: Decimal | int | str) -> Decimal:
    """Strict decimal constructor for money values.

    Accepts int and str; floats are rejected outright to prevent
    binary-fraction contamination (spec §3.3: never float for money).
    """
    if isinstance(value, float):
        raise MoneyError("Floats are forbidden for money. Use str or Decimal.")
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise MoneyError(f"Invalid decimal value: {value!r}") from exc


def money(value: Decimal | int | str) -> Decimal:
    """Normalize to 2 decimal places with ROUND_HALF_UP."""
    return D(value).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def is_non_negative(value: Decimal) -> bool:
    return value >= 0


def is_positive(value: Decimal) -> bool:
    return value > 0


def total(values: Iterable[Decimal]) -> Decimal:
    result = Decimal("0")
    for v in values:
        result += D(v)
    return result


def allocate(
    amount: Decimal,
    weights: list[Decimal],
) -> list[Decimal]:
    """Largest-remainder allocation of `amount` across `weights`.

    Guarantees the parts sum EXACTLY to `amount` (no lost kobo) and each
    part is >= 0 when amount >= 0. Used for repayment allocation and
    schedule splitting.
    """
    amount = money(amount)
    if not weights:
        raise MoneyError("allocate() requires at least one weight")
    if any(w < 0 for w in weights):
        raise MoneyError("weights must be non-negative")
    weight_sum = sum(weights)
    if weight_sum == 0:
        # Equal split
        weights = [Decimal(1)] * len(weights)
        weight_sum = Decimal(len(weights))

    raw = [(amount * w) / weight_sum for w in weights]
    parts = [r.quantize(TWO_PLACES, rounding=ROUND_HALF_UP) for r in raw]
    remainder = amount - sum(parts)
    if remainder != 0:
        # Distribute kobo one-by-one to the largest fractional remainders.
        order = sorted(
            range(len(raw)),
            key=lambda i: (raw[i] - parts[i]),
            reverse=True,
        )
        step = Decimal("0.01") if remainder > 0 else Decimal("-0.01")
        i = 0
        while remainder != 0:
            parts[order[i % len(order)]] += step
            remainder -= step
            i += 1
    return parts


def format_naira(value: Decimal) -> str:
    """Human display only — never used for storage or arithmetic."""
    return f"₦{D(value):,.2f}"
