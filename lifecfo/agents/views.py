"""Calculation results turned into plain data for tools and explanations.

Every figure here comes from the engines. Amounts are THB (not satang). The
explanation layer (`explain.py`) only words these values; it never computes.
"""

from datetime import date, timedelta
from typing import Any

from lifecfo.cashflow import check_feasibility, forecast_cash_flow, monthly_summary
from lifecfo.cashflow.position import PositionReport, ShortfallKind, assess_position
from lifecfo.debt.schedule import allocate_extra, interest_basis, payoff_order, schedule_debts
from lifecfo.domain.models import (
    DebtStrategy,
    Expense,
    ExpenseCategory,
    FinancialState,
    Frequency,
)
from lifecfo.domain.money import SATANG_PER_THB
from lifecfo.optimization import Plan, PlanningResult, PlanningStatus, generate_plans
from lifecfo.optimization.optimizer import horizon_days
from lifecfo.optimization.reasons import deferral_reasons
from lifecfo.optimization.strategies import load_strategies


def baht(satang: int) -> int | float:
    whole, rest = divmod(satang, SATANG_PER_THB)
    return whole if rest == 0 else round(satang / SATANG_PER_THB, 2)


def _iso(day: date | None) -> str | None:
    return day.isoformat() if day else None


# --- position (rules D1 to D4, section 3.1) ------------------------------------------


def position_data(report: PositionReport) -> dict[str, Any]:
    budget = report.budget
    return {
        "as_of": report.as_of.isoformat(),
        "horizon_days": report.horizon_days,
        "monthly_budget": {
            "income": baht(budget.income),
            "essentials": baht(budget.essentials),
            "debt_minimums": baht(budget.debt_minimums),
            "flexible_budget": baht(budget.flexible_budget),
            "flexible_minimum_permitted": baht(budget.flexible_minimum),
            "reduction_permitted": budget.reduction_allowed,
            "surplus_under_original_budget": baht(budget.original_surplus),
            "surplus_if_flexible_at_minimum": baht(budget.adjusted_surplus),
        },
        "current_cash": {
            "unallocated": baht(report.cash.unallocated),
            "eligible_emergency_reserve": baht(report.cash.eligible_reserve),
            "committed_to_goals": baht(report.cash.committed_to_goals),
            "accessible": baht(report.cash.accessible),
            "total": baht(report.cash.total),
        },
        "coming_month": {
            "until": report.month_end.isoformat(),
            "income": baht(report.income_next_month),
            "obligations_under_original_budget": baht(report.obligations_next_month),
            "uncommitted_funds": baht(report.uncommitted_next_month),
        },
        "emergency_reserve": {
            "target": baht(report.reserve.target),
            "basis": ("custom amount set by the user" if report.reserve.custom else
                      f"{report.reserve.months:g} months x (essentials + debt minimums)"),
            "eligible_balance": baht(report.reserve.eligible),
            "gap": baht(report.reserve.gap),
        },
        "cash_buffer": {
            "configured": report.buffer.configured,
            "target": baht(report.buffer.target) if report.buffer.target is not None else None,
            "recommended_if_not_configured": baht(report.buffer.recommended),
            "accessible_now": baht(report.buffer.accessible_now),
            "shortfall_now": baht(report.buffer.shortfall_now),
            "note": "The buffer and the emergency reserve are checked against the same "
                    "accessible cash and are not added together.",
        },
        "original_budget_deficit": baht(report.original_deficit),
        "original_budget_deficit_from": _iso(report.original_deficit_on),
        "deficit_if_flexible_at_minimum": baht(report.adjusted_deficit),
        "shortfalls": [
            {"kind": s.kind.value, "amount": baht(s.amount) if s.amount is not None else None,
             "from": _iso(s.on), "detail": s.detail}
            for s in report.shortfalls
        ],
    }


# --- plans ---------------------------------------------------------------------------


def _goal_kinds(goal) -> list[str]:
    kinds = []
    if goal.on_track is False:
        kinds.append(ShortfallKind.FLEXIBLE_GOAL_DELAY.value if goal.flexible
                     else ShortfallKind.DEADLINE_RISK.value)
        if goal.completion_month is None:
            kinds.append(ShortfallKind.SAVINGS_GOAL_SHORTFALL.value)
    return kinds


