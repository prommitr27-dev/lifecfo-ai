from datetime import date

import pytest

from lifecfo.cashflow import (
    EventKind,
    FeasibilityStatus,
    check_feasibility,
    forecast_cash_flow,
    monthly_summary,
)
from lifecfo.domain import Debt, thb
from tests.conftest import with_income

NOV_DEC_JAN = 92  # 2026-11-01 .. 2027-01-31


def test_baseline_plan_is_exactly_funded(demo_state):
    forecast = forecast_cash_flow(demo_state, NOV_DEC_JAN)
    assert forecast.min_unallocated == 0
    assert forecast.first_shortfall_on is None
    assert forecast.days[-1].on == date(2027, 1, 31)
    # Three months of contributions land in the envelopes, on top of the opening 6,000.
    assert forecast.closing_envelopes == {
        "emergency": thb(6000 + 3 * 4000),
        "env-laptop": thb(3 * 3000),
        "env-travel": thb(3 * 2000),
    }


def test_inflows_apply_before_outflows_on_the_same_day(demo_state):
    same_day = with_income(demo_state, day_of_month=2)
    forecast = forecast_cash_flow(same_day, 30)
    assert forecast.min_unallocated >= 0
    kinds = [e.kind for e in forecast.days[1].events]
    assert kinds[0] is EventKind.INCOME
    assert kinds[-1] is EventKind.SAVINGS_TRANSFER


def test_total_cash_changes_only_by_income_and_spending(demo_state):
    forecast = forecast_cash_flow(demo_state, NOV_DEC_JAN)
    previous = forecast.opening_unallocated + forecast.opening_envelopes
    for day in forecast.days:
        external = sum(
            e.unallocated_delta for e in day.events if e.kind is not EventKind.SAVINGS_TRANSFER
        )
        assert day.total_cash == previous + external
        previous = day.total_cash


def test_forecast_does_not_mutate_state(demo_state):
    before = demo_state.model_dump()
    forecast_cash_flow(demo_state, NOV_DEC_JAN)
    check_feasibility(demo_state, NOV_DEC_JAN)
    assert demo_state.model_dump() == before


def test_twenty_percent_income_cut_makes_plan_infeasible_but_fixable(demo_state):
    cut = with_income(demo_state, amount=thb(24000))
    report = check_feasibility(cut, NOV_DEC_JAN)
    assert report.status is FeasibilityStatus.PLAN_INFEASIBLE
    # 24,000 in on the 1st, 20,000 out on the 2nd, rent of 9,000 on the 5th.
    assert report.first_shortfall_on == date(2026, 11, 5)
    # The plan overspends by 6,000 a month for three months.
    assert report.max_shortfall == thb(18000)
    # Essentials (18,000) plus the leisure floor (1,000) still fit inside 24,000.
    assert report.needs_reserves is False
    assert report.essential_shortfall == 0


def test_timing_gap_is_detected_even_when_monthly_totals_balance(demo_state):
    late_pay = with_income(demo_state, day_of_month=25)
    report = check_feasibility(late_pay, NOV_DEC_JAN)
    assert report.status is FeasibilityStatus.ESSENTIAL_SHORTFALL
    assert report.first_shortfall_on == date(2026, 11, 2)
    # Before the first payday: 18,000 essentials + 1,000 leisure floor against 6,000 saved.
    assert report.essential_shortfall == thb(13000)
    assert report.essential_shortfall_on == date(2026, 11, 2)


def test_income_below_essentials_is_an_essential_shortfall(demo_state):
    low = with_income(demo_state, amount=thb(15000))
    report = check_feasibility(low, NOV_DEC_JAN)
    assert report.status is FeasibilityStatus.ESSENTIAL_SHORTFALL
    assert report.needs_reserves is True
    # 4,000 short each month for three months, against a 6,000 emergency fund.
    assert report.essential_shortfall == thb(3 * 4000 - 6000)
    assert report.essential_shortfall_on == date(2026, 12, 5)


def test_debt_minimum_stops_when_balance_is_cleared(demo_state):
    debt = Debt(id="card", name="Credit card", balance=thb(2500), minimum_payment=thb(1000),
                day_of_month=20)
    state = with_income(demo_state, amount=thb(31000)).model_copy(update={"debts": (debt,)})
    forecast = forecast_cash_flow(state, 150)
    payments = [e.amount for d in forecast.days for e in d.events
                if e.kind is EventKind.DEBT_MINIMUM]
    assert payments == [thb(1000), thb(1000), thb(500)]


def test_monthly_summary_matches_plan(demo_state):
    summary = monthly_summary(forecast_cash_flow(demo_state, NOV_DEC_JAN))
    assert [m.month for m in summary] == ["2026-11", "2026-12", "2027-01"]
    november = summary[0]
    assert november.income == thb(30000)
    assert november.essential == thb(18000)
    assert november.flexible == thb(3000)
    assert november.transfers == thb(9000)
    assert november.closing_unallocated == 0
    assert november.closing_total_cash == thb(15000)


def test_horizon_must_be_positive(demo_state):
    with pytest.raises(ValueError):
        forecast_cash_flow(demo_state, 0)
