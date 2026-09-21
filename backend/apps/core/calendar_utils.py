"""Shared calendar stepping for ALL financial schedules (spec §18, §96).

Month-end anchoring: 31 Jan → 28 Feb (clamped) → 31 Mar (restored).
Without this, schedules drift to month-ends forever after a short month.
"""

from __future__ import annotations

from datetime import date

from dateutil.relativedelta import relativedelta

FREQUENCY_DELTA: dict[str, dict] = {
    "DAILY": {"days": 1},
    "WEEKLY": {"weeks": 1},
    "MONTHLY": {"months": 1},
    "QUARTERLY": {"months": 3},
    "BIYEARLY": {"months": 6},
    "YEARLY": {"years": 1},
}

_MONTHS_PER_PERIOD = {"MONTHLY": 1, "QUARTERLY": 3, "BIYEARLY": 6, "YEARLY": 12}


def add_calendar_step(anchor: date, current: date, frequency: str) -> date:
    """Advance one period on the real calendar, anchored to the start day."""
    next_date = current + relativedelta(**FREQUENCY_DELTA[frequency])
    if frequency in _MONTHS_PER_PERIOD:
        months = _MONTHS_PER_PERIOD[frequency]
        target_day = anchor.day
        months_between = (next_date.year - anchor.year) * 12 + (next_date.month - anchor.month)
        if months_between % months == 0 and next_date.day < target_day:
            try:
                return next_date.replace(day=target_day)
            except ValueError:
                return next_date  # e.g. Feb 30 does not exist — keep clamped
    return next_date