def plan_data(plan: Plan, state: FinancialState) -> dict[str, Any]:
    first = plan.months[0]
    reasons = deferral_reasons(state, plan)
    goals = []
    for g in plan.goals:
        envelope_id = next(e.id for e in state.envelopes if e.goal_id == g.goal_id)
        unfinished = [m for m in plan.months
                      if g.completion_month is None or m.month <= g.completion_month]
        zero_months = [m.month for m in unfinished if not m.contributions.get(envelope_id)]
        entry = {
            "name": g.name,
            "priority": next(x.priority for x in state.goals if x.id == g.goal_id),
            "flexible": g.flexible,
            "deadline": _iso(g.deadline),
            "completion_month": g.completion_month,
            "completion_is_projection": True,
            "on_track": g.on_track,
            "shortfall_at_deadline": baht(g.shortfall_at_deadline),
            "shortfall_kinds": _goal_kinds(g),
            "why_late": reasons.get(g.goal_id),
            "saved_in_horizon": baht(g.contributed_in_horizon),
            "average_per_month": baht(g.average_monthly_contribution),
            "remaining_after_horizon": baht(max(0, g.target - g.projected_saved)),
            "months_with_zero_allocation": zero_months,
        }
        if zero_months:
            buffer_months = set(plan.months_below_buffer)
            held = [m for m in zero_months if m in buffer_months]
            why = []
            if held:
                why.append(f"accessible cash is below your cash buffer in {', '.join(held)}")
            if len(held) < len(zero_months):
                why.append("in the other months money goes first to needs this strategy "
                           "weights higher (the reserve schedule or higher-priority goals)")
            listed = ", ".join(zero_months[:4]) + (", ..." if len(zero_months) > 4 else "")
            entry["zero_allocation_note"] = (
                f"{g.name} receives nothing in {len(zero_months)} month(s) ({listed}) "
                f"because {'; '.join(why)}. The goal stays in the plan; a month with zero is "
                "not a cancellation."
            )
        if g.deadline is None:
            entry["no_deadline_note"] = (
                "No deadline was given, so none is assumed. The completion month, if shown, "
                "is a projection from this plan, not a guarantee.")
        goals.append(entry)

    reduced = [m for m in plan.months if m.flexible_total < m.flexible_max]
    data: dict[str, Any] = {
        "strategy": plan.label,
        "status": "PROPOSED_NOT_APPROVED",
        "emergency_fund_target_reached": plan.reserve.reached_month if plan.reserve else None,
        "emergency_fund_projected": baht(plan.reserve.projected_saved) if plan.reserve else None,
        "goals": goals,
        "first_month": first.month,
        "first_month_contributions": {k: baht(v) for k, v in first.contributions.items()},
        "first_month_extra_debt_repayment": {k: baht(v) for k, v in first.extra_debt.items()},
        "flexible_spending": {
            "original_budget_first_month": baht(first.flexible_max),
            "proposed_first_month": baht(first.flexible_total),
            "reduction_first_month": baht(first.flexible_max - first.flexible_total),
            "reduction_percent_first_month": (
                round(100 * (first.flexible_max - first.flexible_total) / first.flexible_max, 1)
                if first.flexible_max else 0),
            "months_with_a_proposed_reduction": len(reduced),
            "note": "A reduction is a proposal within the user's permitted range and applies "
                    "only if the user approves the plan.",
        },
        "flexible_spending_over_horizon": baht(sum(m.flexible_total for m in plan.months)),
        "cash_buffer": {
            "target": baht(plan.buffer_target) if plan.buffer_target is not None else None,
            "months_below_buffer": list(plan.months_below_buffer),
            "largest_shortfall": baht(max((m.buffer_shortfall for m in plan.months),
                                          default=0)),
        },
        "extra_debt_repayment_over_horizon": baht(
            sum(sum(m.extra_debt.values()) for m in plan.months)),
        "validated": True,
    }
    return data


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


