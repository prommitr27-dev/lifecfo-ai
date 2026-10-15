"""LifeCFO AI: Streamlit entry point.

Views: daily cash flow forecast, Personal CFO plan comparison, AI CFO chat, and
the Sandbox where the user approves plans and the audit log is shown. State is
kept in a local SQLite sandbox. The what-if control works on a copy and never
changes stored data. The chat works with no LLM at all; see docs/AI_PROVIDERS.md.
"""

import json
import os
from pathlib import Path

import pandas as pd
import streamlit as st

from lifecfo.agents import AgentContext, AgentReply, Tier, build_agent, explain
from lifecfo.agents.views import position_data
from lifecfo.cashflow import (
    FeasibilityStatus,
    check_feasibility,
    forecast_cash_flow,
    monthly_summary,
)
from lifecfo.database import Store
from lifecfo.domain.loader import load_state
from lifecfo.domain.models import FinancialState
from lifecfo.domain.money import SATANG_PER_THB, format_thb
from lifecfo.llm import LLMSettings, load_env_file
from lifecfo.optimization import PlanningResult, PlanningStatus, generate_plans
from lifecfo.services import OpResult, SandboxService

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "data" / "synthetic" / "profile_demo.yaml"
DB_PATH = Path(os.environ.get("LIFECFO_DB_PATH") or ROOT / ".lifecfo" / "sandbox.db")
VIEWS = ["Cash flow", "Personal CFO", "AI CFO chat", "Sandbox"]


@st.cache_resource
def open_store(path: str) -> Store:
    return Store(path)



@st.cache_data(max_entries=32)
def plan_for(state_json: str, horizon_months: int) -> PlanningResult:
    return generate_plans(FinancialState.model_validate_json(state_json), None, horizon_months)


def baht(satang: int) -> float:
    return satang / SATANG_PER_THB


def report_result(result: OpResult) -> None:
    """Keep the outcome of a sandbox action so it is shown after the rerun."""
    st.session_state["sandbox_message"] = (result.ok, f"{result.code}: {result.message}")
    st.rerun()


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

sandbox = SandboxService(open_store(str(DB_PATH)))
if sandbox.store.load_state() is None:
    sandbox.reset(load_state(PROFILE), actor="SYSTEM")
state = sandbox.state

with st.sidebar:
    st.header("What-if (hypothetical)")
    income_change = st.slider("Income change (%)", min_value=-100, max_value=50, value=0, step=5)
    st.caption("Hypothetical scenarios are simulated on a copy. Nothing is saved.")

hypothetical = income_change != 0
if hypothetical:
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
    load_env_file(ROOT / ".env")
    settings = LLMSettings.from_env()
    # The agent may call the execute tool, which itself refuses without the user's approval.
    agent = build_agent(settings, max_tier=Tier.EXECUTE)
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
            past = [(e["role"], e["text"] if e["role"] == "user" else e["reply"].text)
                    for e in history[:-1]]
            context = AgentContext(state, None if hypothetical else sandbox)
            reply = agent.reply(context, prompt, past)
            show_reply(reply)
        history.append({"role": "assistant", "reply": reply})

