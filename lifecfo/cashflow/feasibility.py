"""Classify whether the current plan can be funded day by day.

Three outcomes:
- FEASIBLE: unallocated cash never goes negative under the plan as written.
- PLAN_INFEASIBLE: the plan runs short, but essentials and debt minimums can
  still be paid from accessible cash (unallocated cash and the emergency fund)
  if flexible spending and savings stop. `needs_reserves` says whether the
  emergency fund would have to be used. Replanning can fix it.
- ESSENTIAL_SHORTFALL: even with no flexible spending, no savings, and the
  whole emergency fund used, essentials and debt minimums cannot be paid on
  time. Money already saved for goals is not counted: using it is the user's
  decision. Nothing is reduced or invented; the shortfall is reported as is.
"""

from datetime import date
from enum import StrEnum

from lifecfo.cashflow.forecast import Forecast, forecast_cash_flow
from lifecfo.domain.models import FinancialState, Frozen


class FeasibilityStatus(StrEnum):
    FEASIBLE = "FEASIBLE"
    PLAN_INFEASIBLE = "PLAN_INFEASIBLE"
    ESSENTIAL_SHORTFALL = "ESSENTIAL_SHORTFALL"


class FeasibilityReport(Frozen):
    status: FeasibilityStatus
    horizon_days: int
    # Under the plan as written:
    first_shortfall_on: date | None
    max_shortfall: int
    min_unallocated: int
    min_unallocated_on: date
    # Under the essentials-only view:
    needs_reserves: bool
    essential_shortfall: int
    essential_shortfall_on: date | None


def check_feasibility(
    state: FinancialState, horizon_days: int = 90, *, planned: Forecast | None = None
) -> FeasibilityReport:
    planned = planned or forecast_cash_flow(state, horizon_days)
    essentials = forecast_cash_flow(
        state, horizon_days, include_transfers=False, exclude_flexible=True
    )
    reserve = state.emergency.balance if state.emergency else 0

    essential_shortfall = max(0, -(essentials.min_unallocated + reserve))
    essential_shortfall_on = next(
        (day.on for day in essentials.days if day.unallocated + reserve < 0), None
    )

    if planned.max_shortfall == 0:
        status = FeasibilityStatus.FEASIBLE
    elif essential_shortfall == 0:
        status = FeasibilityStatus.PLAN_INFEASIBLE
    else:
        status = FeasibilityStatus.ESSENTIAL_SHORTFALL

    return FeasibilityReport(
        status=status,
        horizon_days=horizon_days,
        first_shortfall_on=planned.first_shortfall_on,
        max_shortfall=planned.max_shortfall,
        min_unallocated=planned.min_unallocated,
        min_unallocated_on=planned.min_unallocated_on,
        needs_reserves=essentials.min_unallocated < 0,
        essential_shortfall=essential_shortfall,
        essential_shortfall_on=essential_shortfall_on,
    )
