"""The user's financial position, before any plan (rules D1 to D4, section 3.1).

One definition of available cash is used everywhere. Over the coming month:

    original surplus = income - essentials - debt minimums - flexible budget
    adjusted surplus = income - essentials - debt minimums - flexible minimum

The adjusted figure exists only when the user allows a flexible reduction, and
it is a proposal, not the user's budget. Savings and extra repayments are
allocations, not obligations, so they are not subtracted here.

Cash is reported in three pools that never overlap:
- unallocated cash, which pays bills and funds allocations;
- the eligible emergency reserve (the emergency envelope);
- money committed to goals, which is not counted as available for anything else.

The buffer (D3) and the reserve (D4) are checked against the same accessible
cash, unallocated plus reserve, and are never added together.
"""

from datetime import date, timedelta
from enum import StrEnum

from lifecfo.cashflow.forecast import EventKind, build_events, forecast_cash_flow
from lifecfo.domain.models import (
    EnvelopeKind,
    ExpenseCategory,
    FinancialState,
    Frequency,
    Frozen,
)
from lifecfo.domain.schedule import clamp_day


class ShortfallKind(StrEnum):
    # Essentials and debt minimums cannot be paid even using the emergency reserve.
    CASH_FLOW_SHORTFALL = "CASH_FLOW_SHORTFALL"
    # Essentials and debt minimums can be paid only by withdrawing from the reserve.
    RESERVE_WITHDRAWAL_NEEDED = "RESERVE_WITHDRAWAL_NEEDED"
    # The user's flexible budget leaves the original budget in deficit.
    FLEXIBLE_SPENDING_CONSTRAINT = "FLEXIBLE_SPENDING_CONSTRAINT"
    # Accessible cash is below the user's configured buffer.
    BUFFER_SHORTFALL = "BUFFER_SHORTFALL"
    # Goal-related kinds, attached per plan by the planner.
    SAVINGS_GOAL_SHORTFALL = "SAVINGS_GOAL_SHORTFALL"
    DEADLINE_RISK = "DEADLINE_RISK"
    FLEXIBLE_GOAL_DELAY = "FLEXIBLE_GOAL_DELAY"


class Shortfall(Frozen):
    kind: ShortfallKind
    amount: int | None  # satang; None when the kind has no single amount
    on: date | None = None
    goal_id: str | None = None
    detail: str


class MonthlyBudget(Frozen):
    """Recurring monthly figures, in satang."""

    income: int
    essentials: int
    debt_minimums: int
    flexible_budget: int
    flexible_minimum: int  # equals the budget when no reduction is allowed
    reduction_allowed: bool

    @property
    def original_surplus(self) -> int:
        return self.income - self.essentials - self.debt_minimums - self.flexible_budget

    @property
    def adjusted_surplus(self) -> int:
        return self.income - self.essentials - self.debt_minimums - self.flexible_minimum


class CashPools(Frozen):
    unallocated: int
    eligible_reserve: int
    committed_to_goals: int

    @property
    def total(self) -> int:
        return self.unallocated + self.eligible_reserve + self.committed_to_goals

    @property
    def accessible(self) -> int:
        """Cash that may serve the buffer and emergencies: counted once."""
        return self.unallocated + self.eligible_reserve


class ReserveStatus(Frozen):
    target: int
    months: float | None  # None when the user set a custom amount
    custom: bool
    eligible: int
    gap: int


class BufferStatus(Frozen):
    configured: bool
    target: int | None
    recommended: int
    accessible_now: int
    shortfall_now: int  # 0 when unconfigured or met


class PositionReport(Frozen):
    as_of: date
    horizon_days: int
    budget: MonthlyBudget
    cash: CashPools
    # Over the coming month under the original budget.
    month_end: date
    income_next_month: int
    obligations_next_month: int  # essentials + debt minimums + flexible budget
    uncommitted_next_month: int  # unallocated + income - obligations; may be negative
    reserve: ReserveStatus
    buffer: BufferStatus
    # Over the horizon, with no new allocations.
    original_deficit: int  # largest cash gap under the original budget
    original_deficit_on: date | None
    adjusted_deficit: int  # the same with flexible at its permitted minimum
    shortfalls: tuple[Shortfall, ...]

    def has(self, kind: ShortfallKind) -> bool:
        return any(s.kind is kind for s in self.shortfalls)


def _month_end(start: date) -> date:
    year, month = (start.year + 1, 1) if start.month == 12 else (start.year, start.month + 1)
    return clamp_day(year, month, start.day) - timedelta(days=1)