elif view == "Sandbox":
    message = st.session_state.pop("sandbox_message", None)
    if message:
        (st.success if message[0] else st.error)(message[1])

    stored = sandbox.state
    chain_ok = sandbox.store.verify_audit_chain()
    with st.container(horizontal=True):
        st.metric("Sandbox date", stored.as_of.isoformat(), border=True)
        st.metric("Sandbox cash", format_thb(stored.total_cash), border=True)
        st.metric("Audit log", "Intact" if chain_ok else "Altered", border=True,
                  help="Each entry stores the hash of the previous one.")
    st.caption("A simulated account. No real money, bank, or credentials are involved.")

    st.subheader("Waiting for your decision")
    pending = sandbox.store.list_plans("PROPOSED")
    if not pending:
        st.caption("No proposals. Propose a plan from Personal CFO or ask in the chat.")
    for row in pending:
        with st.container(border=True, horizontal=True, vertical_alignment="center"):
            st.markdown(f"**{row['label']}** plan `{row['id']}`, proposed {row['created_at']}")
            if st.button("Approve", key=f"approve-{row['id']}", type="primary",
                         icon=":material/check:"):
                report_result(sandbox.decide(row["id"], True))
            if st.button("Reject", key=f"reject-{row['id']}", icon=":material/close:"):
                report_result(sandbox.decide(row["id"], False))

    st.subheader("Approved, ready to execute")
    ready = [a for a in sandbox.store.list_approvals()
             if a["decision"] == "APPROVED" and a["used_at"] is None]
    if not ready:
        st.caption("Nothing approved is waiting.")
    for approval in ready:
        plan_row = sandbox.store.get_plan(approval["plan_id"])
        with st.container(border=True, horizontal=True, vertical_alignment="center"):
            st.markdown(f"**{plan_row['label']}** plan `{plan_row['id']}`, approval "
                        f"`{approval['id']}`")
            if st.button("Execute in sandbox", key=f"execute-{approval['id']}", type="primary",
                         icon=":material/play_arrow:"):
                report_result(sandbox.execute(approval["id"], "USER"))

    st.subheader("Move time forward")
    with st.container(horizontal=True, vertical_alignment="bottom"):
        days = st.number_input("Days", min_value=1, max_value=366, value=30, step=1)
        if st.button("Post scheduled transactions", icon=":material/fast_forward:"):
            report_result(sandbox.advance(int(days)))
    st.caption("Posts income, bills, and savings transfers for those days as sandbox "
               "transactions. It is refused if cash would run short.")

    st.subheader("Sandbox transactions")
    rows = sandbox.store.list_transactions()
    if rows:
        st.dataframe(
            pd.DataFrame([
                {"#": r["id"], "date": r["effective_on"], "kind": r["kind"], "ref": r["ref"],
                 "from": r["from_envelope"], "to": r["to_envelope"],
                 "amount_thb": baht(r["amount"])}
                for r in rows
            ]),
            hide_index=True, alt="Sandbox transactions",
        )
    else:
        st.caption("No transactions yet.")

    st.subheader("Audit log")
    entries = sandbox.store.list_audit()
    st.dataframe(
        pd.DataFrame([
            {"#": e.seq, "time (UTC)": e.ts, "actor": e.actor, "action": e.action,
             "code": e.payload.get("code", ""), "plan": e.payload.get("plan_id", ""),
             "hash": e.hash[:12]}
            for e in entries
        ]),
        hide_index=True, alt="Audit log entries",
    )
    with st.container(horizontal=True):
        st.download_button(
            "Download audit log (JSON)",
            data=json.dumps(
                {"chain_intact": chain_ok,
                 "entries": [e.__dict__ for e in entries],
                 "transactions": [dict(r) for r in rows]}, indent=2),
            file_name="lifecfo_sandbox_log.json", mime="application/json",
            icon=":material/download:",
        )
        if st.button("Reset sandbox", icon=":material/restart_alt:"):
            st.session_state.pop("chat", None)
            report_result(sandbox.reset(load_state(PROFILE)))

else:
    horizon_months = st.select_slider("Horizon (months)", options=[6, 12, 18, 24], value=12)
    result = plan_for(state.model_dump_json(), horizon_months)

    # Rules D2: the user's own position comes first, before any proposal.
    with st.container(border=True):
        st.markdown(explain.position(position_data(result.position)))

    if result.status is PlanningStatus.ESSENTIAL_SHORTFALL:
        st.error(
            "ESSENTIAL_SHORTFALL: no plan can pay essential expenses and minimum debt "
            f"payments. From {result.feasibility.essential_shortfall_on} the shortfall reaches "
            f"{format_thb(result.feasibility.essential_shortfall)} even with no flexible "
            "spending, no savings, and the whole emergency reserve used. Nothing is reduced "
            "to make a plan fit, so no plan is offered."
        )
    elif result.status is PlanningStatus.REQUIRES_RESERVE_DRAWDOWN:
        st.warning(
            "REQUIRES_RESERVE_DRAWDOWN: essentials can only be paid by withdrawing from the "
            "emergency reserve. That is a recovery decision, so no regular plan is offered."
        )
    elif result.status is PlanningStatus.FLEXIBLE_SPENDING_CONSTRAINT:
        st.warning(
            "FLEXIBLE_SPENDING_CONSTRAINT: even at the flexible minimum you allowed, the "
            "budget runs short. A plan needs a change to one of your preferences, which is "
            "your decision."
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
                    "Flexible, first month (THB)": (
                        f"{baht(plan.months[0].flexible_total):,.0f} of "
                        f"{baht(plan.months[0].flexible_max):,.0f}"),
                    "Months below buffer": len(plan.months_below_buffer),
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
                    **{f"extra: {debt}": baht(amount)
                       for debt, amount in month.extra_debt.items()},
                    "Flexible spending": baht(month.flexible_total),
                    "Flexible budget": baht(month.flexible_max),
                    "Below buffer by": baht(month.buffer_shortfall),
                    "Unallocated after sweep": baht(month.closing_unallocated),
                }
                for month in plan.months
            ]
        ).fillna(0.0)
        st.dataframe(schedule, hide_index=True,
                     alt=f"Monthly allocations for the {plan.label} plan in baht")
        st.caption("Savings are swept on the last day of each month. A plan is only a "
                   "proposal until you approve it in the Sandbox view.")
        if hypothetical:
            st.info("This is a what-if view. Set the income change back to 0 to propose a plan "
                    "for your actual sandbox state.")
        elif st.button(f"Request approval for the {plan.label} plan",
                       icon=":material/assignment_turned_in:"):
            outcome = sandbox.propose(plan, "USER")
            (st.success if outcome.ok else st.error)(
                f"{outcome.code}: {outcome.message} Open the Sandbox view to decide.")
