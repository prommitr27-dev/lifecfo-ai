"""Monthly linear program that allocates free cash across envelopes.

One LP serves all three strategies; only the parameters differ. The model and
its assumptions are described in docs/financial_model/FINANCIAL_MODEL.md.

Decision variables, per month t of the horizon:
  x[e,t]  contribution to envelope e (emergency reserve or a goal), swept on
          the last day of the month
  th[t]   share of the cuttable part of flexible spending that is kept, 0..1
  s[e,t]  how far envelope e is behind its ramp at the end of month t
  z[t]    extra debt repayment (cash), only from money left after every ramp
  b[t]    how far accessible cash is below the user's buffer after the sweep

Hard constraints:
  - unallocated cash is never negative on any day that has a scheduled event
    (essentials and debt minimums are always paid in full)
  - an envelope never receives more than it still needs
  - extra repayments never exceed what is owed

The buffer (rules D3) is a heavily weighted soft constraint: when it cannot be
met, the shortfall is reported per month instead of the plan being withheld.

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
from lifecfo.cashflow.position import ShortfallKind, assess_position
from lifecfo.debt.schedule import allocate_extra, payoff_order
from lifecfo.domain.models import (
    EnvelopeKind,
    ExpenseCategory,
    FinancialState,
)
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


def horizon_days(start: date, months: int) -> int:
    """Days from `start` to the end of the last month of a `months`-month plan."""
    return (_periods(start, months)[-1][1] - start).days + 1


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
    """Best plan for one strategy, or None when the flexible minimum cannot be funded.

    Existing `state.transfers` and `state.debt_payments` are ignored: the plan
    replaces them. Nothing here changes the user's preferences: deadlines, targets,
    priorities, the buffer, and the flexible budget are inputs, and any flexible
    reduction in the result is a proposal that needs approval.
    """
    if horizon_months < 1:
        raise ValueError("horizon_months must be at least 1")

    base = state.model_copy(update={"transfers": (), "debt_payments": ()})
    spans = _periods(base.as_of, horizon_months)
    periods = _build_periods(base, spans)
    n_months = horizon_months
    opening = base.unallocated.balance / SATANG_PER_THB
    goals = {g.id: g for g in base.goals}
    reserve_envelope = base.emergency
    reserve_now = (reserve_envelope.balance if reserve_envelope else 0) / SATANG_PER_THB
    buffer = base.buffer_target

    # Envelopes that can receive money: (envelope, remaining need in baht, ramp weight,
    # surplus bonus, months to reach the target).
    targets = []
    for envelope in base.envelopes:
        if envelope.kind is EnvelopeKind.EMERGENCY:
            need = max(0, base.emergency_target - envelope.balance)
            targets.append((envelope, need / SATANG_PER_THB, strategy.reserve_weight,
                            strategy.surplus_reserve, strategy.reserve_ramp_months))
        elif envelope.kind is EnvelopeKind.GOAL:
            goal = goals[envelope.goal_id]
            factor = strategy.priority_factor(goal.priority)
            need = max(0, goal.target - envelope.balance)
            # Rules D9: a goal without a deadline has no ramp. It only takes money left
            # after time-bound goals, so its allocation does not depend on the horizon.
            weight = strategy.goal_weight * factor if goal.deadline else 0.0
            targets.append((envelope, need / SATANG_PER_THB, weight,
                            strategy.surplus_goal * factor, _months_until(goal.deadline, spans)))
    n_env = len(targets)
    goal_rows = [e for e, target in enumerate(targets)
                 if target[0].kind is EnvelopeKind.GOAL]

    order = payoff_order(base)
    debt_room = sum(d.balance for d in base.debts if d.id in order) / SATANG_PER_THB
    use_debt = strategy.surplus_debt > 0 and debt_room > 0

    # Variable layout.
    index = 0

    def block(size: int) -> int:
        nonlocal index
        start, index = index, index + size
        return start

    x0 = block(n_env * n_months)  # contributions
    th0 = block(n_months)  # share of the cuttable flexible spending kept
    s0 = block(n_env * n_months)  # behind-the-ramp shortfall
    z0 = block(n_months) if use_debt else -1  # extra debt repayment (cash)
    b0 = block(n_months) if buffer is not None else -1  # buffer shortfall

    def x(e: int, t: int) -> int:
        return x0 + e * n_months + t

    def th(t: int) -> int:
        return th0 + t

    def s(e: int, t: int) -> int:
        return s0 + e * n_months + t

    n_vars = index
    rows: list[np.ndarray] = []
    rhs: list[float] = []

    # Liquidity: unallocated cash stays non-negative on every event day and after each
    # month-end sweep. Essentials and debt minimums are constants: always paid in full.
    carried = opening  # cash carried in if nothing is allocated and flexible is at floor
    for t, period in enumerate(periods):
        before = np.zeros(n_vars)
        for prev in range(t):
            before[th(prev)] = periods[prev].cuttable
            for e in range(n_env):
                before[x(e, prev)] = 1.0
            if use_debt:
                before[z0 + prev] = 1.0
        for i in range(len(period.days)):
            row = before.copy()
            row[th(t)] = period.flex_max[i] - period.flex_min[i]
            rows.append(row)
            rhs.append(carried + period.fixed[i] - period.flex_min[i])
        row = before.copy()
        row[th(t)] = period.cuttable
        for e in range(n_env):
            row[x(e, t)] = 1.0
        if use_debt:
            row[z0 + t] = 1.0
        rows.append(row)
        rhs.append(carried + period.net - period.fmin)
        carried += period.net - period.fmin

        if buffer is not None:
            # Rules D3: accessible cash (unallocated + reserve) after the sweep should not
            # fall below the buffer. Moving money into the reserve keeps it accessible;
            # goal contributions, extra repayments, and flexible spending do not.
            row = np.zeros(n_vars)
            for prev in range(t + 1):
                row[th(prev)] = periods[prev].cuttable
                for e in goal_rows:
                    row[x(e, prev)] = 1.0
                if use_debt:
                    row[z0 + prev] = 1.0
            row[b0 + t] = -1.0
            rows.append(row)
            rhs.append(carried + reserve_now - buffer / SATANG_PER_THB)

    if min(rhs[i] for i in range(len(rhs))
           if not (buffer is not None and _is_buffer_row(rows[i], b0, n_months))) < -_EPS:
        return None  # even with no allocations and flexible at its floor, cash runs out

    for e, (_, need, _, _, ramp) in enumerate(targets):
        row = np.zeros(n_vars)  # envelope cap
        for t in range(n_months):
            row[x(e, t)] = 1.0
        rows.append(row)
        rhs.append(need)
        for t in range(n_months):  # s[e,t] >= required(t) - contributed so far
            required = need if ramp <= 0 else need * min(1.0, (t + 1) / ramp)
            row = np.zeros(n_vars)
            for prev in range(t + 1):
                row[x(e, prev)] = -1.0
            row[s(e, t)] = -1.0
            rows.append(row)
            rhs.append(-required)
    if use_debt:
        row = np.zeros(n_vars)
        row[z0:z0 + n_months] = 1.0
        rows.append(row)
        rhs.append(debt_room)

    cost = np.zeros(n_vars)
    for e, (_, _, weight, bonus, _) in enumerate(targets):
        for t in range(n_months):
            cost[s(e, t)] = weight
            # A baht saved in month t sits in the envelope for the rest of the horizon.
            cost[x(e, t)] = -strategy.surplus_bonus_scale * bonus * (n_months - t)
    for t, period in enumerate(periods):
        cost[th(t)] = -strategy.flexible_cut_weight * period.cuttable
        if use_debt:
            cost[z0 + t] = -strategy.surplus_bonus_scale * strategy.surplus_debt * (n_months - t)
        if buffer is not None:
            cost[b0 + t] = strategy.buffer_weight

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
        cumulative_satang[envelope.id] = _round_cumulative(
            [sol[x(e, t)] for t in range(n_months)], need, contributions, envelope.id)

    flexible_expenses = [e for e in base.expenses if e.category is ExpenseCategory.FLEXIBLE]
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

    if use_debt:
        cash_by_month: list[dict[str, int]] = [{} for _ in range(n_months)]
        _round_cumulative([sol[z0 + t] for t in range(n_months)], debt_room, cash_by_month,
                          "debt")
        months = _split_extra_repayments(base, months, [m.get("debt", 0) for m in cash_by_month],
                                         order)

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
                target=base.emergency_target,
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
                flexible=goal.flexible,
                contributed_in_horizon=series[-1],
                average_monthly_contribution=series[-1] // n_months,
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
        buffer_target=buffer,
        debt_order=tuple(order) if use_debt else (),
    )

    # Closing balances and buffer checks come from the authoritative daily forecast.
    forecast = forecast_cash_flow(apply_plan(state, plan), plan.horizon_days)
    closing = {day.on: day.unallocated for day in forecast.days}
    reserve_id = reserve_envelope.id if reserve_envelope else None
    reserve_series = cumulative_satang.get(reserve_id, [0] * n_months) if reserve_id else None
    updated = []
    for t, month in enumerate(plan.months):
        unallocated = closing[month.transfer_date]
        shortfall = 0
        if buffer is not None:
            reserve = (reserve_envelope.balance + reserve_series[t]) if reserve_envelope else 0
            shortfall = max(0, buffer - (unallocated + reserve))
        updated.append(month.model_copy(update={"closing_unallocated": unallocated,
                                                "buffer_shortfall": shortfall}))
    plan = plan.model_copy(update={"months": tuple(updated)})

    validation = validate_plan(state, plan)
    if not validation.ok:
        raise PlanValidationError(
            f"{strategy.name} plan failed validation: {'; '.join(validation.violations)}"
        )
    return plan


def _is_buffer_row(row: np.ndarray, b0: int, n_months: int) -> bool:
    return b0 >= 0 and bool(np.any(row[b0:b0 + n_months] != 0))


def _round_cumulative(values: list[float], cap: float, out: list[dict[str, int]],
                      key: str) -> list[int]:
    """Round a monthly series down on its running total, in whole baht, within `cap`.

    Rounding the running total (not each month) keeps the rounding error below one
    baht overall and can only leave more cash on hand than the LP solution.
    """
    cap_satang = round(cap * SATANG_PER_THB)
    running, previous, series = 0.0, 0, []
    for t, value in enumerate(values):
        running += max(0.0, value)
        if running >= cap - _EPS:
            rounded = cap_satang
        else:
            rounded = math.floor(running + _EPS) * SATANG_PER_THB
        rounded = max(previous, min(rounded, cap_satang))
        if rounded > previous:
            out[t][key] = rounded - previous
        previous = rounded
        series.append(rounded)
    return series


def _split_extra_repayments(
    state: FinancialState, months: list[PlanMonth], cash: list[int], order: list[str]
) -> list[PlanMonth]:
    """Record each month's extra-repayment cash per debt, in payoff order."""
    payments = allocate_extra(
        state, [(m.transfer_date, amount) for m, amount in zip(months, cash, strict=True)],
        order)
    by_month: dict[date, dict[str, int]] = {}
    for payment in payments:
        assert payment.on_date is not None
        by_month.setdefault(payment.on_date, {})[payment.debt_id] = payment.amount
    return [m.model_copy(update={"extra_debt": by_month.get(m.transfer_date, {})})
            for m in months]


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
    """The user's position first, then a validated plan per strategy when one exists."""
    strategies = strategies or load_strategies()
    days = horizon_days(state.as_of, horizon_months)
    position = assess_position(state, days)
    bare = state.model_copy(update={"transfers": (), "debt_payments": ()})

    status = None
    if position.has(ShortfallKind.CASH_FLOW_SHORTFALL):
        status = PlanningStatus.ESSENTIAL_SHORTFALL
    elif position.has(ShortfallKind.RESERVE_WITHDRAWAL_NEEDED):
        status = PlanningStatus.REQUIRES_RESERVE_DRAWDOWN
    elif position.adjusted_deficit > 0:
        status = PlanningStatus.FLEXIBLE_SPENDING_CONSTRAINT
    if status is not None:
        return PlanningResult(status=status, feasibility=check_feasibility(bare, days),
                              position=position)

    plans = [optimize_plan(state, config, horizon_months) for config in strategies.values()]
    if any(plan is None for plan in plans):  # agrees with adjusted_deficit; kept as a guard
        return PlanningResult(status=PlanningStatus.FLEXIBLE_SPENDING_CONSTRAINT,
                              feasibility=check_feasibility(bare, days), position=position)

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
        feasibility=check_feasibility(apply_plan(state, plans[0]), days),
        identical=identical,
        position=position,
    )
