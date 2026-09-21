"""Calendar-correct schedule generation (spec §18, §19, §96).

NEVER approximate with fixed day multipliers (no 30.4167-day months).
We generate real calendar dates with relativedelta, clamping month-end
overflow (Jan 31 + 1 month = Feb 28), and handle leap years natively
because we operate on actual dates.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Iterable

from dateutil.relativedelta import relativedelta

from apps.savings.models import SavingsPlan


from apps.core.calendar_utils import FREQUENCY_DELTA, add_calendar_step


def _advance(current: date, frequency: str) -> date:
    """Advance one period on the real calendar."""
    return current + relativedelta(**FREQUENCY_DELTA[frequency])


def _anchor_rollover(anchor: date, current: date, frequency: str) -> date:
    """Anchored calendar step — see apps.core.calendar_utils."""
    return add_calendar_step(anchor, current, frequency)


def generate_due_dates(
    *,
    start_date: date,
    end_date: date,
    frequency: str,
) -> list[date]:
    """All contribution due dates in [start_date, end_date] on the calendar.

    The first contribution is due on the start date itself.
    """
    if start_date > end_date:
        raise ValueError("Start date must not be after end date.")
    if frequency not in FREQUENCY_DELTA:
        raise ValueError(f"Unsupported frequency {frequency!r}")
    dates: list[date] = []
    anchor = start_date
    current = start_date
    guard = 0
    while current <= end_date:
        dates.append(current)
        nxt = _anchor_rollover(anchor, current, frequency)
        if nxt <= current:  # safety: never loop forever
            raise ValueError("Schedule generation failed to advance.")
        current = nxt
        guard += 1
        if guard > 20000:  # ~54 years of daily contributions
            raise ValueError("Schedule too long (over 20,000 contributions).")
    return dates


def project_plan(
    *,
    amount,
    frequency: str,
    start_date: date,
    end_date: date,
) -> dict:
    """Server-authoritative projection (spec §21) — the calculator's engine."""
    dates = generate_due_dates(
        start_date=start_date, end_date=end_date, frequency=frequency
    )
    total = amount * len(dates)
    return {
        "contribution_count": len(dates),
        "total_amount": total,
        "first_due": dates[0],
        "last_due": dates[-1],
        "due_dates": dates,
    }


def generate_schedule_items(plan: SavingsPlan) -> list:
    """Create the persisted schedule rows for a plan."""
    from apps.savings.models import SavingsScheduleItem

    dates = generate_due_dates(
        start_date=plan.start_date, end_date=plan.end_date, frequency=plan.frequency
    )
    items = [
        SavingsScheduleItem(
            plan=plan,
            sequence=i + 1,
            due_date=d,
            amount=plan.amount,
            status=SavingsScheduleItem.Status.UPCOMING,
        )
        for i, d in enumerate(dates)
    ]
    SavingsScheduleItem.objects.bulk_create(items, batch_size=500)
    return items
