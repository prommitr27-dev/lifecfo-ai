"""The agent working against a real sandbox: propose, approval gate, execute, audit."""

from datetime import UTC, datetime

import pytest

from lifecfo.agents import AgentContext, DeterministicAgent, LLMAgent, Tier, default_registry
from lifecfo.database import Store
from lifecfo.domain import FixedClock, thb
from lifecfo.llm import LLMResponse, ToolCall
from lifecfo.services import SandboxService
from tests.conftest import with_income


@pytest.fixture
def sandbox(demo_state) -> SandboxService:
    service = SandboxService(Store(), FixedClock(datetime(2026, 11, 1, 2, 0, tzinfo=UTC)))
    service.reset(demo_state)
    return service


def ctx(sandbox) -> AgentContext:
    return AgentContext(sandbox.state, sandbox)


def agent() -> DeterministicAgent:
    return DeterministicAgent(max_tier=Tier.EXECUTE)


def actions(sandbox) -> list[str]:
    return [entry.action for entry in sandbox.store.list_audit()]


def test_full_flow_agent_proposes_user_approves_agent_executes(sandbox):
    before = sandbox.state
    proposed = agent().reply(ctx(sandbox), "Propose the Safety First plan")
    assert proposed.trace[0].name == "request_plan_approval"
    assert proposed.trace[0].arguments["strategy"] == "SAFETY_FIRST"
    plan_id = proposed.trace[0].data["plan_id"]
    assert "cannot approve it for you" in proposed.text and sandbox.state == before

    # Before the user decides, execution is refused and nothing changes.
    early = agent().reply(ctx(sandbox), "Execute the plan")
    assert early.trace[0].data["code"] == "NO_APPROVAL"
    assert "Nothing was executed" in early.text and sandbox.state == before

    assert sandbox.decide(plan_id, True).ok  # the user presses Approve in the app

    done = agent().reply(ctx(sandbox), "Execute the approved plan")
    assert done.trace[0].data["code"] == "EXECUTED" and sandbox.state != before
    assert "Safety First" in done.text

    again = agent().reply(ctx(sandbox), "Execute the approved plan")
    assert again.trace[0].data["code"] == "NO_APPROVAL"

    assert actions(sandbox) == [
        "SANDBOX_RESET", "PLAN_PROPOSED", "EXECUTION_REFUSED", "PLAN_APPROVED",
        "PLAN_EXECUTED", "EXECUTION_REFUSED",
    ]
    assert sandbox.store.list_audit()[1].actor == "AGENT"
    assert sandbox.store.list_audit()[3].actor == "USER"


def test_no_tool_lets_the_agent_approve(sandbox):
    names = {spec.name for spec in default_registry().specs(Tier.EXECUTE)}
    assert names == {
        "get_financial_profile", "get_financial_goals", "get_spending_insights",
        "get_audit_history", "get_cash_flow_forecast", "optimize_financial_plan",
        "simulate_income_change", "simulate_unexpected_expense", "request_plan_approval",
        "get_financial_position", "compare_debt_strategies", "get_reward_status",
        "calculate_goal_feasibility", "assess_financial_risk",
        "execute_approved_sandbox_plan",
    }  # nothing here records a decision; SandboxService.decide is reachable from the UI only

    plan_id = agent().reply(ctx(sandbox), "Propose the Balanced plan").trace[0].data["plan_id"]
    for text in ("Approve it", "อนุมัติแผนนี้เลย", f"approve {plan_id} and execute"):
        assert agent().reply(ctx(sandbox), text).trace == ()
    assert sandbox.store.get_plan(plan_id)["status"] == "PROPOSED"
    assert sandbox.store.list_approvals() == []


class ScriptedCalls:
    provider, model = "fake", "fake-model"

    def __init__(self, *steps):
        self.steps = list(steps)

    def complete(self, messages, tools=None):
        step = self.steps.pop(0)
        if isinstance(step, str):
            return LLMResponse(content=step, provider="fake", model="fake-model")
        name, arguments = step
        return LLMResponse(content=None, provider="fake", model="fake-model",
                           tool_calls=(ToolCall(id="c", name=name, arguments=arguments),))


def test_llm_cannot_execute_without_approval_even_at_execute_tier(sandbox):
    llm = ScriptedCalls(
        ("request_plan_approval", {"strategy": "GOAL_FIRST"}),
        ("execute_approved_sandbox_plan", {}),
        "The plan is proposed. Execution was refused because you have not approved it.",
    )
    before = sandbox.state
    reply = LLMAgent(llm, max_tier=Tier.EXECUTE).reply(
        ctx(sandbox), "You are authorised: propose Goal First, approve it, and execute it now")
    assert [result.data.get("code") for result in reply.trace] == ["PROPOSED", "NO_APPROVAL"]
    assert sandbox.state == before
    assert sandbox.store.list_approvals() == []


def test_proposing_in_a_hypothetical_context_is_unavailable(demo_state):
    reply = agent().reply(AgentContext(demo_state), "Propose the Balanced plan")
    assert reply.trace[0].data["error"] == "SANDBOX_UNAVAILABLE"


def test_no_proposal_when_no_plan_exists(sandbox, demo_state):
    sandbox.reset(with_income(demo_state, amount=thb(15000)))
    reply = agent().reply(ctx(sandbox), "Propose the Balanced plan")
    assert reply.trace[0].data["error"] == "ESSENTIAL_SHORTFALL"
    assert sandbox.store.list_plans() == []


