import random
from datetime import date

import pytest

from lifecfo.cashflow import forecast_cash_flow
from lifecfo.domain import (
    Envelope,
    EnvelopeKind,
    Expense,
    ExpenseCategory,
    FinancialState,
    Goal,
    IncomeSource,
    thb,
)
from lifecfo.optimization import (
    PlanningStatus,
    apply_plan,
    generate_plans,
    load_strategies,
    optimize_plan,
    validate_plan,
)
from tests.conftest import with_income


def by_strategy(result):
    return {plan.strategy: plan for plan in result.plans}


def test_three_strategies_are_valid_and_genuinely_different(demo_state):
    result = generate_plans(demo_state)
    assert result.status is PlanningStatus.OK
    assert [p.strategy for p in result.plans] == ["SAFETY_FIRST", "BALANCED", "GOAL_FIRST"]
    assert result.identical == ()
    for plan in result.plans:
        assert validate_plan(demo_state, plan).ok
        assert plan.goals_at_risk == ()


def test_strategies_trade_reserve_speed_against_goal_speed(demo_state):
    plans = by_strategy(generate_plans(demo_state))
    reserve = {name: plan.reserve.reached_month for name, plan in plans.items()}
    assert reserve["SAFETY_FIRST"] < reserve["BALANCED"] < reserve["GOAL_FIRST"]

    travel = {name: plan.goals[1].completion_month for name, plan in plans.items()}
    assert travel["GOAL_FIRST"] < travel["SAFETY_FIRST"]

    # Safety First cuts leisure to its floor while the reserve is being built.
    assert plans["SAFETY_FIRST"].months[0].flexible == {"leisure": thb(1000)}
    assert plans["BALANCED"].months[0].flexible == {"leisure": thb(3000)}


def test_plan_never_overfunds_and_conserves_cash(demo_state):
    for plan in generate_plans(demo_state).plans:
        forecast = forecast_cash_flow(apply_plan(demo_state, plan), plan.horizon_days)
        assert forecast.min_unallocated >= 0
        assert forecast.closing_envelopes["emergency"] <= demo_state.reserve_target
        assert forecast.closing_envelopes["env-laptop"] <= thb(30000)
        assert forecast.closing_envelopes["env-travel"] <= thb(15000)
        for month in plan.months:
            assert all(amount > 0 for amount in month.contributions.values())
            assert all(amount % 100 == 0 for amount in month.contributions.values())


def test_income_cut_yields_valid_plans_and_flags_goals_at_risk(demo_state):
    cut = with_income(demo_state, amount=thb(24000))
    plans = by_strategy(generate_plans(cut))
    assert len(plans) == 3
    for plan in plans.values():
        assert validate_plan(cut, plan).ok
        # 59,000 of targets cannot all be met on time from 5,000 a month of free cash.
        assert "travel" in plan.goals_at_risk
    # The higher-priority laptop goal is protected by every strategy.
    assert all(plan.goals[0].on_track for plan in plans.values())
    assert plans["GOAL_FIRST"].goals[1].shortfall_at_deadline < (
        plans["SAFETY_FIRST"].goals[1].shortfall_at_deadline
    )


def test_no_plan_is_invented_when_essentials_cannot_be_paid(demo_state):
    result = generate_plans(with_income(demo_state, amount=thb(15000)))
    assert result.status is PlanningStatus.ESSENTIAL_SHORTFALL
    assert result.plans == ()
    assert result.feasibility.essential_shortfall > 0


def test_reserve_drawdown_is_left_to_recovery(demo_state):
    # Payday on the 25th with nothing unallocated: bills are payable only from savings.
    envelopes = tuple(
        e.model_copy(update={"balance": thb(40000)}) if e.kind is EnvelopeKind.EMERGENCY else e
        for e in demo_state.envelopes
    )
    state = with_income(demo_state.model_copy(update={"envelopes": envelopes}), day_of_month=25)
    result = generate_plans(state)
    assert result.status is PlanningStatus.REQUIRES_RESERVE_DRAWDOWN
    assert result.plans == ()


def test_month_end_sweep_respects_bills_due_before_payday(demo_state):
    # Payday on the 25th with a month of cash in hand: the sweep must leave
    # enough for the bills that fall before the next payday.
    envelopes = tuple(
        e.model_copy(update={"balance": thb(25000)}) if e.kind is EnvelopeKind.UNALLOCATED else e
        for e in demo_state.envelopes
    )
    state = with_income(demo_state.model_copy(update={"envelopes": envelopes}), day_of_month=25)
    result = generate_plans(state)
    assert result.status is PlanningStatus.OK
    for plan in result.plans:
        assert validate_plan(state, plan).ok
        assert plan.months[0].closing_unallocated >= thb(19000)


