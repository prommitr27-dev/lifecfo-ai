"""Run LifeCFO and three baselines on every scenario and measure the outcome.

Methods (all see the same post-shock situation over the same 12 months):

- FIXED_BUDGET: the user's own static savings plan continues unchanged.
- PRIORITY_WATERFALL: each month-end, the recurring monthly surplus goes to the
  reserve until its target, then to goals by priority. Recomputed after the
  shock, but with no daily cash check, no buffer, and no flexible changes.
- NO_REPLANNING: LifeCFO's Balanced plan made before the shock, kept as it is.
- LIFECFO: LifeCFO's Balanced plan made after the shock (validated). When the
  position report says essentials need the reserve, the user withdraws the
  amount LifeCFO shows and LifeCFO plans again (a recovery plan). When no plan
  exists even then, LifeCFO says so; the outcome is then measured with no
  savings and flexible spending at the user's minimum.

A payment counts as missed only when unallocated cash and the whole emergency
reserve together cannot cover it, so every method may fall back on the reserve.
Days with negative unallocated cash are reported separately: on those days the
user must raid savings the plan had not set aside for this.

Each method's schedule is applied to the post-shock profile and run through
the same daily forecast, so every number comes from one engine.
"""

from dataclasses import dataclass
from datetime import date
from statistics import mean

from lifecfo.cashflow.forecast import EventKind, forecast_cash_flow
from lifecfo.cashflow.position import ShortfallKind, assess_position
from lifecfo.domain.models import (
    EnvelopeKind,
    ExpenseCategory,
    FinancialState,
    Frequency,
    SavingsTransfer,
)
from lifecfo.domain.money import SATANG_PER_THB
from lifecfo.evaluation.scenarios import Scenario
from lifecfo.optimization import PlanningStatus, apply_plan, generate_plans
from lifecfo.optimization.optimizer import _periods, horizon_days
from lifecfo.optimization.strategies import load_strategies

METHODS = ("FIXED_BUDGET", "PRIORITY_WATERFALL", "NO_REPLANNING", "LIFECFO")
MONTHS = 12


@dataclass(frozen=True)
class ScenarioResult:
    seed: int
    shock: str
    method: str
    outcome: str  # PLAN, RECOVERY_PLAN or NO_PLAN_DISCLOSED (baselines always PLAN)
    shortfall_days: int
    max_shortfall: float  # THB
    missed_essential_payment: bool
    months_below_buffer: int
    reserve_end_percent: float
    goals_due: int
    goals_on_time: int


def _with_schedule(after: FinancialState, scheduled: FinancialState) -> FinancialState:
    """The post-shock profile, following another state's savings and flexible schedule."""
    essentials = tuple(e for e in after.expenses if e.category is ExpenseCategory.ESSENTIAL)
    flexible = tuple(e for e in scheduled.expenses if e.category is ExpenseCategory.FLEXIBLE)
    return after.model_copy(update={
        "transfers": scheduled.transfers, "debt_payments": scheduled.debt_payments,
        "expenses": (*essentials, *flexible)})


def _waterfall(after: FinancialState) -> FinancialState:
    surplus = (sum(i.amount for i in after.incomes if i.frequency is Frequency.MONTHLY)
               - after.monthly_essentials - after.monthly_debt_minimums
               - sum(e.amount for e in after.expenses if e.category is ExpenseCategory.FLEXIBLE
                     and e.frequency is Frequency.MONTHLY))
    needs = []
    if after.emergency:
        needs.append(("emergency", max(0, after.emergency_target - after.emergency.balance)))
    for goal in sorted(after.goals, key=lambda g: g.priority):
        envelope = next(e for e in after.envelopes if e.goal_id == goal.id)
        needs.append((envelope.id, max(0, goal.target - envelope.balance)))
    transfers = []
    for _, month_end in _periods(after.as_of, MONTHS):
        left = max(0, surplus)
        for index, (envelope_id, need) in enumerate(needs):
            amount = min(left, need)
            if amount > 0:
                transfers.append(SavingsTransfer(
                    id=f"wf:{envelope_id}:{month_end}", envelope_id=envelope_id, amount=amount,
                    frequency=Frequency.ONE_TIME, on_date=month_end))
                needs[index] = (envelope_id, need - amount)
                left -= amount
    return after.model_copy(update={"transfers": tuple(transfers), "debt_payments": ()})


