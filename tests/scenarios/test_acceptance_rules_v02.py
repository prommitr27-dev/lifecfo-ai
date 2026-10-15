"""Acceptance tests AT1 to AT12 from Financial Rules v0.2.

AT13, AT14, and AT16 are in test_acceptance.py; AT15 is at the end of this file.
Numbers are worked out by hand in the comments so they can be checked.
"""

from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from lifecfo.agents import AgentContext, DeterministicAgent, Tier, default_registry
from lifecfo.agents.agent import unverified_numbers
from lifecfo.agents.views import debt_comparison, expense_scenario, planning_data
from lifecfo.cashflow.position import ShortfallKind, assess_position
from lifecfo.database import Store
from lifecfo.debt import InterestBasis, schedule_debts
from lifecfo.domain import Debt, FixedClock, Goal, thb
from lifecfo.domain.loader import load_state
from lifecfo.domain.models import Envelope, EnvelopeKind, Frequency
from lifecfo.optimization import PlanningStatus, apply_plan, generate_plans, validate_plan
from lifecfo.services import SandboxService
from lifecfo.services.sandbox import AGENT
from tests.conftest import with_income

ROOT = Path(__file__).resolve().parents[2]
DEBT_PROFILE = ROOT / "data" / "synthetic" / "profile_debt_demo.yaml"
YEAR = 365


def plans_by_strategy(state, months=12):
    return {p.strategy: p for p in generate_plans(state, horizon_months=months).plans}


def leisure(state):
    return next(e for e in state.expenses if e.id == "leisure")


# --- AT1: flexible-spending reduction ------------------------------------------------


def test_at1_proposal_stays_in_the_permitted_range_and_shows_the_original(demo_state):
    data = planning_data(demo_state, 12)
    for plan in data["plans"]:
        flex = plan["flexible_spending"]
        assert flex["original_budget_first_month"] == 3000
        assert 2000 <= flex["proposed_first_month"] <= 3000
    for plan in generate_plans(demo_state).plans:
        assert all(thb(2000) <= m.flexible["leisure"] <= thb(3000) for m in plan.months)


def test_at1_no_reduction_is_proposed_without_permission(demo_state):
    fixed = demo_state.model_copy(update={"expenses": tuple(
        e.model_copy(update={"reduction_allowed": False}) if e.id == "leisure" else e
        for e in demo_state.expenses)})
    for plan in generate_plans(fixed).plans:
        assert all(m.flexible["leisure"] == thb(3000) for m in plan.months)


def test_at1_not_applied_before_approval_and_kept_when_declined(demo_state):
    sandbox = SandboxService(Store(), FixedClock(datetime(2026, 11, 1, tzinfo=UTC)))
    sandbox.reset(demo_state)
    plan = plans_by_strategy(sandbox.state)["SAFETY_FIRST"]
    assert plan.months[0].flexible["leisure"] == thb(2000)  # a proposed cut
    plan_id = sandbox.propose(plan, AGENT).data["plan_id"]
    assert leisure(sandbox.state).amount == thb(3000)  # not applied by proposing
    sandbox.decide(plan_id, False)
    assert leisure(sandbox.state).amount == thb(3000)  # declined: original kept
    assert leisure(sandbox.state).frequency is Frequency.MONTHLY


# --- AT2: original budget deficit ----------------------------------------------------


@pytest.fixture
def deficit_state(demo_state):
    # 20,500 - 18,000 essentials - 3,000 flexible budget = -500 a month.
    return with_income(demo_state, amount=thb(20500))


def test_at2_original_deficit_is_disclosed_first(deficit_state):
    data = planning_data(deficit_state, 12)
    position = data["original_position"]
    assert position["monthly_budget"]["surplus_under_original_budget"] == -500
    assert position["original_budget_deficit"] > 0
    kinds = [s["kind"] for s in position["shortfalls"]]
    assert "FLEXIBLE_SPENDING_CONSTRAINT" in kinds
    reply = DeterministicAgent().reply(AgentContext(deficit_state), "Compare the three plans")
    assert reply.text.index("a deficit of 500 THB a month") < reply.text.index("I generated")


def test_at2_adjusted_plan_is_separate_and_shows_its_effects(deficit_state):
    data = planning_data(deficit_state, 12)
    assert data["status"] == "OK"  # at the 2,000 minimum the budget balances
    for plan in data["plans"]:
        assert plan["status"] == "PROPOSED_NOT_APPROVED"
        assert plan["flexible_spending"]["reduction_first_month"] > 0
        assert all("shortfall_kinds" in g for g in plan["goals"])


