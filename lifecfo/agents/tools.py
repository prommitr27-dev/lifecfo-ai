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
from datetime import date, timedelta
from enum import IntEnum, StrEnum
from typing import Annotated, Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from lifecfo.cashflow import check_feasibility, forecast_cash_flow, monthly_summary
from lifecfo.cashflow.forecast import EventKind, build_events
from lifecfo.domain.models import (
    EnvelopeKind,
    Expense,
    ExpenseCategory,
    FinancialState,
    Frequency,
)
from lifecfo.domain.money import SATANG_PER_THB
from lifecfo.domain.schedule import clamp_day
from lifecfo.llm.base import ToolSpec
from lifecfo.optimization import Plan, PlanningResult, PlanningStatus, generate_plans
from lifecfo.optimization.optimizer import horizon_days
from lifecfo.optimization.reasons import deferral_reasons
from lifecfo.services.sandbox import AGENT, SandboxService


class Tier(IntEnum):
    READ = 0
    COMPUTE = 1
    PROPOSE = 2
    EXECUTE = 3


@dataclass(frozen=True)
class AgentContext:
    state: FinancialState
    # Needed by PROPOSE and EXECUTE tools; None in read-only or hypothetical contexts.
    sandbox: SandboxService | None = None


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


class Strategy(StrEnum):
    SAFETY_FIRST = "SAFETY_FIRST"
    BALANCED = "BALANCED"
    GOAL_FIRST = "GOAL_FIRST"


class ProposeInput(NoInput):
    # Declared as a plain string so that "Balanced" or "safety first" from a model is
    # normalised here instead of being rejected by the provider's schema check.
    strategy: Annotated[str, Field(max_length=40, description=(
        "Which plan to propose: SAFETY_FIRST, BALANCED, or GOAL_FIRST."))]
    horizon_months: Annotated[int, Field(ge=1, le=24)] = 12

    @field_validator("strategy")
    @classmethod
    def _known_strategy(cls, value: str) -> str:
        normalised = "_".join(value.strip().upper().replace("-", " ").split())
        if normalised not in Strategy.__members__:
            raise ValueError("must be SAFETY_FIRST, BALANCED, or GOAL_FIRST")
        return normalised


class AuditInput(NoInput):
    limit: Annotated[int, Field(ge=1, le=50)] = 10


class UnexpectedExpenseInput(NoInput):
    amount_thb: Annotated[float | None, Field(gt=0, le=100_000_000, description=(
        "Size of the one-off expense in THB. Give this or percent_of_monthly_income."))] = None
    percent_of_monthly_income: Annotated[float | None, Field(gt=0, le=1000, description=(
        "Size of the expense as a percentage of monthly income, e.g. 30."))] = None
    days_from_now: Annotated[int, Field(ge=0, le=365, description=(
        "When the expense must be paid, in days from the profile date."))] = 0
    horizon_months: Annotated[int, Field(ge=1, le=24)] = 12

    @model_validator(mode="after")
    def _one_size(self):
        if (self.amount_thb is None) == (self.percent_of_monthly_income is None):
            raise ValueError("give exactly one of amount_thb or percent_of_monthly_income")
        return self


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


def _one_month_ahead(start: date) -> date:
    """Last day of the month-long window starting at `start` (1 Dec -> 31 Dec)."""
    year, month = (start.year + 1, 1) if start.month == 12 else (start.year, start.month + 1)
    return clamp_day(year, month, start.day) - timedelta(days=1)


def baht(satang: int) -> int | float:
    whole, rest = divmod(satang, SATANG_PER_THB)
    return whole if rest == 0 else round(satang / SATANG_PER_THB, 2)


def _monthly(items) -> int:
    return sum(i.amount for i in items if i.frequency is Frequency.MONTHLY)