def _measure(scenario: Scenario, method: str, state: FinancialState,
             outcome: str = "PLAN") -> ScenarioResult:
    days = horizon_days(state.as_of, MONTHS)
    forecast = forecast_cash_flow(state, days)

    balances = {e.id: e.balance for e in state.envelopes}
    by_day: dict[date, dict[str, int]] = {}
    for day in forecast.days:
        for event in day.events:
            if event.envelope_id:
                balances[event.envelope_id] += event.amount
        by_day[day.on] = dict(balances)
    end = forecast.days[-1].on
    missed = any(day.unallocated + by_day[day.on].get("emergency", 0) < 0
                 for day in forecast.days if any(
                     e.kind in (EventKind.ESSENTIAL_EXPENSE, EventKind.DEBT_MINIMUM)
                     for e in day.events))

    below = 0
    buffer = state.buffer_target
    if buffer is not None:
        for _, month_end in _periods(state.as_of, MONTHS):
            unallocated = next(d.unallocated for d in forecast.days if d.on == month_end)
            if unallocated + by_day[month_end].get("emergency", 0) < buffer:
                below += 1

    target = state.emergency_target
    reserve_end = by_day[end].get("emergency", 0)
    due = on_time = 0
    for goal in state.goals:
        if goal.deadline is None or goal.deadline > end:
            continue
        due += 1
        envelope = next(e.id for e in state.envelopes if e.goal_id == goal.id)
        check = max(goal.deadline, state.as_of)
        if by_day.get(check, by_day[end]).get(envelope, 0) >= goal.target:
            on_time += 1
    return ScenarioResult(
        seed=scenario.seed, shock=scenario.shock, method=method, outcome=outcome,
        shortfall_days=sum(1 for d in forecast.days if d.unallocated < 0),
        max_shortfall=forecast.max_shortfall / SATANG_PER_THB,
        missed_essential_payment=missed, months_below_buffer=below,
        reserve_end_percent=round(100 * reserve_end / target, 1) if target else 100.0,
        goals_due=due, goals_on_time=on_time,
    )


def _recovered(after: FinancialState) -> FinancialState | None:
    """The state after the reserve withdrawal LifeCFO's position report asks for, if any."""
    position = assess_position(after, horizon_days(after.as_of, MONTHS))
    essentials_gap = next((s.amount for s in position.shortfalls
                           if s.kind is ShortfallKind.RESERVE_WITHDRAWAL_NEEDED), 0)
    needed = min(position.cash.eligible_reserve,
                 max(essentials_gap, position.adjusted_deficit))
    if needed <= 0 or after.emergency is None:
        return None
    return after.model_copy(update={"envelopes": tuple(
        e.model_copy(update={"balance": e.balance - needed}) if e.kind is EnvelopeKind.EMERGENCY
        else e.model_copy(update={"balance": e.balance + needed})
        if e.kind is EnvelopeKind.UNALLOCATED else e for e in after.envelopes)})


def _at_floor(after: FinancialState) -> FinancialState:
    """No savings, flexible spending at the user's own minimum (dropped when it is 0)."""
    expenses = tuple(
        e.model_copy(update={"amount": e.floor}) if e.category is ExpenseCategory.FLEXIBLE else e
        for e in after.expenses
        if not (e.category is ExpenseCategory.FLEXIBLE and e.floor == 0))
    return after.model_copy(update={"transfers": (), "debt_payments": (), "expenses": expenses})


def _lifecfo(after: FinancialState, balanced: dict) -> tuple[FinancialState, str]:
    result = generate_plans(after, balanced, MONTHS)
    if result.status is PlanningStatus.OK:
        return apply_plan(after, result.plans[0]), "PLAN"
    recovered = _recovered(after)
    if recovered is not None:
        result = generate_plans(recovered, balanced, MONTHS)
        if result.status is PlanningStatus.OK:
            return apply_plan(recovered, result.plans[0]), "RECOVERY_PLAN"
        return _at_floor(recovered), "NO_PLAN_DISCLOSED"
    return _at_floor(after), "NO_PLAN_DISCLOSED"


def evaluate(scenarios: list[Scenario]) -> list[ScenarioResult]:
    balanced = {"BALANCED": load_strategies()["BALANCED"]}
    results = []
    for scenario in scenarios:
        after = scenario.after
        results.append(_measure(scenario, "FIXED_BUDGET", after))
        results.append(_measure(scenario, "PRIORITY_WATERFALL", _waterfall(after)))
        # LifeCFO's own pre-shock answer, kept unchanged after the shock.
        before = _lifecfo(scenario.before, balanced)[0]
        results.append(_measure(scenario, "NO_REPLANNING", _with_schedule(after, before)))
        state, outcome = _lifecfo(after, balanced)
        results.append(_measure(scenario, "LIFECFO", state, outcome))
    return results


def summarize(results: list[ScenarioResult]) -> list[dict]:
    rows = []
    for method in METHODS:
        mine = [r for r in results if r.method == method]
        due = sum(r.goals_due for r in mine)
        rows.append({
            "method": method,
            "scenarios": len(mine),
            "plan": sum(1 for r in mine if r.outcome == "PLAN"),
            "recovery_plan": sum(1 for r in mine if r.outcome == "RECOVERY_PLAN"),
            "no_plan_disclosed": sum(1 for r in mine if r.outcome == "NO_PLAN_DISCLOSED"),
            "scenarios_with_negative_cash": sum(1 for r in mine if r.shortfall_days),
            "scenarios_with_a_missed_payment": sum(1 for r in mine if r.missed_essential_payment),
            "mean_max_shortfall_thb": round(mean(r.max_shortfall for r in mine)),
            "mean_months_below_buffer": round(mean(r.months_below_buffer for r in mine), 2),
            "mean_reserve_end_percent": round(mean(r.reserve_end_percent for r in mine), 1),
            "goals_on_time": f"{sum(r.goals_on_time for r in mine)} of {due}",
        })
    return rows


__all__ = ["METHODS", "ScenarioResult", "evaluate", "summarize"]
