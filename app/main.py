"""LifeCFO AI: Streamlit entry point.

M1 scope: load the synthetic demo profile and show the daily cash flow
forecast and feasibility check. The what-if control works on a copy of the
state and never changes stored data.
"""

from pathlib import Path

import pandas as pd
import streamlit as st

from lifecfo.cashflow import (
    FeasibilityStatus,
    check_feasibility,
    forecast_cash_flow,
    monthly_summary,
)
from lifecfo.domain.loader import load_state
from lifecfo.domain.money import SATANG_PER_THB, format_thb

PROFILE = Path(__file__).resolve().parents[1] / "data" / "synthetic" / "profile_demo.yaml"

st.set_page_config(page_title="LifeCFO AI", layout="wide")
st.title("LifeCFO AI")
st.caption("Your financial plan should adapt when life doesn't. Synthetic sandbox data only.")

state = load_state(PROFILE)

with st.sidebar:
    st.header("What-if (hypothetical)")
    income_change = st.slider("Income change (%)", min_value=-100, max_value=50, value=0, step=5)
    horizon = st.select_slider("Horizon (days)", options=[30, 60, 92, 183], value=92)
    st.caption("Hypothetical scenarios are simulated on a copy. Nothing is saved.")

if income_change != 0:
    scaled = tuple(
        income.model_copy(update={"amount": income.amount * (100 + income_change) // 100})
        for income in state.incomes
    )
    state = state.model_copy(update={"incomes": tuple(i for i in scaled if i.amount > 0)})

forecast = forecast_cash_flow(state, horizon)
report = check_feasibility(state, horizon, planned=forecast)

if report.status is FeasibilityStatus.FEASIBLE:
    st.success("FEASIBLE: the current plan is funded on every day of the horizon.")
elif report.status is FeasibilityStatus.PLAN_INFEASIBLE:
    st.warning(
        f"PLAN_INFEASIBLE: unallocated cash first goes negative on {report.first_shortfall_on} "
        f"and the plan runs {format_thb(report.max_shortfall)} short. Essentials can still be "
        "paid, so the plan can be fixed by replanning."
        + (" Existing reserves would be needed." if report.needs_reserves else "")
    )
else:
    st.error(
        f"ESSENTIAL_SHORTFALL: from {report.essential_shortfall_on}, essentials cannot be paid "
        f"even with all flexible spending cut and every envelope used. "
        f"Shortfall: {format_thb(report.essential_shortfall)}."
    )

left, middle, right = st.columns(3)
left.metric("Sandbox cash today", format_thb(state.total_cash))
middle.metric("Lowest unallocated cash", format_thb(report.min_unallocated),
              help=f"On {report.min_unallocated_on}")
right.metric("Envelopes at end of horizon", format_thb(sum(forecast.closing_envelopes.values())))

st.subheader("Projected daily balances (THB)")
daily = pd.DataFrame(
    {
        "date": [day.on for day in forecast.days],
        "Unallocated": [day.unallocated / SATANG_PER_THB for day in forecast.days],
        "Total cash": [day.total_cash / SATANG_PER_THB for day in forecast.days],
    }
).set_index("date")
st.line_chart(daily)

st.subheader("Monthly summary (THB)")
monthly = pd.DataFrame([m.model_dump() for m in monthly_summary(forecast)]).set_index("month")
st.dataframe(monthly / SATANG_PER_THB, use_container_width=True)

with st.expander("Scheduled cash events"):
    events = pd.DataFrame(
        [
            {"date": e.on, "kind": e.kind.value, "name": e.name,
             "amount_thb": e.amount / SATANG_PER_THB}
            for day in forecast.days
            for e in day.events
        ]
    )
    st.dataframe(events, use_container_width=True, hide_index=True)
