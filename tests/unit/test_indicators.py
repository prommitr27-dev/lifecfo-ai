from datetime import date

from lifecfo.agents import AgentContext, DeterministicAgent, Tier, default_registry
from lifecfo.agents.agent import unverified_numbers
from lifecfo.agents.indicators import goal_feasibility_data, risk_data
from lifecfo.domain import Goal, thb
from lifecfo.domain.models import Envelope, EnvelopeKind
from tests.conftest import with_income


def goal(data, name):
    return next(g for g in data["goals"] if g["goal"] == name)


def with_goals(state, **changes):
    """Copy of the demo state with goal fields replaced, e.g. laptop={"deadline": ...}."""
    return state.model_copy(update={"goals": tuple(
        g.model_copy(update=changes.get(g.id, {})) for g in state.goals)})


# --- calculate_goal_feasibility --------------------------------------------------------


def test_demo_goals_are_each_reachable_on_their_own(demo_state):
    data = goal_feasibility_data(demo_state)
    assert data["free_cash_per_month_under_original_budget"] == 9000
    laptop, vacation = goal(data, "New laptop"), goal(data, "Vacation")
    # 30,000 over the 10 month-ends from November to August; 15,000 over 8 to June.
    assert laptop["status"] == "REACHABLE_ON_ITS_OWN" and laptop["required_per_month"] == 3000
    assert vacation["required_per_month"] == 1875
    assert data["required_per_month_by_all_deadline_goals"] == 3000 + 1875


def test_a_fixed_deadline_that_cannot_be_met_is_a_deadline_risk(demo_state):
    near = with_goals(demo_state, laptop={"deadline": date(2026, 12, 31)})
    laptop = goal(goal_feasibility_data(near), "New laptop")
    # At most 10,000 a month (30,000 - 18,000 - 2,000 minimum leisure) for two months.
    assert laptop["status"] == "NOT_REACHABLE_ON_TIME"
    assert laptop["most_possible_by_deadline"] == 20000
    assert laptop["shortfall_at_best"] == 10000
    assert "deadline risk" in laptop["note"]
    assert laptop["deadline"] == "2026-12-31"  # unchanged


def test_a_flexible_goal_may_be_offered_a_later_date(demo_state):
    near = with_goals(demo_state, travel={"deadline": date(2026, 11, 30)})
    vacation = goal(goal_feasibility_data(near), "Vacation")
    assert vacation["status"] == "NOT_REACHABLE_ON_TIME"
    assert "a later date may be proposed" in vacation["note"]


def test_a_goal_that_needs_more_than_the_free_cash_is_flagged(demo_state):
    big = with_goals(demo_state, laptop={"target": thb(95000)})
    laptop = goal(goal_feasibility_data(big), "New laptop")
    assert laptop["required_per_month"] == 9500  # more than the 9,000 that is free
    assert laptop["status"] == "REACHABLE_ONLY_WITH_CUTS"


def test_no_deadline_is_invented(demo_state):
    state = demo_state.model_copy(update={
        "goals": (*demo_state.goals, Goal(id="bike", name="Bike", target=thb(20000),
                                          priority=3)),
        "envelopes": (*demo_state.envelopes, Envelope(id="env-bike", kind=EnvelopeKind.GOAL,
                                                      goal_id="bike", balance=0))})
    bike = goal(goal_feasibility_data(state), "Bike")
    assert bike["status"] == "NO_DEADLINE" and bike["deadline"] is None
    assert bike["months_if_all_free_cash_went_to_it"] == 3  # 20,000 / 9,000, rounded up
    assert "not a projected date" in bike["note"]


# --- assess_financial_risk -------------------------------------------------------------


def indicator(data, prefix):
    return next(i for i in data["indicators"] if i["name"].startswith(prefix))


def test_indicators_are_shown_without_ratings_until_thresholds_are_set(demo_state):
    data = risk_data(demo_state, 12)
    assert indicator(data, "Days until")["rating"] == "NO_SHORTFALL_IN_HORIZON"
    coverage = indicator(data, "Essential bill coverage")
    assert coverage["value"] == 2.0  # (6,000 reserve + 30,000 income) / 18,000 due
    assert coverage["rating"] == "NO_THRESHOLD_SET"
    assert indicator(data, "Emergency reserve")["value"] == 0.33  # 6,000 / 18,000
    assert indicator(data, "Income volatility")["rating"] == "NOT_MEASURABLE"


def test_thresholds_from_the_risk_lead_drive_the_ratings(demo_state):
    rules = {
        "days_until_shortfall": {"high_risk_below": 30, "medium_risk_below": 90},
        "emergency_reserve_months_of_essentials": {"adequate_at_or_above": 3, "low_below": 1},
        "essential_bill_coverage_ratio": {"at_risk_below": 1.5},
    }
    cut = with_income(demo_state, amount=thb(24000))
    data = risk_data(cut, 12, rules)
    days = indicator(data, "Days until")
    assert days["value"] == 4 and days["rating"] == "HIGH_RISK"  # short on 5 November
    assert indicator(data, "Emergency reserve")["rating"] == "LOW"
    assert indicator(data, "Essential bill coverage")["rating"] == "WITHIN_THRESHOLDS"


def test_goals_at_risk_are_counted(demo_state):
    near = with_goals(demo_state, laptop={"deadline": date(2026, 12, 31)})
    item = indicator(risk_data(near, 12), "Goals that cannot")
    assert item["value"] == 1 and item["goals"] == ["New laptop"]


# --- through the agent ------------------------------------------------------------------


def test_offline_agent_answers_with_verified_figures(demo_state):
    agent = DeterministicAgent()
    for question, tool in (("Can I reach my goals on time?", "calculate_goal_feasibility"),
                           ("เป้าหมายทันไหม", "calculate_goal_feasibility"),
                           ("How risky is my plan?", "assess_financial_risk")):
        reply = agent.reply(AgentContext(demo_state), question)
        assert reply.trace[0].name == tool
        assert unverified_numbers(reply.text, question, reply.trace) == []


def test_both_tools_are_compute_tier(demo_state):
    names = {s.name for s in default_registry().specs(Tier.COMPUTE)}
    assert {"calculate_goal_feasibility", "assess_financial_risk"} <= names
    assert not {"calculate_goal_feasibility", "assess_financial_risk"} & {
        s.name for s in default_registry().specs(Tier.READ)}
