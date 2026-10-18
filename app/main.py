"""LifeCFO AI: Streamlit entry point.

Views: daily cash flow forecast, Personal CFO plan comparison, AI CFO chat, and
the Sandbox where the user approves plans and the audit log is shown. State is
kept in a local SQLite sandbox. The what-if control works on a copy and never
changes stored data. The chat works with no LLM at all; see docs/AI_PROVIDERS.md.
"""

import json
import os
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st
import ui

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
from lifecfo.domain.money import SATANG_PER_THB, format_thb, thb
from lifecfo.llm import LLMSettings, load_env_file
from lifecfo.optimization import PlanningResult, PlanningStatus, generate_plans
from lifecfo.services import OpResult, SandboxService

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "data" / "synthetic" / "profile_demo.yaml"
DB_PATH = Path(os.environ.get("LIFECFO_DB_PATH") or ROOT / ".lifecfo" / "sandbox.db")


def setting(name: str) -> str:
    """An environment variable, or a Streamlit secret of the same name (Community Cloud)."""
    if name in os.environ:
        return os.environ[name]
    try:
        # Loading st.secrets also exports root-level secrets as environment variables,
        # which is how the LLM settings below pick up keys stored as Cloud secrets.
        return str(st.secrets.get(name, ""))
    except Exception:  # no secrets file: a plain local run
        return ""


# On a public deployment set LIFECFO_SANDBOX=session: every visitor then gets a private
# in-memory sandbox that disappears with their browser session, so one visitor's
# approvals or reset never show up for another.
PER_VISITOR = setting("LIFECFO_SANDBOX").strip().lower() == "session"
VIEWS = ["Cash flow", "Personal CFO", "AI CFO chat", "Rewards", "Sandbox"]
SUBTITLES = {
    "Cash flow": "See what you can use today and how your plan holds up over the horizon.",
    "Personal CFO": "Compare three validated plans for your reserve, goals, and flexible spending.",
    "AI CFO chat": "Ask about your plan, bills, goals, or a what-if. Every number comes from the "
                   "engines.",
    "Rewards": "Goal progress, streaks, and weekly missions. For motivation only.",
    "Sandbox": "Approve plans, record real events, and check the audit log. Synthetic data only.",
}


@st.cache_resource
def open_store(path: str) -> Store:
    return Store(path)



@st.cache_data(max_entries=32)
def plan_for(state_json: str, horizon_months: int) -> PlanningResult:
    return generate_plans(FinancialState.model_validate_json(state_json), None, horizon_months)


def baht(satang: int) -> float:
    return satang / SATANG_PER_THB


def baht_columns(frame: pd.DataFrame) -> dict:
    """Show every numeric column with thousand separators, e.g. 30,000."""
    return {
        name: st.column_config.NumberColumn(format="localized")
        for name in frame.columns
        if pd.api.types.is_numeric_dtype(frame[name]) and name != "#"
    }


def reset_what_if() -> None:
    st.session_state["income_change"] = 0


def cash_chart(daily: pd.DataFrame, low_on, low_value: float) -> alt.LayerChart:
    """Daily balances: total cash in navy, unallocated in teal, the lowest point marked."""
    long = daily.reset_index().melt("date", var_name="series", value_name="thb")
    lines = alt.Chart(long).mark_line(strokeWidth=2.4).encode(
        x=alt.X("date:T", title=None, axis=alt.Axis(format="%-d %b", grid=False,
                                                    labelColor="#94A3B8", tickCount=6)),
        y=alt.Y("thb:Q", title=None, axis=alt.Axis(
            labelColor="#94A3B8", gridColor="#E9EEF3", domain=False, ticks=False,
            labelExpr="datum.value >= 1000 ? format(datum.value / 1000, '~') + 'k' : datum.value")),
        color=alt.Color("series:N", legend=None, scale=alt.Scale(
            domain=["Total cash", "Unallocated"], range=[ui.NAVY, ui.TEAL])),
        tooltip=[alt.Tooltip("date:T", format="%-d %b %Y"), "series:N",
                 alt.Tooltip("thb:Q", format=",.0f", title="THB")],
    )
    low = pd.DataFrame({"date": [pd.Timestamp(low_on)], "thb": [low_value],
                        "label": [f"Lowest: ฿{low_value:,.0f}"]})
    point = alt.Chart(low).mark_point(filled=True, fill="#FFFFFF", stroke=ui.TEAL,
                                      strokeWidth=2, size=60).encode(x="date:T", y="thb:Q")
    label = alt.Chart(low).mark_text(dy=-16, fontSize=11, color="#475569").encode(
        x="date:T", y="thb:Q", text="label:N")
    return (lines + point + label).properties(height=230).configure_view(stroke=None)


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
ui.apply_styles()

