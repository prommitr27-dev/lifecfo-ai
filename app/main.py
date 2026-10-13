"""LifeCFO AI: Streamlit entry point.

Current scope (M1, M2): the daily cash flow forecast with its feasibility
check, the Personal CFO comparison of three validated plans, and the AI CFO
chat. The what-if control works on a copy of the state and never changes
stored data. The chat works with no LLM at all; see docs/AI_PROVIDERS.md.
"""

from pathlib import Path

import pandas as pd
import streamlit as st

from lifecfo.agents import AgentContext, AgentReply, build_agent
from lifecfo.cashflow import (
    FeasibilityStatus,
    check_feasibility,
    forecast_cash_flow,
    monthly_summary,
)
from lifecfo.domain.loader import load_state
from lifecfo.domain.models import FinancialState
from lifecfo.domain.money import SATANG_PER_THB, format_thb
from lifecfo.llm import LLMSettings, load_env_file
from lifecfo.optimization import PlanningResult, PlanningStatus, generate_plans

PROFILE = Path(__file__).resolve().parents[1] / "data" / "synthetic" / "profile_demo.yaml"
VIEWS = ["Cash flow", "Personal CFO", "AI CFO chat"]


@st.cache_data(max_entries=32)
def plan_for(state_json: str, horizon_months: int) -> PlanningResult:
    return generate_plans(FinancialState.model_validate_json(state_json), None, horizon_months)


def baht(satang: int) -> float:
    return satang / SATANG_PER_THB


def show_reply(reply: AgentReply) -> None:
    if reply.notice:
        st.caption(f":material/info: {reply.notice}")
    if reply.trace:
        with st.expander(f"Tools used: {', '.join(r.name for r in reply.trace)}", type="compact"):
            for result in reply.trace:
                tier = result.tier.name if result.tier is not None else "none"
                with st.expander(f"{result.name} (tier {tier})", type="step"):
                    st.json({"arguments": result.arguments, "ok": result.ok,
                             "result": result.data}, expanded=False)
    st.markdown(reply.text)
    source = "Offline engine" if reply.mode == "offline" else f"{reply.provider} / {reply.model}"
    st.caption(f"Answered by: {source}")


st.set_page_config(page_title="LifeCFO AI", page_icon=":material/savings:", layout="wide")
st.title("LifeCFO AI")
st.caption("Your financial plan should adapt when life doesn't. Synthetic sandbox data only.")

state = load_state(PROFILE)

with st.sidebar:
    st.header("What-if (hypothetical)")
    income_change = st.slider("Income change (%)", min_value=-100, max_value=50, value=0, step=5)
    st.caption("Hypothetical scenarios are simulated on a copy. Nothing is saved.")

