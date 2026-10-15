"""Plan data, applying a plan to a state, and deterministic plan validation.

`validate_plan` is the gate every allocation must pass, whoever produced it:
the optimizer, a recovery routine, or a suggestion relayed by the LLM agent.
"""

import hashlib
from datetime import date
from enum import StrEnum

from lifecfo.cashflow.feasibility import FeasibilityReport
from lifecfo.cashflow.forecast import forecast_cash_flow
from lifecfo.cashflow.position import PositionReport
from lifecfo.debt.schedule import schedule_debts
from lifecfo.domain.models import (
    EnvelopeKind,
    Expense,
    ExpenseCategory,
    ExtraDebtPayment,
    FinancialState,
    Frequency,
    Frozen,
    SavingsTransfer,
)
from lifecfo.domain.money import format_thb


def state_fingerprint(state: FinancialState) -> str:
    """Stable hash of a state, used to bind plans and approvals to it."""
    return hashlib.sha256(state.model_dump_json().encode()).hexdigest()


class PlanMonth(Frozen):
    month: str  # YYYY-MM
    period_start: date
    transfer_date: date  # savings are swept on the last day of the month
    contributions: dict[str, int]  # envelope id -> satang
    flexible: dict[str, int]  # flexible expense id -> satang per occurrence
    flexible_total: int
    flexible_max: int  # the user's original flexible budget for the month
    closing_unallocated: int
    extra_debt: dict[str, int] = {}  # debt id -> satang applied above the minimum
    # How far accessible cash (unallocated + reserve) is below the buffer after the
    # month-end sweep; 0 when the buffer is met or not configured.
    buffer_shortfall: int = 0


class GoalProjection(Frozen):
    goal_id: str
    name: str
    target: int
    saved_now: int
    projected_saved: int  # at the end of the plan horizon
    completion_month: str | None  # None: not reached within the horizon
    deadline: date | None
    on_track: bool | None  # None when the goal has no deadline
    shortfall_at_deadline: int
    flexible: bool = False
    # Saved into the goal during the plan horizon, and the average per month. For a goal
    # without a deadline these replace a completion date when none can be projected.
    contributed_in_horizon: int = 0
    average_monthly_contribution: int = 0


class ReserveProjection(Frozen):
    target: int
    saved_now: int
    projected_saved: int
    reached_month: str | None


class Plan(Frozen):
    strategy: str
    label: str
    start: date
    horizon_months: int
    state_hash: str
    months: tuple[PlanMonth, ...]
    goals: tuple[GoalProjection, ...]
    reserve: ReserveProjection | None
    buffer_target: int | None = None
    debt_order: tuple[str, ...] = ()

    @property
    def end(self) -> date:
        return self.months[-1].transfer_date

    @property
    def horizon_days(self) -> int:
        return (self.end - self.start).days + 1

    @property
    def months_below_buffer(self) -> tuple[str, ...]:
        return tuple(m.month for m in self.months if m.buffer_shortfall > 0)

    @property
    def goals_at_risk(self) -> tuple[str, ...]:
        return tuple(g.goal_id for g in self.goals if g.on_track is False)

    def fingerprint(self) -> str:
        return hashlib.sha256(self.model_dump_json().encode()).hexdigest()

    def same_allocations(self, other: "Plan") -> bool:
        mine = [(m.contributions, m.flexible, m.extra_debt) for m in self.months]
        theirs = [(m.contributions, m.flexible, m.extra_debt) for m in other.months]
        return mine == theirs


class PlanValidation(Frozen):
    ok: bool
    violations: tuple[str, ...] = ()


class PlanningStatus(StrEnum):
    OK = "OK"
    # Essentials can only be paid by drawing on existing envelopes. That is a
    # recovery decision, so no base plan is offered.
    REQUIRES_RESERVE_DRAWDOWN = "REQUIRES_RESERVE_DRAWDOWN"
    # Essentials cannot be paid at all. No plan exists.
    ESSENTIAL_SHORTFALL = "ESSENTIAL_SHORTFALL"
    # Essentials can be paid, but not together with the user's flexible budget at its
    # permitted minimum. No plan exists without changing a user preference.
    FLEXIBLE_SPENDING_CONSTRAINT = "FLEXIBLE_SPENDING_CONSTRAINT"


class IdenticalPlans(Frozen):
    """Facts explaining why two strategies produced the same allocations."""

    strategies: tuple[str, str]
    months_cash_fully_allocated: int
    months_flexible_at_floor: int
    envelopes_fully_funded: tuple[str, ...]
    horizon_months: int

    def describe(self) -> str:
        funded = ", ".join(self.envelopes_fully_funded) or "none"
        return (
            f"{self.strategies[0]} and {self.strategies[1]} produce identical allocations. "
            f"All free cash is allocated in {self.months_cash_fully_allocated} of "
            f"{self.horizon_months} months, flexible spending is at its floor in "
            f"{self.months_flexible_at_floor} months, and these envelopes reach their target "
            f"within the horizon: {funded}. The strategies only differ when there is a real "
            "choice about where a baht goes."
        )


class PlanningResult(Frozen):
    status: PlanningStatus
    plans: tuple[Plan, ...] = ()
    feasibility: FeasibilityReport
    identical: tuple[IdenticalPlans, ...] = ()
    # The user's own position, computed before any proposal (rules D2: disclosed first).
    position: PositionReport | None = None


