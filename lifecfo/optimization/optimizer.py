"""Monthly linear program that allocates free cash across envelopes.

One LP serves all three strategies; only the parameters differ. The model and
its assumptions are described in docs/financial_model/FINANCIAL_MODEL.md.

Decision variables, per month t of the horizon:
  x[e,t]  contribution to envelope e (emergency reserve or a goal), swept on
          the last day of the month
  th[t]   share of the cuttable part of flexible spending that is kept, 0..1
  s[e,t]  how far envelope e is behind its ramp at the end of month t

Hard constraints:
  - unallocated cash is never negative on any day that has a scheduled event
    (essentials and debt minimums are always paid in full)
  - an envelope never receives more than it still needs

The solution is rounded down to whole baht on cumulative contributions, which
can only leave more cash on hand, and is then re-checked by `validate_plan`
against the daily forecast before it is returned.
"""

import calendar
import math
from datetime import date

import numpy as np
from scipy.optimize import linprog

from lifecfo.cashflow.feasibility import check_feasibility
from lifecfo.cashflow.forecast import EventKind, build_events, forecast_cash_flow
from lifecfo.domain.models import EnvelopeKind, ExpenseCategory, FinancialState
from lifecfo.domain.money import SATANG_PER_THB
from lifecfo.optimization.plan import (
    GoalProjection,
    IdenticalPlans,
    Plan,
    PlanMonth,
    PlanningResult,
    PlanningStatus,
    ReserveProjection,
    apply_plan,
    state_fingerprint,
    validate_plan,
)
from lifecfo.optimization.strategies import StrategyConfig, load_strategies

_EPS = 1e-6


class PlanValidationError(RuntimeError):
    """The optimizer produced a plan that failed validation. This is a bug."""


def _periods(start: date, months: int) -> list[tuple[date, date]]:
    """Calendar-month periods from `start`; the first may be a partial month."""
    out: list[tuple[date, date]] = []
    year, month, lo = start.year, start.month, start
    for _ in range(months):
        hi = date(year, month, calendar.monthrange(year, month)[1])
        out.append((lo, hi))
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
        lo = date(year, month, 1)
    return out


class _Period:
    """Cumulative cash figures, in baht, for each event day of one month."""

    def __init__(self) -> None:
        self.days: list[date] = []
        self.fixed: list[float] = []  # income - essentials - debt minimums, cumulative
        self.flex_min: list[float] = []  # flexible spending at its floor, cumulative
        self.flex_max: list[float] = []  # flexible spending as budgeted, cumulative

    @property
    def net(self) -> float:
        return self.fixed[-1] if self.fixed else 0.0

    @property
    def fmin(self) -> float:
        return self.flex_min[-1] if self.flex_min else 0.0

    @property
    def cuttable(self) -> float:
        return (self.flex_max[-1] - self.flex_min[-1]) if self.flex_max else 0.0


def _build_periods(state: FinancialState, spans: list[tuple[date, date]]) -> list[_Period]:
    start, end = spans[0][0], spans[-1][1]
    budgeted = build_events(state, start, end, include_transfers=False)
    floor = build_events(state, start, end, flexible_at_floor=True, include_transfers=False)

    periods: list[_Period] = []
    for lo, hi in spans:
        period = _Period()
        days = sorted({e.on for e in budgeted if lo <= e.on <= hi})
        fixed = fmin = fmax = 0.0
        for day in days:
            for event in budgeted:
                if event.on != day:
                    continue
                if event.kind is EventKind.FLEXIBLE_EXPENSE:
                    fmax += event.amount / SATANG_PER_THB
                else:
                    fixed += event.unallocated_delta / SATANG_PER_THB
            fmin += sum(
                e.amount for e in floor
                if e.on == day and e.kind is EventKind.FLEXIBLE_EXPENSE
            ) / SATANG_PER_THB
            period.days.append(day)
            period.fixed.append(fixed)
            period.flex_min.append(fmin)
            period.flex_max.append(fmax)
        periods.append(period)
    return periods


def _months_until(deadline: date | None, spans: list[tuple[date, date]]) -> int:
    """Number of month-end sweeps that land on or before the deadline."""
    if deadline is None:
        return len(spans)
    return sum(1 for _, hi in spans if hi <= deadline)


