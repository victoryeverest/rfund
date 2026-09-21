"""Savings schedule calendar tests (spec §18, §19, §21, §96).

The prototype's fixed-multiplier math is forbidden; these tests pin the
real-calendar behaviour including leap years and month-end clamping.
"""

from datetime import date, timedelta

import pytest

from apps.savings.schedules import generate_due_dates, project_plan


class TestFrequencies:
    def test_daily(self):
        dates = generate_due_dates(
            start_date=date(2026, 1, 1), end_date=date(2026, 1, 10), frequency="DAILY"
        )
        assert dates == [date(2026, 1, d) for d in range(1, 11)]

    def test_weekly(self):
        dates = generate_due_dates(
            start_date=date(2026, 1, 1), end_date=date(2026, 2, 1), frequency="WEEKLY"
        )
        assert dates[0] == date(2026, 1, 1)
        assert all(
            (dates[i + 1] - dates[i]).days == 7 for i in range(len(dates) - 1)
        )

    def test_monthly_same_day(self):
        dates = generate_due_dates(
            start_date=date(2026, 1, 15), end_date=date(2026, 6, 15), frequency="MONTHLY"
        )
        assert [d.day for d in dates] == [15] * 6
        assert dates == [
            date(2026, 1, 15), date(2026, 2, 15), date(2026, 3, 15),
            date(2026, 4, 15), date(2026, 5, 15), date(2026, 6, 15),
        ]

    def test_quarterly(self):
        dates = generate_due_dates(
            start_date=date(2026, 1, 1), end_date=date(2027, 1, 1), frequency="QUARTERLY"
        )
        assert [(d.year, d.month) for d in dates] == [
            (2026, 1), (2026, 4), (2026, 7), (2026, 10), (2027, 1)
        ]

    def test_biyearly(self):
        dates = generate_due_dates(
            start_date=date(2026, 2, 1), end_date=date(2027, 12, 31), frequency="BIYEARLY"
        )
        assert [(d.year, d.month) for d in dates] == [(2026, 2), (2026, 8), (2027, 2), (2027, 8)]

    def test_yearly(self):
        dates = generate_due_dates(
            start_date=date(2026, 3, 1), end_date=date(2029, 3, 1), frequency="YEARLY"
        )
        assert len(dates) == 4


class TestMonthEndAndLeapYears:  # spec §96
    def test_jan31_clamps_feb_then_returns_to_31(self):
        dates = generate_due_dates(
            start_date=date(2026, 1, 31), end_date=date(2026, 4, 30), frequency="MONTHLY"
        )
        assert dates == [
            date(2026, 1, 31), date(2026, 2, 28), date(2026, 3, 31), date(2026, 4, 30)
        ]

    def test_leap_year_february_has_29(self):
        dates = generate_due_dates(
            start_date=date(2024, 1, 31), end_date=date(2024, 3, 31), frequency="MONTHLY"
        )
        assert dates[1] == date(2024, 2, 29)

    def test_leap_day_yearly(self):
        dates = generate_due_dates(
            start_date=date(2024, 2, 29), end_date=date(2028, 12, 31), frequency="YEARLY"
        )
        assert dates[0] == date(2024, 2, 29)
        assert dates[1] == date(2025, 2, 28)  # clamped non-leap
        assert dates[-1] == date(2028, 2, 29)  # anchor restored in leap year

    def test_year_boundary(self):
        dates = generate_due_dates(
            start_date=date(2026, 12, 15), end_date=date(2027, 1, 20), frequency="MONTHLY"
        )
        assert dates == [date(2026, 12, 15), date(2027, 1, 15)]

    def test_end_date_inclusive(self):
        # A due date falling exactly on the end date is included.
        dates = generate_due_dates(
            start_date=date(2026, 1, 1), end_date=date(2026, 2, 1), frequency="MONTHLY"
        )
        assert dates == [date(2026, 1, 1), date(2026, 2, 1)]
        # ... while the day before the next due date is not.
        dates = generate_due_dates(
            start_date=date(2026, 1, 1), end_date=date(2026, 1, 31), frequency="MONTHLY"
        )
        assert dates == [date(2026, 1, 1)]


class TestScheduleBoundaries:
    def test_start_after_end_rejected(self):
        with pytest.raises(ValueError):
            generate_due_dates(
                start_date=date(2026, 2, 1), end_date=date(2026, 1, 1), frequency="MONTHLY"
            )

    def test_unsupported_frequency_rejected(self):
        with pytest.raises(ValueError):
            generate_due_dates(
                start_date=date(2026, 1, 1), end_date=date(2026, 2, 1), frequency="HOURLY"
            )

    def test_same_day_start_end(self):
        dates = generate_due_dates(
            start_date=date(2026, 5, 5), end_date=date(2026, 5, 5), frequency="DAILY"
        )
        assert dates == [date(2026, 5, 5)]


class TestProjection:  # spec §21 — server-authoritative calculator
    def test_projection_counts_and_totals(self):
        projection = project_plan(
            amount=1000,
            frequency="DAILY",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 10),
        )
        assert projection["contribution_count"] == 10
        assert projection["total_amount"] == 10000

    def test_monthly_projection_is_calendar_exact_not_30_4167(self):
        # Jan 1 → Dec 31 monthly = 12 contributions (not 12.17 as the
        # prototype's 365/30.4167 multiplier would suggest)
        projection = project_plan(
            amount=2000,
            frequency="MONTHLY",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
        )
        assert projection["contribution_count"] == 12
        assert projection["total_amount"] == 24000
