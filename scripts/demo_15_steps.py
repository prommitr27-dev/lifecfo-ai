"""The 15-step competition demo, end to end, with a check on every step.

Runs the brief's "first working demonstration" on synthetic data with no LLM,
no network, and a fixed clock, then writes the evidence:

    docs/competition/evidence/demo_15_steps.md     step-by-step report
    docs/competition/evidence/demo_15_steps.json   audit log, transactions, rewards

    uv run python scripts/demo_15_steps.py
"""

import json
import sys
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path

from lifecfo.agents import AgentContext, DeterministicAgent, Tier, default_registry
from lifecfo.agents.agent import unverified_numbers
from lifecfo.agents.views import tradeoff_facts
from lifecfo.cashflow import FeasibilityStatus, check_feasibility
from lifecfo.cashflow.position import ShortfallKind, assess_position
from lifecfo.database import Store
from lifecfo.domain import FixedClock, thb
from lifecfo.domain.loader import load_state
from lifecfo.domain.models import Envelope, EnvelopeKind, Goal, SavingsTransfer
from lifecfo.domain.money import format_thb
from lifecfo.optimization import PlanningStatus, generate_plans, validate_plan
from lifecfo.optimization.optimizer import horizon_days
from lifecfo.services import SandboxService
from lifecfo.services.sandbox import AGENT

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "data" / "synthetic" / "profile_demo.yaml"
EVIDENCE = ROOT / "docs" / "competition" / "evidence"


@dataclass
class Step:
    number: int
    title: str
    lines: list[str] = field(default_factory=list)
    checks: list[tuple[str, bool]] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(ok for _, ok in self.checks)

    def note(self, text: str) -> None:
        self.lines.append(text)

    def check(self, name: str, ok: bool) -> None:
        self.checks.append((name, bool(ok)))


