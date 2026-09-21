"""Money arithmetic tests (spec §3.3, §3.4, §81, §179)."""

from decimal import Decimal

import pytest

from apps.core.money import D, allocate, format_naira, money


class TestStrictDecimal:
    def test_floats_are_rejected(self):
        with pytest.raises(Exception):
            D(10.5)

    def test_int_and_str_accepted(self):
        assert D(10) == Decimal("10")
        assert D("123.45") == Decimal("123.45")

    def test_money_quantizes_to_two_places(self):
        assert money("10.005") == Decimal("10.01")  # ROUND_HALF_UP
        assert money("10.004") == Decimal("10.00")

    def test_format_naira_is_display_only(self):
        assert format_naira(Decimal("1234.5")) == "₦1,234.50"


class TestFinancialEdgeAmounts:  # spec §81
    @pytest.mark.parametrize("value", ["0", "1", "999", "1000", "100000", "1000000"])
    def test_exact_round_trip(self, value):
        assert str(money(value)) == f"{Decimal(value):.2f}"

    def test_kobo_precision_preserved(self):
        assert money("0.01") == Decimal("0.01")
        assert money("999999999.99") == Decimal("999999999.99")


class TestAllocate:
    def test_equal_split_sums_exactly(self):
        parts = allocate(Decimal("100"), [Decimal(1), Decimal(1), Decimal(1)])
        assert sum(parts) == Decimal("100.00")
        assert parts[0] == Decimal("33.34")  # largest remainder gets the extra kobo

    def test_uneven_split_no_lost_kobo(self):
        parts = allocate(Decimal("1000"), [Decimal("1"), Decimal("2"), Decimal("7")])
        assert sum(parts) == Decimal("1000.00")

    def test_repeated_allocation_is_deterministic(self):
        a = allocate(Decimal("10"), [Decimal(1), Decimal(1), Decimal(1)])
        b = allocate(Decimal("10"), [Decimal(1), Decimal(1), Decimal(1)])
        assert a == b

    @pytest.mark.parametrize("amount", ["0.01", "1", "999.99", "12345.67"])
    def test_many_random_splits_sum_exact(self, amount):
        parts = allocate(Decimal(amount), [Decimal(3), Decimal(7), Decimal(11)])
        assert sum(parts) == money(amount)
        assert all(p >= 0 for p in parts)

    def test_single_bucket(self):
        assert allocate(Decimal("55.55"), [Decimal(2)]) == [Decimal("55.55")]

    def test_zero_weights_fall_back_to_equal(self):
        parts = allocate(Decimal("10"), [Decimal(0), Decimal(0)])
        assert sum(parts) == Decimal("10.00")