def flexible_goal_alternatives(state: FinancialState, result: PlanningResult,
                               horizon_months: int) -> list[dict[str, Any]]:
    """Rules D7: for a flexible goal that misses its deadline, show a later-date option.

    The option is computed with the Balanced strategy and the goal's deadline set aside;
    nothing is changed. Non-flexible goals get no such option.
    """
    if result.status is not PlanningStatus.OK:
        return []
    late = {g.goal_id for p in result.plans for g in p.goals
            if g.flexible and g.on_track is False}
    if not late:
        return []
    config = {"BALANCED": load_strategies()["BALANCED"]}
    baseline = next((p for p in result.plans if p.strategy == "BALANCED"), result.plans[0])
    options = []
    for goal_id in sorted(late):
        goal = next(g for g in state.goals if g.id == goal_id)
        relaxed = state.model_copy(update={"goals": tuple(
            g.model_copy(update={"deadline": None}) if g.id == goal_id else g
            for g in state.goals)})
        alt = generate_plans(relaxed, config, horizon_months)
        if alt.status is not PlanningStatus.OK:
            continue
        plan = alt.plans[0]
        projected = next(g for g in plan.goals if g.goal_id == goal_id)
        effects = []
        for before, after in zip(baseline.goals, plan.goals, strict=True):
            if before.goal_id == goal_id:
                continue
            if before.completion_month != after.completion_month or (
                    before.shortfall_at_deadline != after.shortfall_at_deadline):
                effects.append(
                    f"{after.name}: completes {after.completion_month or 'not within the horizon'}"
                    f" (Balanced now: {before.completion_month or 'not within the horizon'})"
                    + (f", shortfall at its deadline {baht(after.shortfall_at_deadline):,} THB"
                       if after.on_track is False else ""))
        if baseline.reserve and plan.reserve and (
                baseline.reserve.reached_month != plan.reserve.reached_month):
            effects.append(f"Emergency fund target reached "
                           f"{plan.reserve.reached_month or 'not within the horizon'} "
                           f"(Balanced now: {baseline.reserve.reached_month or 'not within'}).")
        options.append({
            "goal": goal.name,
            "current_deadline": _iso(goal.deadline),
            "projected_completion_without_the_deadline": projected.completion_month,
            "effects_on_other_goals": effects or ["No change to other goals or the reserve."],
            "requires_approval": True,
            "note": f"{goal.name} is marked flexible, so a later date may be proposed. Its "
                    "deadline stays as it is unless you change it.",
        })
    return options


def planning_data(state: FinancialState, horizon_months: int) -> dict[str, Any]:
    result = generate_plans(state, horizon_months=horizon_months)
    data: dict[str, Any] = {
        "status": result.status.value,
        "horizon_months": horizon_months,
        "original_position": position_data(result.position) if result.position else None,
    }
    if result.status is PlanningStatus.OK:
        data["plans"] = [plan_data(plan, state) for plan in result.plans]
        data["tradeoffs"] = tradeoff_facts(result)
        data["alternatives"] = flexible_goal_alternatives(state, result, horizon_months)
    else:
        data["plans"] = []
        data["essential_shortfall"] = baht(result.feasibility.essential_shortfall)
        data["essential_shortfall_on"] = _iso(result.feasibility.essential_shortfall_on)
    return data


def feasibility_data(state: FinancialState, days: int) -> dict[str, Any]:
    forecast = forecast_cash_flow(state, days)
    report = check_feasibility(state, days, planned=forecast)
    return {
        "status": report.status.value,
        "horizon_days": days,
        "lowest_unallocated_cash": baht(report.min_unallocated),
        "lowest_unallocated_cash_on": report.min_unallocated_on.isoformat(),
        "first_shortfall_on": _iso(report.first_shortfall_on),
        "largest_shortfall": baht(report.max_shortfall),
        "needs_existing_savings": report.needs_reserves,
        "essential_shortfall": baht(report.essential_shortfall),
        "monthly": [
            {
                "month": m.month, "income": baht(m.income), "essential": baht(m.essential),
                "debt_minimum": baht(m.debt_minimum), "flexible": baht(m.flexible),
                "savings_transfers": baht(m.transfers),
                "extra_debt_repayment": baht(m.extra_debt),
                "closing_unallocated": baht(m.closing_unallocated),
            }
            for m in monthly_summary(forecast)
        ],
    }


# --- debts (rules D5, D6) ------------------------------------------------------------


