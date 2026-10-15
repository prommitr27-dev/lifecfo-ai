"""Economics decisions 1 to 6 (answers to section 4 of RULES_V0.2_STATUS.md)."""

from datetime import date
from pathlib import Path

from lifecfo.agents.views import debt_comparison, expense_scenario, planning_data
from lifecfo.debt import payoff_order, schedule_debts
from lifecfo.domain import Goal, thb
from lifecfo.domain.loader import load_state
from lifecfo.domain.models import DebtStrategy, Envelope, EnvelopeKind
from lifecfo.optimization import generate_plans, validate_plan

DEBT_PROFILE = Path(__file__).resolve().parents[2] / "data" / "synthetic" / "profile_debt_demo.yaml"


def test_decision_1_buffer_cuts_are_proposals_with_a_keep_the_budget_option(demo_state):
    data = planning_data(demo_state, 12)
    cuts = [p for p in data["plans"] if p["flexible_spending"]["reduction_first_month"]]
    assert cuts and all(p["status"] == "PROPOSED_NOT_APPROVED" for p in cuts)
    assert all(p["flexible_spending"]["proposed_first_month"] >= 2000 for p in cuts)
    keep = next(a for a in data["alternatives"] if a["kind"] == "KEEP_FLEXIBLE_BUDGET")
    assert keep["possible"] and "Essentials are never reduced" in keep["note"]


def test_decision_2_extra_repayment_waits_for_goal_allocations():
    state = load_state(DEBT_PROFILE)
    goal = Goal(id="bike", name="Bike", target=thb(20000), priority=3)
    with_goal = state.model_copy(update={
        "goals": (goal,),
        "envelopes": (*state.envelopes,
                      Envelope(id="env-bike", kind=EnvelopeKind.GOAL, goal_id="bike", balance=0))})
    for plan in generate_plans(with_goal, horizon_months=6).plans:
        assert validate_plan(with_goal, plan).ok
        bike_done = next(g for g in plan.goals if g.goal_id == "bike").completion_month
        for month in plan.months:
            if month.extra_debt:
                # Extra repayment starts only once the goal no longer needs money.
                assert bike_done is not None and month.month >= bike_done


def test_decision_3_unknown_rate_debt_is_disclosed_and_never_zero():
    state = load_state(DEBT_PROFILE)
    store = schedule_debts(state, state.as_of, date(2027, 4, 30))["store"]
    assert store.total_interest is None and store.payoff_date is None
    assert len([p for p in store.periods if p.minimum_paid]) == 6  # minimum continues
    notes = " ".join(debt_comparison(state, 6, None)["assumptions_and_limitations"])
    assert "not assumed to be 0%" in notes


def test_decision_4_prepayment_fees_are_excluded_and_disclosed():
    state = load_state(DEBT_PROFILE)
    debts = tuple(d.model_copy(update={"prepayment_fee_possible": True}) if d.id == "loan"
                  else d for d in state.debts)
    state = state.model_copy(update={"debts": debts})
    data = debt_comparison(state, 6, None)
    assert all(d["fees"] == 0 for c in data["comparisons"] for d in c["debts"])
    assert any("excludes any such fee" in n for n in data["assumptions_and_limitations"])


def test_decision_5_unknown_rates_rank_last_in_avalanche_with_an_explanation():
    state = load_state(DEBT_PROFILE)
    assert payoff_order(state, DebtStrategy.AVALANCHE) == ["card", "loan", "store"]
    notes = " ".join(debt_comparison(state, 6, None)["assumptions_and_limitations"])
    assert "not because it is the lowest" in notes
    rated = state.model_copy(update={"debts": tuple(
        d.model_copy(update={"apr": 0.4}) if d.id == "store" else d for d in state.debts)})
    assert payoff_order(rated, DebtStrategy.AVALANCHE)[0] == "store"  # recalculated


def test_decision_6_simulated_withdrawal_is_on_the_profile_date_and_not_recorded(demo_state):
    before = demo_state.model_dump()
    data = expense_scenario(demo_state, thb(10000), date(2026, 11, 12), 12)
    assert data["reserve_withdrawal_needed"] == 1000
    assert data["emergency_reserve"]["balance_after_withdrawal"] == 5000
    assert "on the profile date" in data["limitation"]
    assert demo_state.model_dump() == before