def run() -> tuple[list[Step], dict]:
    clock = FixedClock(datetime(2026, 11, 1, 2, 0, tzinfo=UTC))
    sandbox = SandboxService(Store(), clock)
    agent = DeterministicAgent(max_tier=Tier.EXECUTE)
    steps: list[Step] = []

    def ask(step: Step, text: str):
        reply = agent.reply(AgentContext(sandbox.state, sandbox), text)
        step.note(f"User asks: \"{text}\" -> tools "
                  + (", ".join(r.name for r in reply.trace) or "none"))
        step.check(f"Every figure in the answer to \"{text}\" comes from a tool result",
                   not unverified_numbers(reply.text, text, reply.trace))
        return reply

    # 1. Synthetic profile, without goals yet.
    step = Step(1, "Create a synthetic financial profile")
    full = load_state(PROFILE)
    profile = full.model_copy(update={
        "goals": (), "transfers": (t for t in full.transfers if t.envelope_id == "emergency"),
        "envelopes": tuple(e for e in full.envelopes if e.kind is not EnvelopeKind.GOAL)})
    profile = profile.model_copy(update={"transfers": tuple(profile.transfers)})
    sandbox.reset(profile, actor="USER")
    state = sandbox.state
    step.note(f"Salary {format_thb(30000 * 100)} on day 1; essentials "
              f"{format_thb(state.monthly_essentials)}; leisure 3,000 (minimum 2,000, "
              f"reduction allowed); emergency reserve {format_thb(state.emergency.balance)}; "
              "reserve target 3 months; buffer 1 month. Synthetic data only.")
    step.check("Profile loads and validates", state.monthly_essentials == thb(18000))
    steps.append(step)

    # 2. Goals.
    step = Step(2, "Add multiple goals")
    goals = (Goal(id="laptop", name="New laptop", target=thb(30000), priority=1,
                  deadline=date(2027, 8, 31)),
             Goal(id="travel", name="Vacation", target=thb(15000), priority=2,
                  deadline=date(2027, 6, 30), flexible=True))
    envelopes = (*state.envelopes,
                 Envelope(id="env-laptop", kind=EnvelopeKind.GOAL, goal_id="laptop", balance=0),
                 Envelope(id="env-travel", kind=EnvelopeKind.GOAL, goal_id="travel", balance=0))
    transfers = (*state.transfers,
                 SavingsTransfer(id="t-laptop", envelope_id="env-laptop", amount=thb(3000),
                                 day_of_month=2),
                 SavingsTransfer(id="t-travel", envelope_id="env-travel", amount=thb(2000),
                                 day_of_month=2))
    sandbox.reset(state.model_copy(update={"goals": goals, "envelopes": envelopes,
                                           "transfers": transfers}), actor="USER")
    step.note("New laptop 30,000 by 2027-08-31 (priority 1); Vacation 15,000 by 2027-06-30 "
              "(priority 2, flexible). The user's own savings plan: 4,000 + 3,000 + 2,000 a "
              "month.")
    step.check("Two goals with their own envelopes", len(sandbox.state.goals) == 2)
    steps.append(step)

    # 3. Initial plan.
    step = Step(3, "Generate an initial financial plan")
    reply = ask(step, "Compare the three plans")
    result = generate_plans(sandbox.state)
    step.check("Three plans generated and each passes the validator",
               result.status is PlanningStatus.OK and len(result.plans) == 3
               and all(validate_plan(sandbox.state, p).ok for p in result.plans))
    step.check("The user's own position is shown before the proposals",
               reply.text.index("Your position") < reply.text.index("I generated"))
    ask(step, "Propose the Balanced plan")
    plan_id = sandbox.store.list_plans("PROPOSED")[0]["id"]
    step.check("User approves in the app", sandbox.decide(plan_id, True).ok)
    executed = ask(step, "Execute the approved plan")
    step.check("Executed in the sandbox", executed.trace[0].data.get("code") == "EXECUTED")
    initial = next(p for p in result.plans if p.strategy == "BALANCED")
    step.note("Balanced plan active: reserve target reached "
              f"{initial.reserve.reached_month}; "
              + "; ".join(f"{g.name} {g.completion_month}" for g in initial.goals))
    steps.append(step)

    # 4. Income cut, first as a what-if, then confirmed.
    step = Step(4, "Simulate a 20% income reduction")
    before = sandbox.state
    what_if = ask(step, "What if my income drops 20%?")
    step.check("The simulation leaves stored data untouched", sandbox.state == before)
    compared = what_if.trace[0].data["compared_with_current"]
    step.check("Before and after use the same 12-month horizon",
               compared["horizon_months"] == 12)
    for change in compared["changes"][:3]:
        step.note(f"What-if: {change}")
    confirmed = sandbox.confirm_income_change(-20)
    step.note(f"User confirms the cut in the app: {confirmed.message}")
    step.check("Confirmed income is 24,000 a month",
               confirmed.data.get("monthly_income") == thb(24000))
    steps.append(step)

    # 5. The active plan no longer works.
    step = Step(5, "Identify that the existing plan is infeasible")
    days = horizon_days(sandbox.state.as_of, 12)
    report = check_feasibility(sandbox.state, days)
    step.note(f"Active plan status: {report.status.value}; cash first runs short on "
              f"{report.first_shortfall_on}, by up to {format_thb(report.max_shortfall)}.")
    step.check("The active plan is reported as infeasible",
               report.status is FeasibilityStatus.PLAN_INFEASIBLE)
    ask(step, "Can I afford my current plan?")
    steps.append(step)

    # 6. Alternatives.
    step = Step(6, "Generate alternative financial plans")
    result = generate_plans(sandbox.state)
    step.check("Three alternatives, each validated", result.status is PlanningStatus.OK and all(
        validate_plan(sandbox.state, p).ok for p in result.plans))
    for plan in result.plans:
        step.note(f"{plan.label}: reserve {plan.reserve.reached_month or 'not within 12 months'};"
                  " " + "; ".join(f"{g.name} {g.completion_month or 'not within 12 months'}"
                                  + (" (late)" if g.on_track is False else "")
                                  for g in plan.goals))
    steps.append(step)

    # 7. Trade-offs.
    step = Step(7, "Explain the trade-offs")
    facts = tradeoff_facts(result)
    for fact in facts[:4]:
        step.note(fact)
    step.check("Trade-offs are derived from the plans", bool(facts))
    reply = ask(step, "Compare the three plans")
    step.check("Late goals carry a reason built from the plan", "Why" in reply.text)
    steps.append(step)

    # 8. Approval.
    step = Step(8, "Let the user approve one")
    attempt = ask(step, "Approve the Safety First plan")
    step.check("The assistant cannot approve", attempt.trace == ())
    ask(step, "Propose the Safety First plan")
    plan_id = sandbox.store.list_plans("PROPOSED")[0]["id"]
    decided = sandbox.decide(plan_id, True)
    step.check("Approved by the user in the app", decided.ok
               and sandbox.store.list_audit()[-1].actor == "USER")
    steps.append(step)

    # 9. Execution.
    step = Step(9, "Execute changes in the sandbox")
    first = ask(step, "Execute the approved plan").trace[0].data
    second = sandbox.execute(decided.data["approval_id"], AGENT)
    step.check("Executed once", first.get("code") == "EXECUTED")
    step.check("A repeated execution changes nothing", second.code == "ALREADY_EXECUTED")
    steps.append(step)

    # Daily check-ins before the shock (for steps 13 and 14).
    for _ in range(3):
        sandbox.rewards.record_review()
        clock.advance(days=1)

    # 10. Emergency expense.
    step = Step(10, "Simulate a 10,000 THB emergency expense")
    what_if = ask(step, "What if I get a 10,000 THB repair bill?").trace[0].data
    step.note(f"What-if: {format_thb(what_if['not_covered_by_unallocated_cash'] * 100)} not "
              f"covered by unallocated cash; reserve withdrawal "
              f"{format_thb(what_if['reserve_withdrawal_needed'] * 100)}.")
    shock = sandbox.confirm_expense("Car repair", thb(10000), date(2026, 11, 12))
    step.note(f"User confirms it in the app: {shock.message}")
    step.check("Confirmed by the user and recorded", shock.ok)
    steps.append(step)

    # 11. Recovery plan.
    step = Step(11, "Generate a recovery plan")
    position = assess_position(sandbox.state, horizon_days(sandbox.state.as_of, 12))
    essentials_gap = next((s.amount for s in position.shortfalls
                           if s.kind is ShortfallKind.RESERVE_WITHDRAWAL_NEEDED), 0)
    # Enough to pay essentials and keep flexible spending at the user's own minimum.
    needed = min(position.cash.eligible_reserve,
                 max(essentials_gap, position.adjusted_deficit))
    step.note(f"Essentials alone need {format_thb(essentials_gap)} from the reserve; keeping "
              f"flexible spending at the user's minimum needs "
              f"{format_thb(position.adjusted_deficit)}.")
    if needed:
        withdrawal = sandbox.withdraw_reserve(needed)
        step.note(f"User withdraws from the reserve: {withdrawal.message}")
    recovery = generate_plans(sandbox.state)
    step.check("A validated recovery plan exists", recovery.status is PlanningStatus.OK)
    ask(step, "Propose the Safety First plan")
    plan_id = sandbox.store.list_plans("PROPOSED")[0]["id"]
    step.check("User approves the recovery plan", sandbox.decide(plan_id, True).ok)
    step.check("Executed", sandbox.execute(None, AGENT).ok)
    steps.append(step)

    # 12. Goal projections.
    step = Step(12, "Update goal projections")
    before_shock = next(p for p in result.plans if p.strategy == "SAFETY_FIRST")
    after_shock = next(p for p in recovery.plans if p.strategy == "SAFETY_FIRST")
    step.note("Safety First, the plan the user approved, before and after the confirmed "
              "expense (12-month horizon):")
    for old, new in zip(before_shock.goals, after_shock.goals, strict=True):
        step.note(f"{new.name}: saved by month 12 {format_thb(old.projected_saved)} -> "
                  f"{format_thb(new.projected_saved)}; completes "
                  f"{old.completion_month or 'after month 12'} -> "
                  f"{new.completion_month or 'after month 12'}"
                  + (f"; {format_thb(new.shortfall_at_deadline)} short at its deadline"
                     if new.on_track is False else ""))
    step.note(f"Emergency reserve by month 12: {format_thb(before_shock.reserve.projected_saved)}"
              f" -> {format_thb(after_shock.reserve.projected_saved)} of "
              f"{format_thb(after_shock.reserve.target)}")
    step.check("Projections recalculated from the new state",
               after_shock.state_hash != before_shock.state_hash
               and after_shock.reserve.projected_saved < before_shock.reserve.projected_saved)
    steps.append(step)

    # 13. Recovery mission.
    step = Step(13, "Trigger an appropriate recovery mission")
    events = {e["type"]: e for e in sandbox.store.list_reward_events()}
    step.check("The shock switched missions to recovery and protected the streak",
               "STREAK_PROTECTION_ACTIVATED" in events)
    step.check("Approving the recovery plan completed the recovery mission",
               "RECOVERY_MISSION_COMPLETED" in events)
    step.note("Missions after the shock: review recovery options; approve a feasible recovery "
              "plan. No saving was expected during the emergency.")
    steps.append(step)

    # 14. Streak.
    step = Step(14, "Maintain or protect the financial streak")
    status = default_registry().call(AgentContext(sandbox.state, sandbox), "get_reward_status",
                                     {}, Tier.READ).data
    daily = status["streaks"]["DAILY"]
    step.note(f"Daily streak {daily['count']} (status {daily['status']}, best {daily['best']}); "
              f"{status['xp']} XP, level {status['level']}; badges: "
              + ", ".join(status["badges"]))
    step.check("The streak survived the emergency and grew only by earned days",
               daily["count"] == 4 and daily["status"] != "BROKEN")
    steps.append(step)

    # 15. Audit log.
    step = Step(15, "Display the audit log")
    entries = sandbox.store.list_audit()
    actions = [e.action for e in entries]
    for entry in entries:
        step.note(f"#{entry.seq} {entry.actor}: {entry.action}"
                  + (f" ({entry.payload['code']})" if "code" in entry.payload else ""))
    step.check("Hash chain intact", sandbox.store.verify_audit_chain())
    step.check("Every decision and execution is logged", all(a in actions for a in (
        "PLAN_APPROVED", "PLAN_EXECUTED", "INCOME_CHANGE_CONFIRMED", "SHOCK_CONFIRMED",
        "DUPLICATE_EXECUTION_BLOCKED")))
    steps.append(step)

    log = {
        "audit_chain_intact": sandbox.store.verify_audit_chain(),
        "audit_log": [e.__dict__ for e in entries],
        "transactions": [dict(r) for r in sandbox.store.list_transactions()],
        "reward_events": sandbox.store.list_reward_events(),
    }
    return steps, log