def optimize_plan(
    state: FinancialState, strategy: StrategyConfig, horizon_months: int = 12
) -> Plan | None:
    """Best plan for one strategy, or None when essentials cannot be funded from income.

    Existing `state.transfers` are ignored: the plan replaces them.
    """
    if horizon_months < 1:
        raise ValueError("horizon_months must be at least 1")

    spans = _periods(state.as_of, horizon_months)
    periods = _build_periods(state, spans)
    n_months = horizon_months
    opening = state.unallocated.balance / SATANG_PER_THB
    goals = {g.id: g for g in state.goals}

    # Envelopes that can receive money: (envelope, remaining need in baht, weight,
    # surplus bonus, months to reach the target).
    targets = []
    for envelope in state.envelopes:
        if envelope.kind is EnvelopeKind.EMERGENCY:
            need = max(0, state.reserve_target - envelope.balance)
            targets.append((envelope, need / SATANG_PER_THB, strategy.reserve_weight,
                            strategy.surplus_reserve, strategy.reserve_ramp_months))
        elif envelope.kind is EnvelopeKind.GOAL:
            goal = goals[envelope.goal_id]
            factor = strategy.priority_factor(goal.priority)
            need = max(0, goal.target - envelope.balance)
            targets.append((envelope, need / SATANG_PER_THB, strategy.goal_weight * factor,
                            strategy.surplus_goal * factor, _months_until(goal.deadline, spans)))
    n_env = len(targets)

    def x(e: int, t: int) -> int:
        return e * n_months + t

    def th(t: int) -> int:
        return n_env * n_months + t

    def s(e: int, t: int) -> int:
        return n_env * n_months + n_months + e * n_months + t

    n_vars = 2 * n_env * n_months + n_months
    rows: list[np.ndarray] = []
    rhs: list[float] = []

    # Liquidity: unallocated cash stays non-negative on every event day and after
    # each month-end sweep.
    carried = opening  # cash carried in if nothing is saved and flexible is at its floor
    for t, period in enumerate(periods):
        base = np.zeros(n_vars)
        for prev in range(t):
            base[th(prev)] = periods[prev].cuttable
            for e in range(n_env):
                base[x(e, prev)] = 1.0
        for i in range(len(period.days)):
            row = base.copy()
            row[th(t)] = period.flex_max[i] - period.flex_min[i]
            rows.append(row)
            rhs.append(carried + period.fixed[i] - period.flex_min[i])
        row = base.copy()
        row[th(t)] = period.cuttable
        for e in range(n_env):
            row[x(e, t)] = 1.0
        rows.append(row)
        rhs.append(carried + period.net - period.fmin)
        carried += period.net - period.fmin

    if min(rhs) < -_EPS:
        return None  # even with no savings and flexible at its floor, cash runs out

    for e, (_, need, _, _, ramp) in enumerate(targets):
        # Envelope cap.
        row = np.zeros(n_vars)
        for t in range(n_months):
            row[x(e, t)] = 1.0
        rows.append(row)
        rhs.append(need)
        # Behind-the-ramp shortfall: s[e,t] >= required(t) - contributed so far.
        for t in range(n_months):
            required = need if ramp <= 0 else need * min(1.0, (t + 1) / ramp)
            row = np.zeros(n_vars)
            for prev in range(t + 1):
                row[x(e, prev)] = -1.0
            row[s(e, t)] = -1.0
            rows.append(row)
            rhs.append(-required)

    cost = np.zeros(n_vars)
    for e, (_, _, weight, bonus, _) in enumerate(targets):
        for t in range(n_months):
            cost[s(e, t)] = weight
            # A baht saved in month t sits in the envelope for the rest of the horizon.
            cost[x(e, t)] = -strategy.surplus_bonus_scale * bonus * (n_months - t)
    for t, period in enumerate(periods):
        cost[th(t)] = -strategy.flexible_cut_weight * period.cuttable

    bounds = [(0.0, None)] * n_vars
    for t in range(n_months):
        bounds[th(t)] = (0.0, 1.0)

    result = linprog(cost, A_ub=np.array(rows), b_ub=np.array(rhs), bounds=bounds,
                     method="highs")
    if not result.success:
        raise PlanValidationError(f"LP solver failed for {strategy.name}: {result.message}")
    sol = result.x

    # Round cumulative contributions down to whole baht (never more cash out than the LP).
    contributions: list[dict[str, int]] = [{} for _ in range(n_months)]
    cumulative_satang: dict[str, list[int]] = {}
    for e, (envelope, need, _, _, _) in enumerate(targets):
        need_satang = round(need * SATANG_PER_THB)
        running, previous, series = 0.0, 0, []
        for t in range(n_months):
            running += max(0.0, sol[x(e, t)])
            if running >= need - _EPS:
                rounded = need_satang
            else:
                rounded = math.floor(running + _EPS) * SATANG_PER_THB
            rounded = max(previous, min(rounded, need_satang))
            if rounded > previous:
                contributions[t][envelope.id] = rounded - previous
            previous = rounded
            series.append(rounded)
        cumulative_satang[envelope.id] = series

    flexible_expenses = [e for e in state.expenses if e.category is ExpenseCategory.FLEXIBLE]
    months: list[PlanMonth] = []
    for t, ((lo, hi), period) in enumerate(zip(spans, periods, strict=True)):
        keep = min(1.0, max(0.0, sol[th(t)])) if period.cuttable > _EPS else 1.0
        flexible: dict[str, int] = {}
        total = 0
        for expense in flexible_expenses:
            occurrences = len(expense.occurrences(lo, hi))
            if occurrences == 0:
                continue
            kept_baht = math.floor(keep * (expense.amount - expense.floor) / SATANG_PER_THB + _EPS)
            amount = min(expense.amount, expense.floor + kept_baht * SATANG_PER_THB)
            flexible[expense.id] = amount
            total += amount * occurrences
        months.append(
            PlanMonth(
                month=f"{lo:%Y-%m}",
                period_start=lo,
                transfer_date=hi,
                contributions=contributions[t],
                flexible=flexible,
                flexible_total=total,
                flexible_max=round(period.flex_max[-1] * SATANG_PER_THB) if period.days else 0,
                closing_unallocated=0,
            )
        )

    def projection_month(series: list[int], need: int) -> str | None:
        if need == 0:
            return months[0].month
        return next((months[t].month for t, value in enumerate(series) if value >= need), None)

    goal_projections = []
    reserve_projection = None
    for envelope, need, _, _, ramp in targets:
        series = cumulative_satang[envelope.id]
        need_satang = round(need * SATANG_PER_THB)
        if envelope.kind is EnvelopeKind.EMERGENCY:
            reserve_projection = ReserveProjection(
                target=state.reserve_target,
                saved_now=envelope.balance,
                projected_saved=envelope.balance + series[-1],
                reached_month=projection_month(series, need_satang),
            )
            continue
        goal = goals[envelope.goal_id]
        if goal.deadline is None:
            on_track, shortfall = None, 0
        else:
            by_deadline = series[ramp - 1] if ramp >= 1 else 0
            shortfall = max(0, need_satang - by_deadline)
            on_track = shortfall == 0
        goal_projections.append(
            GoalProjection(
                goal_id=goal.id,
                name=goal.name,
                target=goal.target,
                saved_now=envelope.balance,
                projected_saved=envelope.balance + series[-1],
                completion_month=projection_month(series, need_satang),
                deadline=goal.deadline,
                on_track=on_track,
                shortfall_at_deadline=shortfall,
            )
        )

    plan = Plan(
        strategy=strategy.name,
        label=strategy.label,
        start=state.as_of,
        horizon_months=horizon_months,
        state_hash=state_fingerprint(state),
        months=tuple(months),
        goals=tuple(goal_projections),
        reserve=reserve_projection,
    )

    # Fill in closing balances from the authoritative daily forecast.
    forecast = forecast_cash_flow(apply_plan(state, plan), plan.horizon_days)
    closing = {day.on: day.unallocated for day in forecast.days}
    plan = plan.model_copy(
        update={
            "months": tuple(
                m.model_copy(update={"closing_unallocated": closing[m.transfer_date]})
                for m in plan.months
            )
        }
    )

    validation = validate_plan(state, plan)
    if not validation.ok:
        raise PlanValidationError(
            f"{strategy.name} plan failed validation: {'; '.join(validation.violations)}"
        )
    return plan


