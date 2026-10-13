from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from lifecfo.domain import (
    Envelope,
    EnvelopeKind,
    Expense,
    ExpenseCategory,
    FinancialState,
    FixedClock,
    IncomeSource,
    format_thb,
    thb,
)
from lifecfo.domain.clock import local_date
from lifecfo.domain.loader import parse_state
from lifecfo.domain.schedule import monthly_occurrences


def test_thb_converts_to_integer_satang():
    assert thb(30000) == 3_000_000
    assert thb("0.1") + thb("0.2") == thb("0.3")
    assert thb(10.005) == 1001  # half up, no float drift


def test_format_thb():
    assert format_thb(123_450) == "1,234.50 THB"
    assert format_thb(-50) == "-0.50 THB"


def test_monthly_occurrences_clamp_to_month_end():
    dates = monthly_occurrences(31, date(2027, 1, 1), date(2027, 4, 30))
    assert dates == [date(2027, 1, 31), date(2027, 2, 28), date(2027, 3, 31), date(2027, 4, 30)]


def test_monthly_occurrences_respect_window_and_active_range():
    dates = monthly_occurrences(
        10, date(2026, 11, 11), date(2027, 2, 9), active_to=date(2027, 1, 10)
    )
    assert dates == [date(2026, 12, 10), date(2027, 1, 10)]


def test_fixed_clock_uses_user_timezone_for_dates():
    clock = FixedClock(datetime(2026, 11, 1, 18, 30, tzinfo=UTC))
    assert local_date(clock, "Asia/Bangkok") == date(2026, 11, 2)
    clock.advance(days=1)
    assert local_date(clock, "Asia/Bangkok") == date(2026, 11, 3)


def test_models_are_immutable(demo_state):
    with pytest.raises(ValidationError):
        demo_state.as_of = date(2030, 1, 1)
    with pytest.raises(ValidationError):
        demo_state.envelopes[0].balance = 1


def test_negative_and_zero_amounts_rejected():
    with pytest.raises(ValidationError):
        IncomeSource(id="i", name="x", amount=0, day_of_month=1)
    with pytest.raises(ValidationError):
        Envelope(id="e", kind=EnvelopeKind.EMERGENCY, balance=-1)


def test_essential_expense_cannot_be_reduced():
    with pytest.raises(ValidationError):
        Expense(id="rent", name="Rent", category=ExpenseCategory.ESSENTIAL, amount=100,
                min_amount=50, day_of_month=1)


def test_flexible_floor_defaults_to_zero():
    expense = Expense(id="fun", name="Fun", category=ExpenseCategory.FLEXIBLE, amount=100,
                      day_of_month=1)
    assert expense.floor == 0


def test_state_requires_exactly_one_unallocated_envelope():
    with pytest.raises(ValidationError, match="exactly one UNALLOCATED"):
        FinancialState(as_of=date(2026, 11, 1), envelopes=())


def test_state_rejects_transfer_to_unknown_envelope():
    raw = {
        "as_of": "2026-11-01",
        "envelopes": [{"id": "u", "kind": "UNALLOCATED", "balance_thb": 0}],
        "transfers": [{"id": "t", "envelope_id": "missing", "amount_thb": 10, "day_of_month": 1}],
    }
    with pytest.raises(ValidationError, match="unknown or UNALLOCATED"):
        parse_state(raw)


def test_loader_reads_demo_profile(demo_state):
    assert demo_state.total_cash == thb(6000)
    assert demo_state.unallocated.balance == 0
    assert sum(i.amount for i in demo_state.incomes) == thb(30000)
    planned_out = (
        sum(e.amount for e in demo_state.expenses) + sum(t.amount for t in demo_state.transfers)
    )
    assert planned_out == thb(30000)