def _debt_outcomes(state: FinancialState, start: date, end: date) -> list[dict[str, Any]]:
    out = []
    for debt_id, schedule in schedule_debts(state, start, end).items():
        debt = next(d for d in state.debts if d.id == debt_id)
        out.append({
            "debt": schedule.name,
            "rate": f"{debt.apr:.2%}" if debt.apr is not None else "unknown",
            "interest_basis": schedule.basis.value,
            "interest_in_period": (baht(schedule.total_interest)
                                   if schedule.total_interest is not None else None),
            "minimum_paid": baht(sum(p.minimum_paid for p in schedule.periods)),
            "extra_paid": baht(sum(p.extra_paid for p in schedule.periods)),
            "fees": baht(sum(p.fee for p in schedule.periods)),
            "paid_off_on": _iso(schedule.payoff_date),
            "balance_at_end": (baht(schedule.closing_balance)
                               if schedule.closing_balance is not None else None),
        })
    return out


def debt_comparison(state: FinancialState, months: int,
                    extra_per_month: int | None) -> dict[str, Any]:
    """Avalanche, Snowball, and the user's own order over the same period and cash."""
    if not state.debts:
        return {"error": "NO_DEBTS", "detail": "No debts are recorded."}
    start = state.as_of
    end = start + timedelta(days=horizon_days(start, months) - 1)
    base = state.model_copy(update={"debt_payments": ()})

    source = "amount given by the user"
    if extra_per_month is None:
        result = generate_plans(state, horizon_months=months)
        balanced = next((p for p in result.plans if p.strategy == "BALANCED"), None)
        extra_per_month = sum(balanced.months[0].extra_debt.values()) if balanced else 0
        source = ("first-month extra repayment in the Balanced plan, which only uses money "
                  "left after essentials, debt minimums, the flexible budget, the buffer, "
                  "and the reserve and goal schedules")

    cash = ([(on, extra_per_month) for on in _month_ends(start, end)]
            if extra_per_month > 0 else [])

    strategies: dict[str, list[str]] = {
        "AVALANCHE": payoff_order(base, DebtStrategy.AVALANCHE),
        "SNOWBALL": payoff_order(base, DebtStrategy.SNOWBALL),
    }
    if state.debt_order:
        strategies["YOUR_ORDER"] = payoff_order(base)
    names = {d.id: d.name for d in base.debts}

    comparisons = []
    for label, order in strategies.items():
        payments = allocate_extra(base, cash, order) if cash else []
        scenario = base.model_copy(update={"debt_payments": tuple(payments)})
        outcomes = _debt_outcomes(scenario, start, end)
        known = [o["interest_in_period"] for o in outcomes if o["interest_in_period"] is not None]
        comparisons.append({
            "strategy": label,
            "order": [names[d] for d in order],
            "debts": outcomes,
            "total_interest_where_calculable": round(sum(known), 2),
            "interest_incomplete": len(known) < len(outcomes),
        })

    notes = []
    for debt in base.debts:
        basis, details = interest_basis(debt)
        notes += [f"{debt.name} ({basis.value}): {text}" for text in details]
        if not debt.extra_payment_allowed:
            notes.append(f"{debt.name}: extra repayment is not permitted, so it only gets "
                         "its minimum.")
        if debt.prepayment_fee_rate:
            notes.append(f"{debt.name}: a prepayment fee of {debt.prepayment_fee_rate:.2%} "
                         "applies to extra repayments and is paid from the same cash.")
    if any(c["interest_incomplete"] for c in comparisons):
        notes.append("At least one rate is unknown, so total interest leaves that debt out "
                     "and the strategies cannot be fully compared on cost.")
    facts = []
    if len(comparisons) >= 2:
        a, s = comparisons[0], comparisons[1]
        diff = round(s["total_interest_where_calculable"]
                     - a["total_interest_where_calculable"], 2)
        scope = (" on the debts whose interest can be calculated" if a["interest_incomplete"]
                 else "")
        if diff > 0:
            facts.append(f"Avalanche costs {diff:,} THB less interest than Snowball over "
                         f"{months} months{scope}.")
        elif diff < 0:
            facts.append(f"Snowball costs {-diff:,} THB less interest than Avalanche over "
                         f"{months} months{scope}.")
        else:
            facts.append(f"Both orders cost the same interest over {months} months{scope}.")
    for comparison in comparisons:
        first_paid = sorted((o["paid_off_on"], o["debt"]) for o in comparison["debts"]
                            if o["paid_off_on"])
        if first_paid:
            facts.append(f"{comparison['strategy']}: first debt paid off is "
                         f"{first_paid[0][1]} on {first_paid[0][0]}.")
    return {
        "period": f"{start.isoformat()} to {end.isoformat()}",
        "months": months,
        "required_minimums_per_month": baht(state.monthly_debt_minimums),
        "extra_available_per_month": baht(extra_per_month),
        "extra_source": source,
        "selected_strategy": (state.debt_strategy.value if not state.debt_order
                              else "YOUR_ORDER"),
        "comparisons": comparisons,
        "facts": facts,
        "assumptions_and_limitations": notes,
        "status": "PROPOSAL_NOT_APPROVED",
        "note": "Extra repayments are applied only after the user approves a plan.",
    }