def assess_position(state: FinancialState, horizon_days: int) -> PositionReport:
    """The position under the user's own inputs, before any proposal."""
    flexible = [e for e in state.expenses
                if e.category is ExpenseCategory.FLEXIBLE and e.frequency is Frequency.MONTHLY]
    budget = MonthlyBudget(
        income=sum(i.amount for i in state.incomes if i.frequency is Frequency.MONTHLY),
        essentials=state.monthly_essentials,
        debt_minimums=state.monthly_debt_minimums,
        flexible_budget=sum(e.amount for e in flexible),
        flexible_minimum=sum(e.floor for e in flexible),
        reduction_allowed=any(e.reduction_allowed for e in flexible),
    )
    reserve_envelope = state.emergency
    cash = CashPools(
        unallocated=state.unallocated.balance,
        eligible_reserve=reserve_envelope.balance if reserve_envelope else 0,
        committed_to_goals=sum(e.balance for e in state.envelopes
                               if e.kind is EnvelopeKind.GOAL),
    )

    month_end = _month_end(state.as_of)
    window = build_events(state, state.as_of, month_end, include_transfers=False)
    income_next = sum(e.amount for e in window if e.kind is EventKind.INCOME)
    obligations_next = sum(e.amount for e in window if e.kind is not EventKind.INCOME)

    target = state.emergency_target
    reserve = ReserveStatus(
        target=target,
        months=None if state.reserve_target is not None else state.reserve_months,
        custom=state.reserve_target is not None,
        eligible=cash.eligible_reserve,
        gap=max(0, target - cash.eligible_reserve) if reserve_envelope else 0,
    )
    buffer_target = state.buffer_target
    buffer = BufferStatus(
        configured=buffer_target is not None,
        target=buffer_target,
        recommended=state.recommended_buffer,
        accessible_now=cash.accessible,
        shortfall_now=max(0, (buffer_target or 0) - cash.accessible),
    )

    original = forecast_cash_flow(state, horizon_days, include_transfers=False)
    adjusted = forecast_cash_flow(state, horizon_days, include_transfers=False,
                                  flexible_at_floor=True)
    essentials = forecast_cash_flow(state, horizon_days, include_transfers=False,
                                    exclude_flexible=True)

    shortfalls: list[Shortfall] = []
    essential_gap = max(0, -(essentials.min_unallocated + cash.eligible_reserve))
    if essential_gap:
        on = next(d.on for d in essentials.days
                  if d.unallocated + cash.eligible_reserve < 0)
        shortfalls.append(Shortfall(
            kind=ShortfallKind.CASH_FLOW_SHORTFALL, amount=essential_gap, on=on,
            detail="Essential expenses and minimum debt payments cannot be paid on time even "
                   "with no flexible spending, no savings, and the whole emergency reserve "
                   "used. They are not reduced; income or obligations must change."))
    elif essentials.max_shortfall:
        shortfalls.append(Shortfall(
            kind=ShortfallKind.RESERVE_WITHDRAWAL_NEEDED, amount=essentials.max_shortfall,
            on=essentials.first_shortfall_on,
            detail="Essential expenses and minimum debt payments can be paid on time only by "
                   "withdrawing from the emergency reserve."))
    if original.max_shortfall and not essential_gap:
        detail = ("Under the original budget, essentials, debt minimums, and the flexible "
                  "budget exceed the cash available.")
        if not budget.reduction_allowed:
            detail += " Flexible reductions are not permitted, so the budget is a constraint."
        elif adjusted.max_shortfall:
            detail += " Even at the permitted flexible minimum a gap remains."
        else:
            detail += (" Reducing flexible spending within the permitted range would close "
                       "the gap; that is a proposal and needs approval.")
        shortfalls.append(Shortfall(
            kind=ShortfallKind.FLEXIBLE_SPENDING_CONSTRAINT, amount=original.max_shortfall,
            on=original.first_shortfall_on, detail=detail))
    if buffer.shortfall_now:
        shortfalls.append(Shortfall(
            kind=ShortfallKind.BUFFER_SHORTFALL, amount=buffer.shortfall_now, on=state.as_of,
            detail="Accessible cash (unallocated plus emergency reserve) is below the "
                   "configured minimum cash buffer. Goal contributions and extra repayments "
                   "wait until it is restored."))

    return PositionReport(
        as_of=state.as_of,
        horizon_days=horizon_days,
        budget=budget,
        cash=cash,
        month_end=month_end,
        income_next_month=income_next,
        obligations_next_month=obligations_next,
        uncommitted_next_month=cash.unallocated + income_next - obligations_next,
        reserve=reserve,
        buffer=buffer,
        original_deficit=original.max_shortfall,
        original_deficit_on=original.first_shortfall_on,
        adjusted_deficit=adjusted.max_shortfall,
        shortfalls=tuple(shortfalls),
    )