def _explain_identical(first: Plan, second: Plan, floors: dict[str, int]) -> IdenticalPlans:
    funded = [g.goal_id for g in first.goals if g.completion_month is not None]
    if first.reserve is not None and first.reserve.reached_month is not None:
        funded.insert(0, "emergency reserve")
    return IdenticalPlans(
        strategies=(first.label, second.label),
        months_cash_fully_allocated=sum(m.closing_unallocated == 0 for m in first.months),
        months_flexible_at_floor=sum(
            m.flexible_total < m.flexible_max
            and all(amount == floors[expense_id] for expense_id, amount in m.flexible.items())
            for m in first.months
        ),
        envelopes_fully_funded=tuple(funded),
        horizon_months=first.horizon_months,
    )


def generate_plans(
    state: FinancialState,
    strategies: dict[str, StrategyConfig] | None = None,
    horizon_months: int = 12,
) -> PlanningResult:
    """Plans for every strategy, each validated, plus notes on identical outcomes."""
    strategies = strategies or load_strategies()
    plans = [optimize_plan(state, config, horizon_months) for config in strategies.values()]

    spans = _periods(state.as_of, horizon_months)
    horizon_days = (spans[-1][1] - state.as_of).days + 1

    if any(plan is None for plan in plans):
        report = check_feasibility(state.model_copy(update={"transfers": ()}), horizon_days)
        status = (
            PlanningStatus.ESSENTIAL_SHORTFALL
            if report.essential_shortfall > 0
            else PlanningStatus.REQUIRES_RESERVE_DRAWDOWN
        )
        return PlanningResult(status=status, feasibility=report)

    floors = {e.id: e.floor for e in state.expenses if e.category is ExpenseCategory.FLEXIBLE}
    identical = tuple(
        _explain_identical(first, second, floors)
        for i, first in enumerate(plans)
        for second in plans[i + 1:]
        if first.same_allocations(second)
    )
    return PlanningResult(
        status=PlanningStatus.OK,
        plans=tuple(plans),
        feasibility=check_feasibility(apply_plan(state, plans[0]), horizon_days),
        identical=identical,
    )