def test_at2_without_permission_no_plan_is_presented_as_feasible(deficit_state):
    fixed = deficit_state.model_copy(update={"expenses": tuple(
        e.model_copy(update={"reduction_allowed": False}) if e.id == "leisure" else e
        for e in deficit_state.expenses)})
    result = generate_plans(fixed)
    assert result.status is PlanningStatus.FLEXIBLE_SPENDING_CONSTRAINT
    assert result.plans == ()
    reply = DeterministicAgent().reply(AgentContext(fixed), "Compare the three plans")
    assert "No plan can be offered without changing one of your preferences" in reply.text


# --- AT3: essentials unaffordable ----------------------------------------------------


def test_at3_cash_flow_shortfall_is_disclosed_and_nothing_is_reduced(demo_state):
    low = with_income(demo_state, amount=thb(15000))
    result = generate_plans(low)
    assert result.status is PlanningStatus.ESSENTIAL_SHORTFALL and result.plans == ()
    assert result.position.has(ShortfallKind.CASH_FLOW_SHORTFALL)
    assert low.monthly_essentials == thb(18000)  # untouched
    text = DeterministicAgent().reply(AgentContext(low), "Compare the three plans").text
    assert "They are not reduced" in text and "I generated" not in text


# --- AT4: minimum cash buffer --------------------------------------------------------


def test_at4_buffer_shortfall_is_shown_and_protected_cash_is_not_allocated(demo_state):
    position = assess_position(demo_state, YEAR)
    # Accessible cash 0 + 6,000 against a 1-month buffer of 18,000.
    assert position.buffer.target == thb(18000)
    assert position.buffer.shortfall_now == thb(12000)
    assert position.has(ShortfallKind.BUFFER_SHORTFALL)
    goal_envelopes = {"env-laptop", "env-travel"}
    for plan in generate_plans(demo_state).plans:
        assert plan.months_below_buffer
        for month in plan.months:
            if month.buffer_shortfall:
                assert not goal_envelopes & set(month.contributions)
                assert not month.extra_debt


def test_at4_the_buffer_preference_is_never_changed_by_a_plan(demo_state):
    for plan in generate_plans(demo_state).plans:
        applied = apply_plan(demo_state, plan)
        assert applied.buffer_months == demo_state.buffer_months == 1


# --- AT5: emergency-fund calculation -------------------------------------------------


def test_at5_reserve_target_and_gap(demo_state):
    debt = Debt(id="loan", name="Loan", balance=thb(50000), minimum_payment=thb(2000),
                day_of_month=10, apr=0.1)
    envelopes = tuple(e.model_copy(update={"balance": thb(25000)})
                      if e.kind is EnvelopeKind.EMERGENCY else e for e in demo_state.envelopes)
    state = demo_state.model_copy(update={"debts": (debt,), "envelopes": envelopes})
    reserve = assess_position(state, YEAR).reserve
    assert reserve.target == thb(60000)  # 3 x (18,000 + 2,000)
    assert reserve.gap == thb(35000)  # 60,000 - 25,000


def test_at5_custom_target_overrides_the_formula(demo_state):
    custom = demo_state.model_copy(update={"reserve_target": thb(40000)})
    reserve = assess_position(custom, YEAR).reserve
    assert reserve.target == thb(40000) and reserve.custom and reserve.months is None


# --- AT6: no double counting of buffer and reserve ----------------------------------


def test_at6_accessible_cash_is_counted_once_and_goal_money_is_excluded(demo_state):
    envelopes = tuple(e.model_copy(update={"balance": thb(5000)}) if e.id == "env-laptop"
                      else e for e in demo_state.envelopes)
    state = demo_state.model_copy(update={"envelopes": envelopes})
    position = assess_position(state, YEAR)
    assert position.cash.accessible == thb(6000)  # 0 unallocated + 6,000 reserve
    assert position.cash.committed_to_goals == thb(5000)
    assert position.reserve.eligible == thb(6000)
    # The buffer and the reserve are separate rules on the same 6,000, not 12,000 of cash.
    assert position.buffer.accessible_now == position.reserve.eligible == thb(6000)


def test_at6_upcoming_obligations_are_not_treated_as_free(demo_state):
    position = assess_position(demo_state, YEAR)
    # 30,000 income in November against 21,000 of bills and flexible spending.
    assert position.uncommitted_next_month == thb(9000)