if income_change != 0:
    scaled = tuple(
        income.model_copy(update={"amount": income.amount * (100 + income_change) // 100})
        for income in state.incomes
    )
    state = state.model_copy(update={"incomes": tuple(i for i in scaled if i.amount > 0)})

view = st.segmented_control("View", VIEWS, default=VIEWS[0], key="view") or VIEWS[0]

if view == "Cash flow":
    horizon = st.select_slider("Horizon (days)", options=[30, 60, 92, 183], value=92)
    forecast = forecast_cash_flow(state, horizon)
    report = check_feasibility(state, horizon, planned=forecast)

    st.subheader("Current plan")
    if report.status is FeasibilityStatus.FEASIBLE:
        st.success("FEASIBLE: the current plan is funded on every day of the horizon.")
    elif report.status is FeasibilityStatus.PLAN_INFEASIBLE:
        st.warning(
            f"PLAN_INFEASIBLE: unallocated cash first goes negative on "
            f"{report.first_shortfall_on} and the plan runs {format_thb(report.max_shortfall)} "
            "short. Essentials can still be paid, so the plan can be fixed by replanning."
            + (" Existing reserves would be needed." if report.needs_reserves else "")
        )
    else:
        st.error(
            f"ESSENTIAL_SHORTFALL: from {report.essential_shortfall_on}, essentials cannot be "
            "paid even with all flexible spending cut and every envelope used. "
            f"Shortfall: {format_thb(report.essential_shortfall)}."
        )

    with st.container(horizontal=True):
        st.metric("Sandbox cash today", format_thb(state.total_cash), border=True)
        st.metric("Lowest unallocated cash", format_thb(report.min_unallocated), border=True,
                  help=f"On {report.min_unallocated_on}")
        st.metric("Envelopes at end of horizon",
                  format_thb(sum(forecast.closing_envelopes.values())), border=True)

    st.subheader("Projected daily balances (THB)")
    daily = pd.DataFrame(
        {
            "date": [day.on for day in forecast.days],
            "Unallocated": [baht(day.unallocated) for day in forecast.days],
            "Total cash": [baht(day.total_cash) for day in forecast.days],
        }
    ).set_index("date")
    st.line_chart(daily, alt="Projected daily unallocated and total cash balances")

    st.subheader("Monthly summary (THB)")
    monthly = pd.DataFrame([m.model_dump() for m in monthly_summary(forecast)]).set_index("month")
    st.dataframe(monthly / SATANG_PER_THB, alt="Monthly cash flow summary")

    with st.expander("Scheduled cash events"):
        events = pd.DataFrame(
            [
                {"date": e.on, "kind": e.kind.value, "name": e.name, "amount_thb": baht(e.amount)}
                for day in forecast.days
                for e in day.events
            ]
        )
        st.dataframe(events, hide_index=True, alt="Scheduled cash events")

elif view == "AI CFO chat":
    load_env_file(Path(__file__).resolve().parents[1] / ".env")
    settings = LLMSettings.from_env()
    agent = build_agent(settings)
    if settings.problem:
        st.warning(f"AI provider is not usable ({settings.problem}) Running in offline mode.")
    elif settings.uses_llm:
        st.caption(
            f"AI provider: {settings.preset.label}, model `{settings.model}`. Calculations "
            "still come from the engines; if the provider fails, the offline engine answers."
        )
    else:
        st.caption("Offline mode: no LLM and no network. Answers are built from engine results.")

    history = st.session_state.setdefault("chat", [])
    for entry in history:
        with st.chat_message(entry["role"]):
            if entry["role"] == "user":
                st.markdown(entry["text"])
            else:
                show_reply(entry["reply"])

    if prompt := st.chat_input("Ask about your plan, goals, bills, or a what-if",
                               submit_mode="disable"):
        history.append({"role": "user", "text": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            reply = agent.reply(AgentContext(state), prompt)
            show_reply(reply)
        history.append({"role": "assistant", "reply": reply})

else:
    horizon_months = st.select_slider("Horizon (months)", options=[6, 12, 18, 24], value=12)
    result = plan_for(state.model_dump_json(), horizon_months)

    if result.status is PlanningStatus.ESSENTIAL_SHORTFALL:
        st.error(
            "ESSENTIAL_SHORTFALL: no plan can pay the essential obligations. From "
            f"{result.feasibility.essential_shortfall_on} the shortfall reaches "
            f"{format_thb(result.feasibility.essential_shortfall)} even with flexible spending "
            "at its minimum and every envelope used. No plan is offered."
        )
    elif result.status is PlanningStatus.REQUIRES_RESERVE_DRAWDOWN:
        st.warning(
            "REQUIRES_RESERVE_DRAWDOWN: essentials can only be paid by using existing "
            "savings. That is a recovery decision, so no regular plan is offered."
        )
    else:
        st.success(
            f"OK: {len(result.plans)} plans generated. Each one passed the deterministic "
            "validator and the daily cash check."
        )
        for note in result.identical:
            st.info(note.describe())

        st.subheader("Strategy comparison")
        comparison = pd.DataFrame(
            [
                {
                    "Strategy": plan.label,
                    "Reserve reached": (plan.reserve.reached_month or "Not in horizon")
                    if plan.reserve else "No reserve",
                    **{
                        goal.name: (goal.completion_month or "Not in horizon")
                        + ("" if goal.on_track is not False
                           else f" (late, {format_thb(goal.shortfall_at_deadline)} short)")
                        for goal in plan.goals
                    },
                    "Flexible kept (THB)": baht(sum(m.flexible_total for m in plan.months)),
                    "Goals at risk": len(plan.goals_at_risk),
                }
                for plan in result.plans
            ]
        )
        st.dataframe(comparison, hide_index=True, alt="Comparison of the three planning strategies")

        chosen = st.segmented_control(
            "Plan details", [plan.label for plan in result.plans], default=result.plans[0].label
        )
        plan = next((p for p in result.plans if p.label == chosen), result.plans[0])
        schedule = pd.DataFrame(
            [
                {
                    "Month": month.month,
                    **{envelope: baht(amount) for envelope, amount in month.contributions.items()},
                    "Flexible spending": baht(month.flexible_total),
                    "Unallocated after sweep": baht(month.closing_unallocated),
                }
                for month in plan.months
            ]
        ).fillna(0.0)
        st.dataframe(schedule, hide_index=True,
                     alt=f"Monthly allocations for the {plan.label} plan in baht")
        st.caption(
            "Savings are swept on the last day of each month. Plans are proposals: nothing is "
            "applied until approval and sandbox execution are added in the next milestone."
        )
