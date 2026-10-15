"""Plain-language reasons for plan outcomes, built only from plan and state data.

Nothing here decides anything; it reports where a plan sent the money so a
user can see why a goal is late.
"""

from datetime import date

from lifecfo.cashflow.forecast import forecast_cash_flow
from lifecfo.domain.models import EnvelopeKind, FinancialState
from lifecfo.domain.money import format_thb
from lifecfo.optimization.plan import Plan


def deferral_reasons(state: FinancialState, plan: Plan) -> dict[str, str]:
    """For each goal that misses its deadline under `plan`, why it does.

    Compares what the goal needed by its deadline with what the plan put into it
    before then, and names where the rest of the saved money went.
    """
    goals = {g.id: g for g in state.goals}
    envelope_of = {e.goal_id: e.id for e in state.envelopes if e.goal_id}
    names = {e.id: ("the emergency fund" if e.kind is EnvelopeKind.EMERGENCY
                    else goals[e.goal_id].name)
             for e in state.envelopes if e.kind is not EnvelopeKind.UNALLOCATED}

    reasons: dict[str, str] = {}
    for projection in plan.goals:
        if projection.on_track is not False or projection.deadline is None:
            continue
        goal = goals[projection.goal_id]
        envelope_id = envelope_of[goal.id]
        before = [m for m in plan.months if m.transfer_date <= projection.deadline]
        if not before:
            reasons[goal.id] = (
                f"{goal.name} is due on {projection.deadline}, before the first month-end "
                f"savings sweep of this plan, so it cannot receive anything in time. It needs "
                f"{format_thb(projection.target - projection.saved_now)} more."
            )
            continue
        received = sum(m.contributions.get(envelope_id, 0) for m in before)
        others: dict[str, int] = {}
        for month in before:
            for other, amount in month.contributions.items():
                if other != envelope_id:
                    others[other] = others.get(other, 0) + amount
        elsewhere = ", ".join(
            f"{format_thb(amount)} to {names[other]}"
            + (f" (priority {goals[_goal_of(state, other)].priority})"
               if _goal_of(state, other) else "")
            for other, amount in sorted(others.items(), key=lambda kv: -kv[1]) if amount
        ) or "nothing to other envelopes"
        ceiling = max_saving_by(state, projection.deadline) + projection.saved_now
        if ceiling < projection.target:
            reachability = (
                f" Even if every spare baht went to it, at most {format_thb(ceiling)} could "
                "be in place by the deadline, so the target is not reachable on time under "
                "the current income and essential costs.")
        else:
            reachability = (
                " The target is reachable on time only if other goals or the emergency "
                "fund wait.")
        reasons[goal.id] = (
            f"{goal.name} (priority {goal.priority}) needs "
            f"{format_thb(projection.target - projection.saved_now)} by {projection.deadline}. "
            f"In the {len(before)} month(s) before then, {plan.label} puts "
            f"{format_thb(received)} into it and sends {elsewhere}, so it is "
            f"{format_thb(projection.shortfall_at_deadline)} short at the deadline. "
            "The deadline itself is not changed." + reachability
        )
    return reasons


def max_saving_by(state: FinancialState, deadline: date) -> int:
    """Upper bound on new saving possible by `deadline`, in satang.

    Unallocated cash on the deadline when only essentials, debt minimums, and
    the flexible minimum are paid and nothing else is saved. It ignores bills
    due after the deadline, so it is a ceiling, not a recommendation.
    """
    if deadline < state.as_of:
        return 0
    days = (deadline - state.as_of).days + 1
    forecast = forecast_cash_flow(state, days, flexible_at_floor=True, include_transfers=False)
    return max(0, forecast.days[-1].unallocated)


def _goal_of(state: FinancialState, envelope_id: str) -> str | None:
    return next((e.goal_id for e in state.envelopes if e.id == envelope_id), None)