# --- AT7: debt interest ---------------------------------------------------------------


def test_at7_contract_estimate_and_unknown_rate_are_kept_apart():
    state = load_state(DEBT_PROFILE)
    schedules = schedule_debts(state, state.as_of, date(2026, 11, 30))
    loan, card, store = schedules["loan"], schedules["card"], schedules["store"]
    assert loan.basis is InterestBasis.CONTRACT_BASED
    # 12,000 x 15% x 9 days / 365 from 1 to 10 November.
    assert loan.periods[0].interest == round(thb(12000) * 0.15 * 9 / 365)
    assert card.basis is InterestBasis.ESTIMATED
    assert any("365" in note for note in card.notes)
    assert store.basis is InterestBasis.UNAVAILABLE
    assert store.total_interest is None and store.payoff_date is None
    assert all(p.interest is None for p in store.periods)  # never shown as 0


# --- AT8: extra debt repayment --------------------------------------------------------


def test_at8_only_residual_cash_goes_to_extra_repayment():
    state = load_state(DEBT_PROFILE)
    for plan in generate_plans(state, horizon_months=6).plans:
        assert validate_plan(state, plan).ok
        assert not plan.months_below_buffer
        # 35,000 - 17,000 essentials - 3,000 minimums - 2,500 flexible = 12,500 at most.
        assert sum(plan.months[0].extra_debt.values()) <= thb(12500)
    # With the buffer unmet nothing goes to extra repayment in those months.
    short = state.model_copy(update={"envelopes": (
        Envelope(id="unallocated", kind=EnvelopeKind.UNALLOCATED, balance=0),
        Envelope(id="emergency", kind=EnvelopeKind.EMERGENCY, balance=0))})
    for plan in generate_plans(short, horizon_months=6).plans:
        for month in plan.months:
            if month.buffer_shortfall:
                assert not month.extra_debt


def test_at8_strategies_differ_and_the_user_can_override_the_order():
    state = load_state(DEBT_PROFILE)
    data = debt_comparison(state, 6, None)
    orders = {c["strategy"]: c["order"] for c in data["comparisons"]}
    assert orders["AVALANCHE"][0] == "Credit card"  # 25% is the highest known rate
    assert orders["SNOWBALL"][0] == "Store installment"  # 4,000 is the smallest balance
    custom = state.model_copy(update={"debt_order": ("loan", "store", "card")})
    data = debt_comparison(custom, 6, None)
    assert {c["strategy"]: c["order"] for c in data["comparisons"]}["YOUR_ORDER"] == [
        "Personal loan", "Store installment", "Credit card"]
    assert data["status"] == "PROPOSAL_NOT_APPROVED"
    assert any("unknown" in note for note in data["assumptions_and_limitations"])


def test_at8_proposal_is_not_applied_without_approval():
    state = load_state(DEBT_PROFILE)
    sandbox = SandboxService(Store(), FixedClock(datetime(2026, 11, 1, tzinfo=UTC)))
    sandbox.reset(state)
    plan = generate_plans(sandbox.state, horizon_months=6).plans[1]
    sandbox.propose(plan, AGENT)
    assert sandbox.state.debt_payments == ()
    assert sandbox.execute(None, AGENT).code == "NO_APPROVAL"
    assert sandbox.state.debt_payments == ()


# --- AT9: flexible and non-flexible goals --------------------------------------------


def test_at9_flexible_goal_gets_an_option_and_non_flexible_gets_a_risk(demo_state):
    data = planning_data(demo_state, 12)
    safety = next(p for p in data["plans"] if p["strategy"] == "Safety First")
    vacation = next(g for g in safety["goals"] if g["name"] == "Vacation")
    assert vacation["flexible"] and "FLEXIBLE_GOAL_DELAY" in vacation["shortfall_kinds"]
    assert data["alternatives"][0]["goal"] == "Vacation"
    assert data["alternatives"][0]["requires_approval"] is True

    strict = demo_state.model_copy(update={"goals": tuple(
        g.model_copy(update={"flexible": False}) for g in demo_state.goals)})
    data = planning_data(strict, 12)
    safety = next(p for p in data["plans"] if p["strategy"] == "Safety First")
    vacation = next(g for g in safety["goals"] if g["name"] == "Vacation")
    assert "DEADLINE_RISK" in vacation["shortfall_kinds"]
    assert data["alternatives"] == []


