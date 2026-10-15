"""Acceptance tests from the economics specification (AT13, AT14, AT16).

AT1 to AT12 and AT15 are not here: the part of the specification that defines
them, and the D1 to D9 decisions AT15 depends on, had not been received when
this file was written.
"""

from datetime import UTC, date, datetime

import pytest

from lifecfo.agents import AgentContext, DeterministicAgent, Tier, default_registry
from lifecfo.agents.agent import unverified_numbers
from lifecfo.database import Store
from lifecfo.domain import FixedClock, Frequency, IncomeSource, thb
from lifecfo.optimization import generate_plans
from lifecfo.optimization.reasons import max_saving_by
from lifecfo.services import SandboxService
from lifecfo.services.sandbox import AGENT


def call(state, name, **arguments):
    return default_registry().call(AgentContext(state), name, arguments, Tier.COMPUTE).data


# --- AT13: income shock ----------------------------------------------------------------


def test_at13_income_change_applies_over_the_whole_horizon(demo_state):
    data = call(demo_state, "simulate_income_change", percent=-20, horizon_months=12)
    # 6,000 short in each of the 12 months of the horizon, not just the first one.
    assert data["current_plan"]["largest_shortfall"] == 72000
    months = data["current_plan"]["monthly"]
    assert len(months) == 12 and all(m["income"] == 24000 for m in months)


def test_at13_before_and_after_use_the_same_horizon(demo_state):
    data = call(demo_state, "simulate_income_change", percent=-20, horizon_months=6)
    compared = data["compared_with_current"]
    assert compared["horizon_months"] == 6
    assert compared["horizon_days"] == data["current_plan"]["horizon_days"]
    assert data["replanning"]["horizon_months"] == 6


def test_at13_new_deficit_and_goal_shortfalls_are_disclosed(demo_state):
    changes = call(demo_state, "simulate_income_change", percent=-20)["compared_with_current"][
        "changes"]
    text = " ".join(changes)
    assert "FEASIBLE to PLAN_INFEASIBLE" in text
    assert "New cash deficit" in text and "72,000 THB" in text
    assert "Vacation now misses its deadline" in text


def test_at13_explanation_numbers_match_the_calculation(demo_state):
    question = "What if my income drops 20%?"
    reply = DeterministicAgent().reply(AgentContext(demo_state), question)
    assert unverified_numbers(reply.text, question, reply.trace) == []
    assert "same 12-month horizon" in reply.text


def test_at13_one_off_income_is_not_scaled(demo_state):
    bonus = IncomeSource(id="bonus", name="Bonus", amount=thb(5000),
                         frequency=Frequency.ONE_TIME, on_date=date(2026, 12, 20))
    state = demo_state.model_copy(update={"incomes": (*demo_state.incomes, bonus)})
    data = call(state, "simulate_income_change", percent=-20)
    december = next(m for m in data["current_plan"]["monthly"] if m["month"] == "2026-12")
    assert december["income"] == 24000 + 5000


def test_at13_no_change_is_reported_as_no_change(demo_state):
    data = call(demo_state, "simulate_income_change", percent=0)
    assert data["compared_with_current"]["changes"] == [
        "No change in status, shortfall, or goal timing."]


# --- AT14: goal deadline in two months ----------------------------------------------


@pytest.fixture
def near_deadline(demo_state):
    goals = tuple(g.model_copy(update={"deadline": date(2026, 12, 31)}) if g.id == "laptop"
                  else g for g in demo_state.goals)
    return demo_state.model_copy(update={"goals": goals})


def test_at14_infeasible_target_is_detected_with_its_shortfall(near_deadline):
    # At most 11,000 a month can be freed (30,000 - 18,000 essentials - 1,000 leisure floor),
    # so no more than 22,000 of the 30,000 can be saved by 31 December.
    assert max_saving_by(near_deadline, date(2026, 12, 31)) == thb(22000)
    for plan in generate_plans(near_deadline).plans:
        laptop = plan.goals[0]
        assert laptop.on_track is False
        assert laptop.shortfall_at_deadline >= thb(8000)


def test_at14_deadline_is_never_silently_extended(near_deadline):
    for plan in generate_plans(near_deadline).plans:
        assert plan.goals[0].deadline == date(2026, 12, 31)


def test_at14_explanation_shows_the_risk_and_why(near_deadline):
    data = call(near_deadline, "optimize_financial_plan")
    for plan in data["plans"]:
        laptop = plan["goals"][0]
        assert laptop["on_track"] is False and laptop["shortfall_at_deadline"] >= 8000
        assert "not reachable on time" in laptop["why_late"]
        assert "at most 22,000.00 THB" in laptop["why_late"]
        assert "The deadline itself is not changed." in laptop["why_late"]


def test_at14_reachable_but_late_goal_says_others_would_have_to_wait(demo_state):
    cut = demo_state.model_copy(update={"incomes": (
        demo_state.incomes[0].model_copy(update={"amount": thb(24000)}),)})
    data = call(cut, "optimize_financial_plan")
    balanced = next(p for p in data["plans"] if p["strategy"] == "Balanced")
    vacation = next(g for g in balanced["goals"] if g["name"] == "Vacation")
    assert "reachable on time only if other goals or the emergency fund wait" in (
        vacation["why_late"])


# --- AT16: approval, execution, duplicate prevention --------------------------------


@pytest.fixture
def sandbox(demo_state):
    service = SandboxService(Store(), FixedClock(datetime(2026, 11, 1, tzinfo=UTC)))
    service.reset(demo_state)
    return service


def test_at16_unapproved_action_is_not_applied(sandbox):
    plan = generate_plans(sandbox.state).plans[0]
    plan_id = sandbox.propose(plan, AGENT).data["plan_id"]
    before = sandbox.state
    result = sandbox.execute(None, AGENT)
    assert not result.ok and result.code == "NO_APPROVAL"
    assert sandbox.state == before
    assert sandbox.store.get_plan(plan_id)["status"] == "PROPOSED"


def test_at16_approved_action_runs_once_and_everything_is_audited(sandbox):
    plan = generate_plans(sandbox.state).plans[0]
    plan_id = sandbox.propose(plan, AGENT).data["plan_id"]
    approval_id = sandbox.decide(plan_id, True).data["approval_id"]

    first = sandbox.execute(approval_id, AGENT)
    assert first.ok and first.code == "EXECUTED"  # actual status is reported
    after = sandbox.state
    second = sandbox.execute(approval_id, AGENT)
    assert not second.ok and second.code == "ALREADY_EXECUTED"
    assert sandbox.state == after
    assert len([r for r in sandbox.store.list_transactions()
                if r["kind"] == "PLAN_ACTIVATION"]) == 1

    actions = [e.action for e in sandbox.store.list_audit()]
    assert actions[-3:] == ["PLAN_APPROVED", "PLAN_EXECUTED", "DUPLICATE_EXECUTION_BLOCKED"]
    assert sandbox.store.verify_audit_chain()


def test_at16_rejection_keeps_the_previous_plan_state(sandbox):
    before = sandbox.state
    plan = generate_plans(sandbox.state).plans[1]
    plan_id = sandbox.propose(plan, AGENT).data["plan_id"]
    approval_id = sandbox.decide(plan_id, False).data["approval_id"]
    assert sandbox.execute(approval_id, AGENT).code == "NOT_APPROVED"
    assert sandbox.state == before
    assert sandbox.store.get_plan(plan_id)["status"] == "REJECTED"