def apply_plan(state: FinancialState, plan: Plan) -> FinancialState:
    """Copy of `state` with its transfers and flexible spending replaced by the plan's.

    Used for validation and projection only; it does not move any money.
    """
    by_month = {m.month: m for m in plan.months}

    transfers = tuple(
        SavingsTransfer(
            id=f"plan:{envelope_id}:{month.month}",
            envelope_id=envelope_id,
            amount=amount,
            frequency=Frequency.ONE_TIME,
            on_date=month.transfer_date,
        )
        for month in plan.months
        for envelope_id, amount in month.contributions.items()
        if amount > 0
    )

    expenses: list[Expense] = []
    for expense in state.expenses:
        if expense.category is ExpenseCategory.ESSENTIAL:
            expenses.append(expense)
            continue
        for occurrence in expense.occurrences(plan.start, plan.end):
            amount = by_month[f"{occurrence:%Y-%m}"].flexible.get(expense.id, expense.amount)
            if amount > 0:
                expenses.append(
                    Expense(
                        id=f"{expense.id}@{occurrence.isoformat()}",
                        name=expense.name,
                        category=ExpenseCategory.FLEXIBLE,
                        amount=amount,
                        min_amount=min(expense.floor, amount),
                        frequency=Frequency.ONE_TIME,
                        on_date=occurrence,
                    )
                )

    debt_payments = tuple(
        ExtraDebtPayment(
            id=f"plan:{debt_id}:{month.month}",
            debt_id=debt_id,
            amount=amount,
            frequency=Frequency.ONE_TIME,
            on_date=month.transfer_date,
        )
        for month in plan.months
        for debt_id, amount in month.extra_debt.items()
        if amount > 0
    )
    return state.model_copy(update={
        "transfers": transfers, "expenses": tuple(expenses), "debt_payments": debt_payments,
    })


def validate_plan(state: FinancialState, plan: Plan) -> PlanValidation:
    """Check every hard constraint. An empty violation list means the plan is safe to offer."""
    violations: list[str] = []

    if plan.state_hash != state_fingerprint(state):
        violations.append("Plan was built for a different financial state.")
    if plan.start != state.as_of:
        violations.append("Plan start date does not match the state.")

    capacity: dict[str, int] = {}
    goals = {g.id: g for g in state.goals}
    for envelope in state.envelopes:
        if envelope.kind is EnvelopeKind.EMERGENCY:
            capacity[envelope.id] = max(0, state.emergency_target - envelope.balance)
        elif envelope.kind is EnvelopeKind.GOAL:
            capacity[envelope.id] = max(0, goals[envelope.goal_id].target - envelope.balance)

    flexible = {
        e.id: e for e in state.expenses if e.category is ExpenseCategory.FLEXIBLE
    }
    contributed: dict[str, int] = dict.fromkeys(capacity, 0)

    for month in plan.months:
        for envelope_id, amount in month.contributions.items():
            if envelope_id not in capacity:
                violations.append(f"{month.month}: unknown envelope '{envelope_id}'.")
                continue
            if amount < 0:
                violations.append(f"{month.month}: negative contribution to '{envelope_id}'.")
            contributed[envelope_id] += amount
        for expense_id, amount in month.flexible.items():
            expense = flexible.get(expense_id)
            if expense is None:
                violations.append(f"{month.month}: unknown flexible expense '{expense_id}'.")
            elif not expense.floor <= amount <= expense.amount:
                violations.append(
                    f"{month.month}: '{expense_id}' must stay between "
                    f"{format_thb(expense.floor)} and {format_thb(expense.amount)}."
                )

    for envelope_id, total in contributed.items():
        if total > capacity[envelope_id]:
            violations.append(
                f"Envelope '{envelope_id}' would be overfunded by "
                f"{format_thb(total - capacity[envelope_id])}."
            )

    debts = {d.id: d for d in state.debts}
    planned_extra: dict[str, int] = {}
    for month in plan.months:
        for debt_id, amount in month.extra_debt.items():
            debt = debts.get(debt_id)
            if debt is None:
                violations.append(f"{month.month}: unknown debt '{debt_id}'.")
            elif not debt.extra_payment_allowed:
                violations.append(f"{month.month}: extra repayment of '{debt_id}' is not "
                                  "permitted.")
            elif amount < 0:
                violations.append(f"{month.month}: negative extra repayment of '{debt_id}'.")
            planned_extra[debt_id] = planned_extra.get(debt_id, 0) + amount

    if not violations and planned_extra:
        applied = schedule_debts(apply_plan(state, plan), plan.start, plan.end)
        for debt_id, amount in planned_extra.items():
            paid = sum(p.extra_paid for p in applied[debt_id].periods)
            if paid != amount:
                violations.append(f"Extra repayment of '{debt_id}' exceeds what is owed.")

    if not violations:
        forecast = forecast_cash_flow(apply_plan(state, plan), plan.horizon_days)
        if forecast.max_shortfall > 0:
            violations.append(
                f"Cash runs short by {format_thb(forecast.max_shortfall)} starting "
                f"{forecast.first_shortfall_on}."
            )

    return PlanValidation(ok=not violations, violations=tuple(violations))