def test_identical_plans_are_explained_not_disguised():
    state = FinancialState(
        as_of=date(2026, 11, 1),
        envelopes=(
            Envelope(id="unallocated", kind=EnvelopeKind.UNALLOCATED, balance=0),
            Envelope(id="env-bike", kind=EnvelopeKind.GOAL, goal_id="bike", balance=0),
        ),
        incomes=(IncomeSource(id="pay", name="Pay", amount=thb(20000), day_of_month=1),),
        expenses=(
            Expense(id="rent", name="Rent", category=ExpenseCategory.ESSENTIAL,
                    amount=thb(15000), day_of_month=5),
        ),
        goals=(Goal(id="bike", name="Bike", target=thb(40000), priority=1),),
    )
    result = generate_plans(state)
    assert result.status is PlanningStatus.OK
    assert len(result.identical) == 3  # every pair
    note = result.identical[0]
    assert note.envelopes_fully_funded == ("bike",)
    assert "identical allocations" in note.describe()


def test_validator_rejects_tampered_and_stale_plans(demo_state):
    plan = generate_plans(demo_state).plans[0]

    first = plan.months[0]
    greedy = first.model_copy(update={"contributions": {"env-laptop": thb(25000)}})
    tampered = plan.model_copy(update={"months": (greedy, *plan.months[1:])})
    result = validate_plan(demo_state, tampered)
    assert not result.ok
    assert any("Cash runs short" in v or "overfunded" in v for v in result.violations)

    below_floor = first.model_copy(update={"flexible": {"leisure": 0}})
    result = validate_plan(
        demo_state, plan.model_copy(update={"months": (below_floor, *plan.months[1:])})
    )
    assert any("must stay between" in v for v in result.violations)

    unknown = first.model_copy(update={"contributions": {"offshore": thb(1)}})
    result = validate_plan(
        demo_state, plan.model_copy(update={"months": (unknown, *plan.months[1:])})
    )
    assert any("unknown envelope" in v for v in result.violations)

    changed_state = with_income(demo_state, amount=thb(29000))
    result = validate_plan(changed_state, plan)
    assert any("different financial state" in v for v in result.violations)


def test_optimizer_is_deterministic(demo_state):
    first = [p.fingerprint() for p in generate_plans(demo_state).plans]
    second = [p.fingerprint() for p in generate_plans(demo_state).plans]
    assert first == second


def test_existing_transfers_do_not_affect_the_plan(demo_state):
    strategy = load_strategies()["BALANCED"]
    bare = demo_state.model_copy(update={"transfers": ()})
    with_transfers = optimize_plan(demo_state, strategy, 6)
    without = optimize_plan(bare, strategy, 6)
    assert with_transfers.same_allocations(without)


def _random_state(rng: random.Random) -> FinancialState:
    goals = tuple(
        Goal(id=f"g{i}", name=f"Goal {i}", target=thb(rng.randrange(5, 80) * 1000),
             priority=rng.randint(1, 3),
             deadline=rng.choice([None, date(2027, rng.randint(1, 12), rng.randint(1, 28))]))
        for i in range(rng.randint(1, 4))
    )
    envelopes = (
        Envelope(id="unallocated", kind=EnvelopeKind.UNALLOCATED,
                 balance=thb(rng.randrange(0, 40) * 1000)),
        Envelope(id="emergency", kind=EnvelopeKind.EMERGENCY,
                 balance=thb(rng.randrange(0, 20) * 1000)),
        *(Envelope(id=f"env-{g.id}", kind=EnvelopeKind.GOAL, goal_id=g.id,
                   balance=thb(rng.randrange(0, 5) * 1000)) for g in goals),
    )
    expenses = tuple(
        Expense(id=f"e{i}", name=f"Expense {i}", category=ExpenseCategory.ESSENTIAL,
                amount=thb(rng.randrange(1, 9) * 1000), day_of_month=rng.randint(1, 31))
        for i in range(rng.randint(1, 4))
    ) + tuple(
        Expense(id=f"f{i}", name=f"Flexible {i}", category=ExpenseCategory.FLEXIBLE,
                amount=thb(rng.randrange(2, 6) * 1000), min_amount=thb(rng.randrange(0, 2) * 500),
                day_of_month=rng.randint(1, 31))
        for i in range(rng.randint(0, 2))
    )
    return FinancialState(
        as_of=date(2026, rng.randint(1, 12), rng.randint(1, 28)),
        reserve_target=thb(rng.randrange(0, 40) * 1000),
        envelopes=envelopes,
        incomes=(IncomeSource(id="pay", name="Pay", amount=thb(rng.randrange(15, 60) * 1000),
                              day_of_month=rng.randint(1, 31)),),
        expenses=expenses,
        goals=goals,
    )


@pytest.mark.parametrize("seed", range(40))
def test_random_profiles_only_ever_get_valid_plans(seed):
    state = _random_state(random.Random(seed))
    result = generate_plans(state, horizon_months=9)
    if result.status is PlanningStatus.OK:
        assert len(result.plans) == 3
        for plan in result.plans:
            assert validate_plan(state, plan).ok
    else:
        assert result.plans == ()
        assert result.feasibility.min_unallocated < 0 or result.feasibility.needs_reserves
