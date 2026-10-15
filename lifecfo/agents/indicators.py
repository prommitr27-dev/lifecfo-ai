"""Goal feasibility and risk indicators, as plain data for the agent tools.

Both are calculated before and independently of any plan. Amounts are THB.
"""

from datetime import timedelta
from pathlib import Path
from typing import Any

import yaml

from lifecfo.agents.views import _iso, _month_ends, baht
from lifecfo.cashflow import forecast_cash_flow
from lifecfo.cashflow.forecast import EventKind
from lifecfo.cashflow.position import assess_position
from lifecfo.domain.models import FinancialState
from lifecfo.optimization.optimizer import horizon_days
from lifecfo.optimization.reasons import max_saving_by

RISK_THRESHOLDS = Path(__file__).resolve().parents[2] / "config" / "risk_thresholds.yaml"


def goal_feasibility_data(state: FinancialState) -> dict[str, Any]:
    """Each goal checked on its own against its deadline.

    "Required per month" spreads what is still needed evenly over the month-end
    sweeps up to the deadline. "Most possible" is the ceiling if every spare baht
    went to that goal alone (essentials, debt minimums, and the flexible minimum
    paid; nothing else saved). Neither is a plan: competing goals and the reserve
    are shared out by the optimizer.
    """
    position = assess_position(state, horizon_days(state.as_of, 12))
    free = position.budget.original_surplus
    saved = {e.goal_id: e.balance for e in state.envelopes if e.goal_id}
    goals, total_required = [], 0
    for goal in sorted(state.goals, key=lambda g: g.priority):
        have = saved.get(goal.id, 0)
        remaining = max(0, goal.target - have)
        entry: dict[str, Any] = {
            "goal": goal.name, "priority": goal.priority, "flexible": goal.flexible,
            "target": baht(goal.target), "saved": baht(have), "remaining": baht(remaining),
            "deadline": _iso(goal.deadline),
        }
        if remaining == 0:
            entry["status"] = "ALREADY_FUNDED"
        elif goal.deadline is None:
            entry["status"] = "NO_DEADLINE"
            entry["months_if_all_free_cash_went_to_it"] = (
                -(-remaining // free) if free > 0 else None)
            entry["note"] = ("No deadline was given, so none is assumed. The month count is a "
                             "what-if for this goal alone, not a projected date.")
        else:
            sweeps = len(_month_ends(state.as_of, goal.deadline))
            ceiling = have + max_saving_by(state, goal.deadline)
            required = -(-remaining // sweeps) if sweeps else remaining
            total_required += required if sweeps else 0
            entry.update({
                "month_end_sweeps_before_deadline": sweeps,
                "required_per_month": baht(required),
                "most_possible_by_deadline": baht(ceiling),
            })
            if ceiling < goal.target:
                entry["status"] = "NOT_REACHABLE_ON_TIME"
                entry["shortfall_at_best"] = baht(goal.target - ceiling)
                entry["note"] = (
                    "Even with every spare baht the target cannot be met by the deadline. "
                    + ("The goal is flexible, so a later date may be proposed for approval."
                       if goal.flexible else "The deadline is fixed: this is a deadline risk."))
            elif required <= free:
                entry["status"] = "REACHABLE_ON_ITS_OWN"
            else:
                entry["status"] = "REACHABLE_ONLY_WITH_CUTS"
                entry["note"] = ("It needs more each month than the original budget leaves "
                                 "free; it fits only with flexible cuts or other goals waiting.")
        goals.append(entry)
    return {
        "as_of": state.as_of.isoformat(),
        "free_cash_per_month_under_original_budget": baht(free),
        "required_per_month_by_all_deadline_goals": baht(total_required),
        "reserve_gap": baht(position.reserve.gap),
        "goals": goals,
        "note": "Each goal is checked on its own. Together they compete for the same free "
                "cash and the reserve; the plans show how the optimizer shares it.",
    }


def _rate(value: float, rule: dict[str, Any] | None) -> str:
    """Apply a threshold rule from the risk lead; never invent one."""
    if not rule or all(limit is None for limit in rule.values()):
        return "NO_THRESHOLD_SET"
    for label, limit in rule.items():
        if limit is None:
            continue
        if label.endswith("_below") and value < limit:
            return label.removesuffix("_below").upper()
    for label, limit in rule.items():
        if limit is not None and label.endswith("_at_or_above") and value >= limit:
            return label.removesuffix("_at_or_above").upper()
    return "WITHIN_THRESHOLDS"


def risk_data(state: FinancialState, months: int,
              thresholds: dict[str, Any] | None = None) -> dict[str, Any]:
    """The brief's risk indicators for the current plan and position."""
    rules = thresholds if thresholds is not None else (
        yaml.safe_load(RISK_THRESHOLDS.read_text(encoding="utf-8")) or {})
    days = horizon_days(state.as_of, months)
    forecast = forecast_cash_flow(state, days)
    position = assess_position(state, days)

    first = forecast.first_shortfall_on
    days_until = (first - state.as_of).days if first else None
    window_end = state.as_of + timedelta(days=29)
    due = sum(e.amount for d in forecast.days if d.on <= window_end for e in d.events
              if e.kind in (EventKind.ESSENTIAL_EXPENSE, EventKind.DEBT_MINIMUM))
    coverage = (round((position.cash.accessible + position.income_next_month) / due, 2)
                if due else None)
    monthly_need = state.monthly_essentials + state.monthly_debt_minimums
    reserve_months = (round(position.cash.eligible_reserve / monthly_need, 2)
                      if monthly_need else None)
    at_risk = [g["goal"] for g in goal_feasibility_data(state)["goals"]
               if g["status"] == "NOT_REACHABLE_ON_TIME"]

    return {
        "as_of": state.as_of.isoformat(),
        "horizon_days": days,
        "indicators": [
            {"name": "Days until projected cash shortfall (current plan)",
             "value": days_until,
             "rating": (_rate(days_until, rules.get("days_until_shortfall"))
                        if days_until is not None else "NO_SHORTFALL_IN_HORIZON")},
            {"name": "Lowest projected unallocated cash", "value": baht(forecast.min_unallocated),
             "unit": "THB", "on": forecast.min_unallocated_on.isoformat(),
             "rating": "INFORMATION"},
            {"name": "Essential bill coverage over the next 30 days: (accessible cash + "
                     "income) / (essentials + debt minimums due)",
             "value": coverage,
             "rating": (_rate(coverage, rules.get("essential_bill_coverage_ratio"))
                        if coverage is not None else "NOTHING_DUE")},
            {"name": "Emergency reserve, in months of essentials and debt minimums",
             "value": reserve_months,
             "rating": (_rate(reserve_months, rules.get("emergency_reserve_months_of_essentials"))
                        if reserve_months is not None else "NO_ESSENTIALS")},
            {"name": "Income volatility", "value": None, "rating": "NOT_MEASURABLE",
             "note": "Only fixed scheduled income is recorded; there is no income history."},
            {"name": "Goals that cannot be met on time even on their own",
             "value": len(at_risk), "goals": at_risk,
             "rating": "AT_RISK" if at_risk else "NONE"},
        ],
        "note": "Ratings come from the thresholds the risk lead sets in "
                "config/risk_thresholds.yaml. Where none is set yet, the value is shown "
                "without a rating rather than with an invented one.",
    }