def render(steps: list[Step]) -> str:
    passed = sum(s.passed for s in steps)
    lines = ["# 15-Step Demo: Execution Evidence", "",
             "Generated by `scripts/demo_15_steps.py` on synthetic data, with no LLM, no "
             "network, and a fixed clock. Re-running it reproduces every line.", "",
             f"**{passed} of {len(steps)} steps pass.**", ""]
    for step in steps:
        lines += [f"## Step {step.number}: {step.title}", "",
                  f"**{'PASS' if step.passed else 'FAIL'}**", ""]
        lines += [f"- {line}" for line in step.lines]
        lines += ["", "| Check | Result |", "|---|---|"]
        lines += [f"| {name} | {'PASS' if ok else 'FAIL'} |" for name, ok in step.checks]
        lines.append("")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    steps, log = run()
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    (EVIDENCE / "demo_15_steps.md").write_text(render(steps), encoding="utf-8", newline="\n")
    (EVIDENCE / "demo_15_steps.json").write_text(json.dumps(log, indent=2, default=str) + "\n",
                                                 encoding="utf-8", newline="\n")
    sys.stdout.reconfigure(encoding="utf-8")
    for step in steps:
        print(f"{'PASS' if step.passed else 'FAIL'}  {step.number:>2}. {step.title}")
        for name, ok in step.checks:
            if not ok:
                print(f"        failed: {name}")
    raise SystemExit(0 if all(s.passed for s in steps) else 1)