def test_at9_targets_and_deadlines_are_never_changed(demo_state):
    for plan in generate_plans(demo_state).plans:
        for projection, goal in zip(plan.goals, demo_state.goals, strict=True):
            assert projection.target == goal.target and projection.deadline == goal.deadline


# --- AT10: zero allocation to a lower-priority goal ----------------------------------


def test_at10_zero_allocation_is_explained_and_not_a_cancellation(demo_state):
    data = planning_data(demo_state, 12)
    notes = [g["zero_allocation_note"] for p in data["plans"] for g in p["goals"]
             if g.get("zero_allocation_note")]
    assert notes and all("not a cancellation" in n for n in notes)
    for plan in generate_plans(demo_state).plans:
        assert {g.goal_id for g in plan.goals} == {"laptop", "travel"}


# --- AT11: goal without a deadline ---------------------------------------------------


def test_at11_no_deadline_goal_is_horizon_stable_and_gets_no_invented_date(demo_state):
    goals = (*demo_state.goals, Goal(id="bike", name="Bike", target=thb(20000), priority=3))
    envelopes = (*demo_state.envelopes,
                 Envelope(id="env-bike", kind=EnvelopeKind.GOAL, goal_id="bike", balance=0))
    state = demo_state.model_copy(update={"goals": goals, "envelopes": envelopes})
    short, long = plans_by_strategy(state, 6), plans_by_strategy(state, 12)
    for name in short:
        first_six = [m.contributions.get("env-bike", 0) for m in long[name].months[:6]]
        assert [m.contributions.get("env-bike", 0) for m in short[name].months] == first_six
        bike = next(g for g in long[name].goals if g.goal_id == "bike")
        assert bike.deadline is None and bike.on_track is None
    data = planning_data(state, 12)
    bike = next(g for g in data["plans"][0]["goals"] if g["name"] == "Bike")
    assert bike["deadline"] is None and "no_deadline_note" in bike
    assert "average_per_month" in bike and "remaining_after_horizon" in bike


# --- AT12: unexpected expense --------------------------------------------------------


def test_at12_expense_recalculates_liquidity_reserve_and_buffer(demo_state):
    before = demo_state.model_dump()
    data = expense_scenario(demo_state, thb(10000), date(2026, 11, 12), 12)
    # 12 Nov: 30,000 - 11,000 - 9,000 - 10,000 = 0; the 1,000 bill on the 15th needs the reserve.
    assert data["not_covered_by_unallocated_cash"] == 1000
    assert data["reserve_withdrawal_needed"] == 1000
    assert data["emergency_reserve"]["balance_after_withdrawal"] == 5000
    assert data["emergency_reserve"]["gap_after"] == 49000
    assert data["accessible_cash"]["with_expense"] == 6000  # 0 unallocated + 6,000 reserve
    assert data["cash_buffer"]["shortfall_after_expense"] == 12000
    assert data["recovery_options"]["plans"]
    assert all(p["status"] == "PROPOSED_NOT_APPROVED" for p in data["recovery_options"]["plans"])
    assert demo_state.model_dump() == before


def test_at12_explanation_numbers_come_from_the_calculation(demo_state):
    question = "What if I get a 10,000 THB repair bill?"
    reply = DeterministicAgent().reply(AgentContext(demo_state), question)
    assert reply.trace[0].name == "simulate_unexpected_expense"
    assert unverified_numbers(reply.text, question, reply.trace) == []


# --- AT15: high-APR debt forecast (six months) ---------------------------------------


def test_at15_six_month_debt_forecast_respects_minimums_and_liquidity():
    state = load_state(DEBT_PROFILE)
    data = default_registry().call(AgentContext(state), "compare_debt_strategies",
                                   {"months": 6}, Tier.COMPUTE).data
    assert data["months"] == 6 and data["required_minimums_per_month"] == 3000
    for comparison in data["comparisons"]:
        for debt in comparison["debts"]:
            assert debt["minimum_paid"] > 0
    avalanche, snowball = data["comparisons"][0], data["comparisons"][1]
    assert avalanche["total_interest_where_calculable"] <= (
        snowball["total_interest_where_calculable"])
    assert avalanche["interest_incomplete"]  # the store installment rate is unknown
    assert any("on the debts whose interest can be calculated" in f for f in data["facts"])
    for plan in generate_plans(state, horizon_months=6).plans:
        assert validate_plan(state, plan).ok
