"""Agent tools with permission tiers.

The agent, whether an LLM or the offline router, can reach the financial
engines only through this registry. Each tool has a typed input model, a
permission tier, and returns plain data with amounts in THB.

Tiers:
  0 READ      read the current state
  1 COMPUTE   run an engine on a copy of the state; nothing is stored
  2 PROPOSE   create a proposal for the user to approve (arrives with M3)
  3 EXECUTE   apply an approved plan in the sandbox (arrives with M3)

An agent is given a maximum tier. A call above that tier is refused by the
registry no matter what the model asked for.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from enum import IntEnum
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from lifecfo.cashflow import check_feasibility, forecast_cash_flow, monthly_summary
from lifecfo.cashflow.forecast import EventKind, build_events
from lifecfo.domain.models import EnvelopeKind, ExpenseCategory, FinancialState, Frequency
from lifecfo.domain.money import SATANG_PER_THB
from lifecfo.llm.base import ToolSpec
from lifecfo.optimization import Plan, PlanningResult, PlanningStatus, generate_plans


class Tier(IntEnum):
    READ = 0
    COMPUTE = 1
    PROPOSE = 2
    EXECUTE = 3


@dataclass(frozen=True)
class AgentContext:
    state: FinancialState


class NoInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ForecastInput(NoInput):
    horizon_days: Annotated[int, Field(ge=7, le=400)] = 92


class PlanInput(NoInput):
    horizon_months: Annotated[int, Field(ge=1, le=24)] = 12


class IncomeChangeInput(NoInput):
    percent: Annotated[float, Field(ge=-100, le=100, description=(
        "Change in every income source, in percent. Negative for a cut, e.g. -20."))]
    horizon_months: Annotated[int, Field(ge=1, le=24)] = 12


@dataclass(frozen=True)
class Tool:
    name: str
    tier: Tier
    description: str
    input_model: type[BaseModel]
    handler: Callable[[AgentContext, Any], dict[str, Any]]

    def spec(self) -> ToolSpec:
        schema = self.input_model.model_json_schema()
        schema.pop("title", None)
        return ToolSpec(name=self.name, description=self.description, parameters=schema)


@dataclass(frozen=True)
class ToolResult:
    name: str
    tier: Tier | None
    arguments: dict[str, Any]
    ok: bool
    data: dict[str, Any]


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"duplicate tool '{tool.name}'")
        self._tools[tool.name] = tool

    def specs(self, max_tier: Tier) -> list[ToolSpec]:
        return [tool.spec() for tool in self._tools.values() if tool.tier <= max_tier]

    def call(
        self, context: AgentContext, name: str, arguments: dict[str, Any], max_tier: Tier
    ) -> ToolResult:
        """Run a tool. Refusals and bad input come back as data, never as exceptions."""
        tool = self._tools.get(name)
        if tool is None:
            return ToolResult(name, None, arguments, False, {"error": "UNKNOWN_TOOL"})
        if tool.tier > max_tier:
            return ToolResult(name, tool.tier, arguments, False, {
                "error": "PERMISSION_DENIED",
                "detail": f"{name} needs tier {tool.tier.name}; this agent is limited to "
                          f"{max_tier.name}.",
            })
        try:
            parsed = tool.input_model.model_validate(arguments)
        except ValidationError as error:
            problems = [f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in error.errors()]
            return ToolResult(name, tool.tier, arguments, False,
                              {"error": "INVALID_ARGUMENTS", "detail": problems})
        return ToolResult(name, tool.tier, parsed.model_dump(), True,
                          tool.handler(context, parsed))


def baht(satang: int) -> int | float:
    whole, rest = divmod(satang, SATANG_PER_THB)
    return whole if rest == 0 else round(satang / SATANG_PER_THB, 2)


def _monthly(items) -> int:
    return sum(i.amount for i in items if i.frequency is Frequency.MONTHLY)


def _profile(context: AgentContext, _: NoInput) -> dict[str, Any]:
    state = context.state
    essential = [e for e in state.expenses if e.category is ExpenseCategory.ESSENTIAL]
    flexible = [e for e in state.expenses if e.category is ExpenseCategory.FLEXIBLE]
    emergency = next((e for e in state.envelopes if e.kind is EnvelopeKind.EMERGENCY), None)
    return {
        "as_of": state.as_of.isoformat(),
        "currency": state.currency,
        "total_cash": baht(state.total_cash),
        "unallocated_cash": baht(state.unallocated.balance),
        "emergency_fund": baht(emergency.balance) if emergency else 0,
        "emergency_fund_target": baht(state.reserve_target),
        "monthly_income": baht(_monthly(state.incomes)),
        "monthly_essential_expenses": baht(_monthly(essential)),
        "monthly_flexible_budget": baht(_monthly(flexible)),
        "monthly_flexible_minimum": baht(
            sum(e.floor for e in flexible if e.frequency is Frequency.MONTHLY)
        ),
        "monthly_debt_minimums": baht(
            sum(d.minimum_payment for d in state.debts if d.balance > 0)
        ),
        "monthly_planned_savings": baht(_monthly(state.transfers)),
    }


def _goals(context: AgentContext, _: NoInput) -> dict[str, Any]:
    state = context.state
    saved = {e.goal_id: e.balance for e in state.envelopes if e.goal_id}
    return {
        "goals": [
            {
                "id": goal.id,
                "name": goal.name,
                "target": baht(goal.target),
                "saved": baht(saved.get(goal.id, 0)),
                "progress_percent": round(100 * saved.get(goal.id, 0) / goal.target, 1),
                "priority": goal.priority,
                "deadline": goal.deadline.isoformat() if goal.deadline else None,
            }
            for goal in sorted(state.goals, key=lambda g: g.priority)
        ]
    }


def _feasibility_data(state: FinancialState, horizon_days: int) -> dict[str, Any]:
    forecast = forecast_cash_flow(state, horizon_days)
    report = check_feasibility(state, horizon_days, planned=forecast)
    return {
        "status": report.status.value,
        "horizon_days": horizon_days,
        "lowest_unallocated_cash": baht(report.min_unallocated),
        "lowest_unallocated_cash_on": report.min_unallocated_on.isoformat(),
        "first_shortfall_on": (
            report.first_shortfall_on.isoformat() if report.first_shortfall_on else None
        ),
        "largest_shortfall": baht(report.max_shortfall),
        "needs_existing_savings": report.needs_reserves,
        "essential_shortfall": baht(report.essential_shortfall),
        "monthly": [
            {
                "month": m.month, "income": baht(m.income), "essential": baht(m.essential),
                "debt_minimum": baht(m.debt_minimum), "flexible": baht(m.flexible),
                "savings_transfers": baht(m.transfers),
                "closing_unallocated": baht(m.closing_unallocated),
            }
            for m in monthly_summary(forecast)
        ],
    }


def _forecast(context: AgentContext, args: ForecastInput) -> dict[str, Any]:
    return _feasibility_data(context.state, args.horizon_days)


def _insights(context: AgentContext, _: NoInput) -> dict[str, Any]:
    state = context.state
    end = state.as_of + timedelta(days=29)
    upcoming = [
        e for e in build_events(state, state.as_of, end, include_transfers=False)
        if e.kind is not EventKind.INCOME
    ]
    income = _monthly(state.incomes)
    essential = _monthly(e for e in state.expenses if e.category is ExpenseCategory.ESSENTIAL)
    debt = sum(d.minimum_payment for d in state.debts if d.balance > 0)
    largest = sorted(
        (e for e in state.expenses if e.frequency is Frequency.MONTHLY),
        key=lambda e: e.amount, reverse=True,
    )[:3]
    return {
        "period": f"{state.as_of.isoformat()} to {end.isoformat()}",
        "upcoming_bills": [
            {"date": e.on.isoformat(), "name": e.name, "amount": baht(e.amount),
             "kind": e.kind.value}
            for e in upcoming
        ],
        "upcoming_bills_total": baht(sum(e.amount for e in upcoming)),
        "committed_share_of_income_percent": (
            round(100 * (essential + debt) / income, 1) if income else None
        ),
        "largest_monthly_expenses": [
            {"name": e.name, "amount": baht(e.amount), "category": e.category.value}
            for e in largest
        ],
        "free_cash_per_month_after_essentials": baht(income - essential - debt),
    }


def _plan_data(plan: Plan) -> dict[str, Any]:
    first = plan.months[0]
    return {
        "strategy": plan.label,
        "emergency_fund_target_reached": plan.reserve.reached_month if plan.reserve else None,
        "goals": [
            {
                "name": g.name,
                "completion_month": g.completion_month,
                "deadline": g.deadline.isoformat() if g.deadline else None,
                "on_track": g.on_track,
                "shortfall_at_deadline": baht(g.shortfall_at_deadline),
            }
            for g in plan.goals
        ],
        "first_month": first.month,
        "first_month_contributions": {k: baht(v) for k, v in first.contributions.items()},
        "first_month_flexible_spending": baht(first.flexible_total),
        "flexible_spending_over_horizon": baht(sum(m.flexible_total for m in plan.months)),
        "validated": True,
    }


def tradeoff_facts(result: PlanningResult) -> list[str]:
    """Plain statements comparing the plans, derived only from plan data."""
    if result.status is not PlanningStatus.OK:
        return []
    facts: list[str] = [note.describe() for note in result.identical]
    plans = result.plans

    with_reserve = [p for p in plans if p.reserve and p.reserve.reached_month]
    if len({p.reserve.reached_month for p in with_reserve}) > 1:
        fastest = min(with_reserve, key=lambda p: p.reserve.reached_month)
        slowest = max(with_reserve, key=lambda p: p.reserve.reached_month)
        facts.append(
            f"{fastest.label} fills the emergency fund by {fastest.reserve.reached_month}; "
            f"{slowest.label} takes until {slowest.reserve.reached_month}."
        )
    for plan in plans:
        if plan.reserve and plan.reserve.reached_month is None:
            facts.append(f"{plan.label} does not reach the emergency fund target in the horizon.")

    kept = {p.label: sum(m.flexible_total for m in p.months) for p in plans}
    if len(set(kept.values())) > 1:
        low, high = min(kept, key=kept.get), max(kept, key=kept.get)
        facts.append(
            f"{low} keeps {baht(kept[low]):,} THB of flexible spending over the horizon; "
            f"{high} keeps {baht(kept[high]):,} THB."
        )

    for index, goal in enumerate(plans[0].goals):
        months = {p.label: p.goals[index].completion_month for p in plans}
        reached = {k: v for k, v in months.items() if v}
        if len(set(months.values())) > 1 and reached:
            first = min(reached, key=reached.get)
            others = ", ".join(
                f"{label} {month or 'not within the horizon'}"
                for label, month in months.items() if label != first
            )
            facts.append(f"{goal.name}: {first} completes it in {reached[first]} ({others}).")
        late = [p.label for p in plans if p.goals[index].on_track is False]
        if late:
            facts.append(f"{goal.name} misses its deadline under: {', '.join(late)}.")
    return facts


def _planning_data(state: FinancialState, horizon_months: int) -> dict[str, Any]:
    result = generate_plans(state, horizon_months=horizon_months)
    data: dict[str, Any] = {"status": result.status.value, "horizon_months": horizon_months}
    if result.status is PlanningStatus.OK:
        data["plans"] = [_plan_data(plan) for plan in result.plans]
        data["tradeoffs"] = tradeoff_facts(result)
    else:
        data["plans"] = []
        data["essential_shortfall"] = baht(result.feasibility.essential_shortfall)
        data["essential_shortfall_on"] = (
            result.feasibility.essential_shortfall_on.isoformat()
            if result.feasibility.essential_shortfall_on else None
        )
    return data


def _optimize(context: AgentContext, args: PlanInput) -> dict[str, Any]:
    return _planning_data(context.state, args.horizon_months)


def _income_change(context: AgentContext, args: IncomeChangeInput) -> dict[str, Any]:
    state = context.state
    factor = 100 + args.percent
    incomes = tuple(
        i.model_copy(update={"amount": round(i.amount * factor / 100)}) for i in state.incomes
    )
    changed = state.model_copy(update={"incomes": tuple(i for i in incomes if i.amount > 0)})
    return {
        "hypothetical": True,
        "note": "Simulated on a copy. The stored financial state was not changed.",
        "income_change_percent": args.percent,
        "new_monthly_income": baht(_monthly(changed.incomes)),
        "current_plan": _feasibility_data(changed, 92),
        "replanning": _planning_data(changed, args.horizon_months),
    }


def default_registry() -> ToolRegistry:
    registry = ToolRegistry()
    for tool in (
        Tool("get_financial_profile", Tier.READ,
             "Current balances, monthly income, expenses, and planned savings.", NoInput,
             _profile),
        Tool("get_financial_goals", Tier.READ,
             "The user's goals with target, saved amount, progress, priority, and deadline.",
             NoInput, _goals),
        Tool("get_spending_insights", Tier.READ,
             "Bills due in the next 30 days, largest expenses, and the share of income "
             "committed to essentials.", NoInput, _insights),
        Tool("get_cash_flow_forecast", Tier.COMPUTE,
             "Daily cash forecast of the current plan: whether it is funded, the lowest "
             "balance, and any shortfall.", ForecastInput, _forecast),
        Tool("optimize_financial_plan", Tier.COMPUTE,
             "Generate and validate the Safety First, Balanced, and Goal First plans and "
             "the trade-offs between them.", PlanInput, _optimize),
        Tool("simulate_income_change", Tier.COMPUTE,
             "Hypothetical: what happens to the current plan and to replanning if income "
             "changes by a percentage. Never changes stored data.", IncomeChangeInput,
             _income_change),
    ):
        registry.register(tool)
    return registry