if PER_VISITOR:
    if "visitor_store" not in st.session_state:
        st.session_state["visitor_store"] = Store(":memory:")
    store = st.session_state["visitor_store"]
else:
    store = open_store(str(DB_PATH))
sandbox = SandboxService(store)
if sandbox.store.load_state() is None:
    sandbox.reset(load_state(PROFILE), actor="SYSTEM")
state = sandbox.state

with st.sidebar:
    ui.sidebar_brand(state.as_of, "Synthetic data")
    with st.container(border=True):
        ui.card_head("What-if income changes?",
                     "Preview how a change to every income may affect your plan.")
        current = st.session_state.get("income_change", 0)
        st.html(f'<div class="lc-big">{current:+d}%</div>'
                '<div class="lc-unit">change to income</div>' if current else
                '<div class="lc-big">0%</div><div class="lc-unit">no change</div>')
        income_change = st.slider("Income change (%)", min_value=-100, max_value=50, value=0,
                                  step=5, key="income_change", label_visibility="collapsed")
        st.caption(":material/info: This is a planning scenario, simulated on a copy. "
                   "Your sandbox data stays as it is.")
        st.button("Reset to current plan", on_click=reset_what_if, width="stretch")

hypothetical = income_change != 0
if hypothetical:
    scaled = tuple(
        income.model_copy(update={"amount": income.amount * (100 + income_change) // 100})
        for income in state.incomes
    )
    state = state.model_copy(update={"incomes": tuple(i for i in scaled if i.amount > 0)})

shown = st.session_state.get("view") or VIEWS[0]
ui.page_header(shown, SUBTITLES[shown], sandbox.state.as_of)
view = st.segmented_control("View", VIEWS, default=VIEWS[0], key="view", required=True,
                            label_visibility="collapsed") or VIEWS[0]

if view == "Cash flow":
    horizon = st.segmented_control("Horizon", [30, 60, 92, 183], default=92,
                                   format_func=lambda days: f"{days} days", key="horizon",
                                   required=True,
                                   label_visibility="collapsed") or 92
    forecast = forecast_cash_flow(state, horizon)
    report = check_feasibility(state, horizon, planned=forecast)

    if report.status is FeasibilityStatus.FEASIBLE:
        st.success("FEASIBLE: the current plan is funded on every day of the horizon.",
                   icon=":material/check_circle:")
    elif report.status is FeasibilityStatus.PLAN_INFEASIBLE:
        st.warning(
            f"PLAN_INFEASIBLE: unallocated cash first goes negative on "
            f"{report.first_shortfall_on} and the plan runs {format_thb(report.max_shortfall)} "
            "short. Essentials can still be paid, so the plan can be fixed by replanning."
            + (" Existing reserves would be needed." if report.needs_reserves else ""),
            icon=":material/warning:",
        )
    else:
        st.error(
            f"ESSENTIAL_SHORTFALL: from {report.essential_shortfall_on}, essentials cannot be "
            "paid even with all flexible spending cut and every envelope used. "
            f"Shortfall: {format_thb(report.essential_shortfall)}.",
            icon=":material/error:",
        )

    if report.min_unallocated > 0:
        low_help = f"Lowest point on {ui.short_date(report.min_unallocated_on)}"
    elif report.min_unallocated == 0:
        low_help = "Plan stays funded, with <strong>no spare buffer</strong>"
    else:
        low_help = (f'<strong class="bad">Short</strong> from '
                    f"{ui.short_date(report.min_unallocated_on)}")
    with st.container(horizontal=True):
        ui.metric_card("Sandbox cash today", ui.baht_text(state.total_cash),
                       f"Cash available on {ui.short_date(state.as_of)}", primary=True)
        ui.metric_card("Lowest unallocated cash", ui.baht_text(report.min_unallocated), low_help)
        ui.metric_card("Envelopes at end of horizon",
                       ui.baht_text(sum(forecast.closing_envelopes.values())),
                       "Reserved in savings envelopes")

    daily = pd.DataFrame(
        {
            "date": [day.on for day in forecast.days],
            "Total cash": [baht(day.total_cash) for day in forecast.days],
            "Unallocated": [baht(day.unallocated) for day in forecast.days],
        }
    ).set_index("date")
    events = [e for day in forecast.days for e in day.events]
    with st.container(key="cash-visuals"):
        chart_col, events_col = st.columns([2.7, 1])
        with chart_col, st.container(border=True):
            ui.card_head("How your cash changes", f"Projected daily balances · next {horizon} days")
            ui.chart_legend()
            st.altair_chart(cash_chart(daily, report.min_unallocated_on,
                                       baht(report.min_unallocated)), width="stretch")
            ui.chart_foot()
        with events_col, st.container(border=True):
            ui.card_head("Coming up", "Events that change your balance")
            ui.upcoming_events(events[:4])

    months = monthly_summary(forecast)
    with st.container(border=True):
        head, note = st.columns([3, 1])
        with head:
            ui.card_head("Monthly summary", "Income and outflows in THB · Unallocated excludes "
                                            "reserved envelopes")
        with note:
            if months:
                ui.mini_note(f"{ui.month_label(months[0].month)} – "
                             f"{ui.month_label(months[-1].month)}")
        ui.monthly_table(months)

    with st.expander("All planned movements"):
        table = pd.DataFrame(
            [
                {"Date": e.on, "Kind": e.kind.value.replace("_", " ").capitalize(),
                 "Name": e.name, "Amount (THB)": baht(e.amount)}
                for e in events
            ]
        )
        st.dataframe(table, hide_index=True, column_config=baht_columns(table),
                     alt="Scheduled cash events")

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

elif view == "Rewards":
    rewards = sandbox.rewards
    message = st.session_state.pop("rewards_message", None)
    if message:
        st.success(message)
    opted_in = st.toggle("Use rewards and streaks", value=rewards.opted_in,
                         help="Switching off stops all recording. Goal progress stays visible.")
    if opted_in != rewards.opted_in:
        rewards.set_opt_in(opted_in)
        st.rerun()
    data = rewards.status()

    st.subheader("Goal progress")
    for goal in data["goal_progress"]:
        st.progress(min(1.0, goal["percent"] / 100),
                    text=f"{goal['goal']}: {format_thb(goal['saved'])} of "
                         f"{format_thb(goal['target'])} ({goal['percent']}%)")

    if data["opted_in"]:
        st.subheader("Your CFO companion")
        with st.container(border=True, horizontal=True, vertical_alignment="center"):
            st.markdown(":material/savings: **Level " + str(data["level"]) + "**")
            if data["next_level_at_xp"]:
                st.progress(data["xp"] / data["next_level_at_xp"],
                            text=f"{data['xp']} of {data['next_level_at_xp']} XP to the next "
                                 "level")
            else:
                st.markdown(f"{data['xp']} XP, top level")

        with st.container(horizontal=True):
            for kind, streak in data["streaks"].items():
                label = "Daily streak" if kind == "DAILY" else "Weekly streak"
                state = {"NOT_STARTED": "Not started", "ACTIVE": "Active",
                         "PROTECTED": f"Protected until {streak['protected_until']}",
                         "PAUSED": "Paused", "BROKEN": "Start again any time"}[streak["status"]]
                st.metric(label, streak["count"], border=True, help=f"Best: {streak['best']}",
                          delta=state, delta_color="off")

        st.subheader("This week's missions")
        if data["missions"].get("note"):
            st.info(data["missions"]["note"])
        for mission in data["missions"]["items"]:
            st.checkbox(mission["title"], value=mission["done"], disabled=True,
                        key=f"mission-{mission['id']}")
        with st.container(horizontal=True):
            if st.button("I reviewed my bills and plan today", icon=":material/task_alt:",
                         type="primary"):
                recorded = rewards.record_review()
                st.session_state["rewards_message"] = (
                    "Check-in recorded." if recorded else "Already recorded for today.")
                st.rerun()
            if any(s["status"] == "PAUSED" for s in data["streaks"].values()):
                if st.button("Resume streaks", icon=":material/play_arrow:"):
                    rewards.resume_streaks()
                    st.rerun()
            elif st.button("Pause streaks", icon=":material/pause:"):
                rewards.pause_streaks()
                st.rerun()

        if data["badges"]:
            st.subheader("Badges")
            st.pills("Badges", data["badges"], disabled=True, label_visibility="collapsed")
        st.caption(data["note"])
    else:
        st.caption(data["note"])

elif view == "Sandbox":
    message = st.session_state.pop("sandbox_message", None)
    if message:
        (st.success if message[0] else st.error)(message[1])

    stored = sandbox.state
    chain_ok = sandbox.store.verify_audit_chain()
    with st.container(horizontal=True):
        ui.metric_card("Sandbox date", stored.as_of.isoformat(), "Simulated calendar", unit="",
                       primary=True)
        ui.metric_card("Sandbox cash", ui.baht_text(stored.total_cash),
                       "A simulated account. No real money, bank, or credentials.")
        ui.metric_card("Audit log", "Intact" if chain_ok else "Altered",
                       "Each entry stores the hash of the previous one" if chain_ok else
                       '<strong class="bad">The hash chain does not match</strong>', unit="")

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

    st.subheader("Record something that really happened")
    st.caption("Use this only for real events, not what-ifs. A confirmed expense becomes an "
               "essential bill, so earlier proposals must be redone.")
    with st.form("confirm_expense", border=True):
        with st.container(horizontal=True, vertical_alignment="bottom"):
            shock_name = st.text_input("What was it?", value="Car repair", max_chars=60)
            shock_amount = st.number_input("Amount (THB)", min_value=1, max_value=10_000_000,
                                           value=10000, step=500)
            shock_date = st.date_input("Due on", value=stored.as_of, min_value=stored.as_of)
        if st.form_submit_button("Confirm this expense", icon=":material/report:"):
            report_result(sandbox.confirm_expense(shock_name, thb(shock_amount), shock_date))
    if stored.emergency is not None and stored.emergency.balance > 0:
        with st.form("withdraw_reserve", border=True):
            with st.container(horizontal=True, vertical_alignment="bottom"):
                amount = st.number_input(
                    "Withdraw from the emergency reserve (THB)", min_value=1,
                    max_value=int(stored.emergency.balance // SATANG_PER_THB),
                    value=min(1000, int(stored.emergency.balance // SATANG_PER_THB)), step=500)
                if st.form_submit_button("Withdraw", icon=":material/savings:"):
                    report_result(sandbox.withdraw_reserve(thb(amount)))

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
        transactions = pd.DataFrame([
            {"#": r["id"], "date": r["effective_on"], "kind": r["kind"], "ref": r["ref"],
             "from": r["from_envelope"], "to": r["to_envelope"],
             "amount_thb": baht(r["amount"])}
            for r in rows
        ])
        st.dataframe(transactions, hide_index=True, column_config=baht_columns(transactions),
                     alt="Sandbox transactions")
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
            "validator and the daily cash check.",
            icon=":material/verified:",
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
        st.dataframe(schedule, hide_index=True, column_config=baht_columns(schedule),
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