def _profile(context: AgentContext, _: NoInput) -> dict[str, Any]:
    state = context.state
    emergency = next((e for e in state.envelopes if e.kind is EnvelopeKind.EMERGENCY), None)
    # Totals over the coming month, so they are right for recurring items and for the
    # dated schedule of an activated plan alike.
    end = _one_month_ahead(state.as_of)
    totals = dict.fromkeys(EventKind, 0)
    for event in build_events(state, state.as_of, end):
        totals[event.kind] += event.amount
    floor = sum(
        e.amount for e in build_events(state, state.as_of, end, flexible_at_floor=True)
        if e.kind is EventKind.FLEXIBLE_EXPENSE
    )
    return {
        "as_of": state.as_of.isoformat(),
        "currency": state.currency,
        "total_cash": baht(state.total_cash),
        "unallocated_cash": baht(state.unallocated.balance),
        "emergency_fund": baht(emergency.balance) if emergency else 0,
        "emergency_fund_target": baht(state.emergency_target),
        "monthly_income": baht(totals[EventKind.INCOME]),
        "monthly_essential_expenses": baht(totals[EventKind.ESSENTIAL_EXPENSE]),
        "monthly_flexible_budget": baht(totals[EventKind.FLEXIBLE_EXPENSE]),
        "monthly_flexible_minimum": baht(floor),
        "monthly_debt_minimums": baht(totals[EventKind.DEBT_MINIMUM]),
        "monthly_planned_savings": baht(totals[EventKind.SAVINGS_TRANSFER]),
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
    end = _one_month_ahead(state.as_of)
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


def _plan_data(plan: Plan, state: FinancialState) -> dict[str, Any]:
    first = plan.months[0]
    reasons = deferral_reasons(state, plan)
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
                "why_late": reasons.get(g.goal_id),
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
        data["plans"] = [_plan_data(plan, state) for plan in result.plans]
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


def _compare(before: FinancialState, after: FinancialState, months: int) -> dict[str, Any]:
    """The same checks on the current state and on the changed one, over one horizon."""
    days = horizon_days(before.as_of, months)
    base_cash, new_cash = _feasibility_data(before, days), _feasibility_data(after, days)
    base_plan = generate_plans(before, horizon_months=months)
    new_plan = generate_plans(after, horizon_months=months)
    facts: list[str] = []

    if base_cash["status"] != new_cash["status"]:
        facts.append(f"Current plan status changes from {base_cash['status']} to "
                     f"{new_cash['status']}.")
    if new_cash["largest_shortfall"] > base_cash["largest_shortfall"]:
        facts.append(
            f"New cash deficit: the current plan would be short by up to "
            f"{new_cash['largest_shortfall']:,} THB (before: "
            f"{base_cash['largest_shortfall']:,} THB), first on "
            f"{new_cash['first_shortfall_on']}.")
    if new_cash["lowest_unallocated_cash"] < base_cash["lowest_unallocated_cash"]:
        facts.append(
            f"Lowest unallocated cash falls from {base_cash['lowest_unallocated_cash']:,} THB "
            f"to {new_cash['lowest_unallocated_cash']:,} THB.")
    if new_cash["essential_shortfall"] > base_cash["essential_shortfall"]:
        facts.append(
            f"Liquidity risk: essentials could not be paid on time; the shortfall reaches "
            f"{new_cash['essential_shortfall']:,} THB.")

    if base_plan.status is PlanningStatus.OK and new_plan.status is not PlanningStatus.OK:
        facts.append(f"No regular plan exists any more ({new_plan.status.value}).")
    elif base_plan.status is PlanningStatus.OK and new_plan.status is PlanningStatus.OK:
        old_by = {p.strategy: p for p in base_plan.plans}
        for plan in new_plan.plans:
            old = old_by[plan.strategy]
            if old.reserve and plan.reserve and (
                    old.reserve.reached_month != plan.reserve.reached_month):
                facts.append(
                    f"{plan.label}: emergency fund target reached "
                    f"{plan.reserve.reached_month or 'not within the horizon'} "
                    f"(before: {old.reserve.reached_month or 'not within the horizon'}).")
            for old_goal, goal in zip(old.goals, plan.goals, strict=True):
                if old_goal.completion_month != goal.completion_month:
                    facts.append(
                        f"{plan.label}: {goal.name} "
                        + (f"completes in {goal.completion_month}" if goal.completion_month
                           else "does not complete within the horizon")
                        + f" (before: {old_goal.completion_month or 'not within the horizon'}).")
                if old_goal.on_track is not False and goal.on_track is False:
                    facts.append(
                        f"{plan.label}: {goal.name} now misses its deadline "
                        f"{goal.deadline} by {baht(goal.shortfall_at_deadline):,} THB.")
    return {
        "horizon_months": months,
        "horizon_days": days,
        "baseline_current_plan_status": base_cash["status"],
        "baseline_largest_shortfall": base_cash["largest_shortfall"],
        "baseline_planning_status": base_plan.status.value,
        "changes": facts or ["No change in status, shortfall, or goal timing."],
    }


def _income_change(context: AgentContext, args: IncomeChangeInput) -> dict[str, Any]:
    state = context.state
    factor = 100 + args.percent
    # The change applies to recurring income for the whole horizon. One-off income
    # (a bonus, a refund) is left as it is: it is not part of the regular pay that changed.
    incomes = tuple(
        i.model_copy(update={"amount": round(i.amount * factor / 100)})
        if i.frequency is Frequency.MONTHLY else i
        for i in state.incomes
    )
    changed = state.model_copy(update={"incomes": tuple(i for i in incomes if i.amount > 0)})
    return {
        "hypothetical": True,
        "note": "Simulated on a copy. The stored financial state was not changed.",
        "income_change_percent": args.percent,
        "new_monthly_income": baht(_monthly(changed.incomes)),
        "current_plan": _feasibility_data(
            changed, horizon_days(changed.as_of, args.horizon_months)),
        "replanning": _planning_data(changed, args.horizon_months),
        "compared_with_current": _compare(state, changed, args.horizon_months),
        "assumption": "The change applies to recurring income only, from today to the end "
                      "of the horizon; one-off income is unchanged.",
    }


def _unexpected_expense(context: AgentContext, args: UnexpectedExpenseInput) -> dict[str, Any]:
    state = context.state
    if args.amount_thb is not None:
        amount = round(args.amount_thb * SATANG_PER_THB)
    else:
        amount = round(_monthly(state.incomes) * args.percent_of_monthly_income / 100)
    if amount <= 0:
        return {"error": "NO_INCOME", "detail": "No monthly income to take a percentage of."}
    due = state.as_of + timedelta(days=args.days_from_now)
    shock = Expense(
        id="hypothetical-expense", name="Unexpected expense",
        category=ExpenseCategory.ESSENTIAL, amount=amount,
        frequency=Frequency.ONE_TIME, on_date=due,
    )
    changed = state.model_copy(update={"expenses": (*state.expenses, shock)})
    emergency = next((e for e in state.envelopes if e.kind is EnvelopeKind.EMERGENCY), None)
    fund = emergency.balance if emergency else 0
    return {
        "hypothetical": True,
        "note": "Simulated on a copy. The stored financial state was not changed.",
        "expense_amount": baht(amount),
        "expense_due_on": due.isoformat(),
        "emergency_fund_now": baht(fund),
        "expense_not_covered_by_emergency_fund": baht(max(0, amount - fund)),
        "current_plan": _feasibility_data(
            changed, horizon_days(changed.as_of, args.horizon_months)),
        "replanning_without_touching_savings": _planning_data(changed, args.horizon_months),
        "compared_with_current": _compare(state, changed, args.horizon_months),
        "limitation": (
            "Replanning here pays the expense from income and unallocated cash only. Using "
            "the emergency fund is a recovery decision that needs the user's approval and "
            "is not simulated yet."
        ),
    }


_NO_SANDBOX = {"error": "SANDBOX_UNAVAILABLE",
               "detail": "This is a hypothetical view; nothing can be proposed or executed here."}


def _request_approval(context: AgentContext, args: ProposeInput) -> dict[str, Any]:
    if context.sandbox is None:
        return _NO_SANDBOX
    result = generate_plans(context.state, horizon_months=args.horizon_months)
    if result.status is not PlanningStatus.OK:
        return {"error": result.status.value, "detail": "No plan exists to propose."}
    plan = next(p for p in result.plans if p.strategy == args.strategy)
    outcome = context.sandbox.propose(plan, AGENT)
    return {
        "ok": outcome.ok, "code": outcome.code, "message": outcome.message,
        "plan_id": outcome.data.get("plan_id"), "strategy": plan.label,
        "next_step": "The user must approve or reject this plan in the Sandbox view. "
                     "The assistant cannot approve it.",
    }


def _execute(context: AgentContext, _: NoInput) -> dict[str, Any]:
    # The tool takes no id on purpose: a model cannot be trusted to copy one, and the
    # only thing that may be executed is what the user has approved.
    if context.sandbox is None:
        return _NO_SANDBOX
    usable = [a for a in context.sandbox.store.list_approvals()
              if a["decision"] == "APPROVED" and a["used_at"] is None]
    if len(usable) > 1:
        return {"ok": False, "code": "SEVERAL_APPROVED_PLANS",
                "message": "More than one approved plan is waiting. The user must choose "
                           "which to execute in the Sandbox view."}
    outcome = context.sandbox.execute(usable[0]["id"] if usable else None, AGENT)
    return {"ok": outcome.ok, "code": outcome.code, "message": outcome.message,
            **{k: v for k, v in outcome.data.items() if k in ("plan_id", "strategy")}}


def _audit(context: AgentContext, args: AuditInput) -> dict[str, Any]:
    if context.sandbox is None:
        return _NO_SANDBOX
    store = context.sandbox.store
    return {
        "chain_intact": store.verify_audit_chain(),
        "entries": [
            {"seq": e.seq, "time": e.ts, "actor": e.actor, "action": e.action,
             "code": e.payload.get("code"), "plan_id": e.payload.get("plan_id")}
            for e in store.list_audit(args.limit)
        ],
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
        Tool("simulate_unexpected_expense", Tier.COMPUTE,
             "Hypothetical: what happens to the current plan and to replanning if a one-off "
             "unexpected expense (repair, medical bill) must be paid. Size is an amount in "
             "THB or a percentage of monthly income. Never changes stored data.",
             UnexpectedExpenseInput, _unexpected_expense),
        Tool("get_audit_history", Tier.READ,
             "Recent sandbox audit log entries and whether the hash chain is intact.",
             AuditInput, _audit),
        Tool("request_plan_approval", Tier.PROPOSE,
             "Store one of the three validated plans as a proposal and ask the user to "
             "approve it in the app. Does not approve or apply anything.", ProposeInput,
             _request_approval),
        Tool("execute_approved_sandbox_plan", Tier.EXECUTE,
             "Activate a plan in the sandbox. Works only if the user has already approved "
             "that plan in the app; otherwise it is refused. Takes no arguments.", NoInput,
             _execute),
    ):
        registry.register(tool)
    return registry