def _month_ends(start: date, end: date) -> list[date]:
    out, year, month = [], start.year, start.month
    while True:
        nxt = date(year + (month == 12), 1 if month == 12 else month + 1, 1)
        last = nxt - timedelta(days=1)
        if last > end:
            return out
        out.append(last)
        year, month = nxt.year, nxt.month


# --- unexpected expense and reserve withdrawal (rules D4, C9) -------------------------


def expense_scenario(state: FinancialState, amount: int, due: date,
                     months: int) -> dict[str, Any]:
    """An unexpected essential expense: liquidity, reserve withdrawal, and recovery."""
    shock = Expense(id="hypothetical-expense", name="Unexpected expense",
                    category=ExpenseCategory.ESSENTIAL, amount=amount,
                    frequency=Frequency.ONE_TIME, on_date=due)
    changed = state.model_copy(update={"expenses": (*state.expenses, shock)})
    days = horizon_days(state.as_of, months)

    # How much unallocated cash cannot cover, on the original budget with no savings,
    # until the next income arrives.
    original = forecast_cash_flow(changed, days, include_transfers=False)
    next_income = next((d.on for d in original.days if d.on > due and any(
        e.kind.value == "INCOME" for e in d.events)), due + timedelta(days=31))
    window = [d for d in original.days if due <= d.on < next_income] or [
        next(d for d in original.days if d.on >= due)]
    gap = max(0, -min(d.unallocated for d in window))

    reserve_env = state.emergency
    reserve_now = reserve_env.balance if reserve_env else 0
    withdrawal = min(gap, reserve_now)
    uncovered = gap - withdrawal
    target = state.emergency_target
    after = changed
    if withdrawal:
        after = changed.model_copy(update={"envelopes": tuple(
            e.model_copy(update={"balance": e.balance - withdrawal}) if e is reserve_env else
            e.model_copy(update={"balance": e.balance + withdrawal})
            if e.id == state.unallocated.id else e
            for e in changed.envelopes)})
    after_pos = assess_position(after, days)
    # Accessible cash (unallocated + reserve) at the end of the due date, original budget.
    without = forecast_cash_flow(state, days, include_transfers=False)
    on_due = (due - state.as_of).days
    accessible_without = without.days[on_due].unallocated + reserve_now
    accessible_with = original.days[on_due].unallocated + reserve_now

    return {
        "hypothetical": True,
        "note": "Simulated on a copy. Nothing was saved, withdrawn, or changed.",
        "expense_amount": baht(amount),
        "expense_due_on": due.isoformat(),
        "period_checked": f"{due.isoformat()} to {(next_income - timedelta(days=1)).isoformat()}",
        "not_covered_by_unallocated_cash": baht(gap),
        "reserve_withdrawal_needed": baht(withdrawal),
        "still_uncovered_after_reserve": baht(uncovered),
        "emergency_reserve": {
            "target": baht(target),
            "balance_before": baht(reserve_now),
            "balance_after_withdrawal": baht(reserve_now - withdrawal),
            "gap_before": baht(max(0, target - reserve_now)) if reserve_env else 0,
            "gap_after": baht(max(0, target - reserve_now + withdrawal)) if reserve_env else 0,
        },
        "accessible_cash": {
            "on": due.isoformat(),
            "without_expense": baht(accessible_without),
            "with_expense": baht(accessible_with),
        },
        "cash_buffer": {
            "target": (baht(state.buffer_target) if state.buffer_target is not None else None),
            "shortfall_after_expense": (
                baht(max(0, state.buffer_target - accessible_with))
                if state.buffer_target is not None else None),
        },
        "position_after": position_data(after_pos),
        "recovery_options": planning_data(after, months),
        "limitation": (
            "The withdrawal is modelled as taken on the profile date, before the expense. "
            "To act on it, the user confirms the expense and any withdrawal in the Sandbox "
            "view; these recovery plans are proposals that need approval."),
    }