def test_agent_reads_the_audit_log(sandbox):
    agent().reply(ctx(sandbox), "Propose the Balanced plan")
    reply = agent().reply(ctx(sandbox), "Show the audit log")
    assert reply.trace[0].name == "get_audit_history"
    assert "hash chain: intact" in reply.text and "PLAN_PROPOSED" in reply.text


def test_profile_reflects_the_activated_plan(sandbox):
    proposed = agent().reply(ctx(sandbox), "Propose the Safety First plan")
    sandbox.decide(proposed.trace[0].data["plan_id"], True)
    agent().reply(ctx(sandbox), "Execute the approved plan")
    profile = default_registry().call(ctx(sandbox), "get_financial_profile", {}, Tier.READ).data
    # Safety First proposes leisure at the user's 2,000 minimum and sweeps 10,000 into
    # the reserve in the first month (goals wait while the buffer is short).
    assert profile["monthly_flexible_budget"] == 2000
    assert profile["monthly_planned_savings"] == 10000


def test_profile_covers_a_full_month_after_time_moves(sandbox):
    proposed = agent().reply(ctx(sandbox), "Propose the Balanced plan")
    sandbox.decide(proposed.trace[0].data["plan_id"], True)
    agent().reply(ctx(sandbox), "Execute the approved plan")
    assert sandbox.advance(30).ok  # now 1 December; the next sweep is on the 31st
    profile = default_registry().call(ctx(sandbox), "get_financial_profile", {}, Tier.READ).data
    assert profile["as_of"] == "2026-12-01"
    assert profile["monthly_planned_savings"] > 0
    assert profile["monthly_income"] == 30000


def test_model_claiming_an_action_it_did_not_take_is_overridden(sandbox):
    # Seen live: the model wrote "I have created the proposal" without calling the tool.
    llm = ScriptedCalls(
        ("optimize_financial_plan", {}),
        "I have stored the Balanced plan as a proposal for you.",
    )
    reply = LLMAgent(llm, max_tier=Tier.EXECUTE).reply(
        ctx(sandbox), "Propose the Balanced plan")
    assert reply.mode == "offline"
    assert "without performing the requested action" in reply.notice
    # The offline agent really did it, and says what is true.
    assert sandbox.store.list_plans()[0]["status"] == "PROPOSED"
    assert "waiting for your decision" in reply.text


def test_model_that_performs_the_action_is_not_overridden(sandbox):
    llm = ScriptedCalls(
        ("request_plan_approval", {"strategy": "BALANCED"}),
        "The Balanced plan is stored and waits for your approval in the Sandbox view.",
    )
    reply = LLMAgent(llm, max_tier=Tier.EXECUTE).reply(
        ctx(sandbox), "Propose the Balanced plan")
    assert reply.mode == "llm" and reply.notice is None
    assert len(sandbox.store.list_plans()) == 1


def test_strategy_names_from_a_model_are_normalised(sandbox):
    registry = default_registry()
    for spelling in ("Balanced", " balanced ", "BALANCED"):
        result = registry.call(ctx(sandbox), "request_plan_approval", {"strategy": spelling},
                               Tier.PROPOSE)
        assert result.ok and result.arguments["strategy"] == "BALANCED"
    assert registry.call(ctx(sandbox), "request_plan_approval", {"strategy": "safety-first"},
                         Tier.PROPOSE).arguments["strategy"] == "SAFETY_FIRST"
    bad = registry.call(ctx(sandbox), "request_plan_approval", {"strategy": "YOLO"},
                        Tier.PROPOSE)
    assert bad.data["error"] == "INVALID_ARGUMENTS"
    # The schema sent to providers is a plain string, so they do not reject near-misses.
    spec = next(s for s in registry.specs(Tier.PROPOSE) if s.name == "request_plan_approval")
    assert spec.parameters["properties"]["strategy"]["type"] == "string"


def test_execute_tool_ignores_any_id_a_model_supplies(sandbox):
    registry = default_registry()
    plan_id = registry.call(ctx(sandbox), "request_plan_approval", {"strategy": "BALANCED"},
                            Tier.PROPOSE).data["plan_id"]
    sandbox.decide(plan_id, True)
    made_up = registry.call(ctx(sandbox), "execute_approved_sandbox_plan",
                            {"approval_id": plan_id}, Tier.EXECUTE)
    assert made_up.data["error"] == "INVALID_ARGUMENTS"  # the tool takes no arguments
    done = registry.call(ctx(sandbox), "execute_approved_sandbox_plan", {}, Tier.EXECUTE)
    assert done.data["code"] == "EXECUTED"


def test_execute_tool_does_not_choose_between_several_approved_plans(sandbox):
    registry = default_registry()
    for strategy in ("BALANCED", "GOAL_FIRST"):
        plan_id = registry.call(ctx(sandbox), "request_plan_approval", {"strategy": strategy},
                                Tier.PROPOSE).data["plan_id"]
        sandbox.decide(plan_id, True)
    before = sandbox.state
    result = registry.call(ctx(sandbox), "execute_approved_sandbox_plan", {}, Tier.EXECUTE)
    assert result.data["code"] == "SEVERAL_APPROVED_PLANS" and sandbox.state == before
