"""HTTP API for the mobile app.

A thin layer over the same engines and `SandboxService` that the Streamlit app
uses. It adds no financial logic. Money is returned as integer satang in fields
ending in `_satang`; the client formats it.

Approval rules stay where they are: `SandboxService.decide` is called with the
USER actor only from the decision endpoint, which a person triggers by tapping
Approve or Reject. The chat agent runs with the AGENT actor and cannot approve.
Plans are never accepted from the client: the server regenerates them from the
stored state and stores the one the user picked.

Single-user demo server for the synthetic sandbox. If `LIFECFO_API_TOKEN` is
set, every request except /health must send `Authorization: Bearer <token>`.
"""

import os
import secrets
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field

from lifecfo.agents import AgentContext, AgentReply, Tier, build_agent, explain
from lifecfo.agents.views import position_data
from lifecfo.cashflow import check_feasibility, forecast_cash_flow, monthly_summary
from lifecfo.database import Store
from lifecfo.domain.loader import load_state
from lifecfo.domain.models import FinancialState
from lifecfo.domain.money import thb
from lifecfo.llm import LLMSettings, load_env_file
from lifecfo.optimization import Plan, PlanningStatus, generate_plans
from lifecfo.services import OpResult, SandboxService

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROFILE = ROOT / "data" / "synthetic" / "profile_demo.yaml"
DEFAULT_DB = ROOT / ".lifecfo" / "sandbox.db"

IncomeChange = Annotated[int, Query(ge=-100, le=50, description="What-if income change, %")]


# --- request bodies ----------------------------------------------------------------


class Body(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProposeIn(Body):
    strategy: str = Field(min_length=1, max_length=40)
    horizon_months: int = Field(default=12, ge=1, le=24)


class DecisionIn(Body):
    approve: bool


class ExpenseIn(Body):
    name: str = Field(min_length=1, max_length=60)
    amount_thb: int = Field(ge=1, le=10_000_000)
    due_on: date | None = None


class WithdrawIn(Body):
    amount_thb: int = Field(ge=1, le=10_000_000)


class AdvanceIn(Body):
    days: int = Field(ge=1, le=366)


class ChatTurn(Body):
    role: str = Field(pattern="^(user|assistant)$")
    text: str = Field(max_length=4000)


class ChatIn(Body):
    message: str = Field(min_length=1, max_length=2000)
    history: list[ChatTurn] = Field(default_factory=list, max_length=40)
    income_change: int = Field(default=0, ge=-100, le=50)


class OptInIn(Body):
    opted_in: bool


# --- helpers -----------------------------------------------------------------------


def _iso(day: date | None) -> str | None:
    return day.isoformat() if day else None


def _what_if(state: FinancialState, income_change: int) -> FinancialState:
    """Same hypothetical as the Streamlit sidebar: a copy, never stored."""
    if income_change == 0:
        return state
    scaled = tuple(
        income.model_copy(update={"amount": income.amount * (100 + income_change) // 100})
        for income in state.incomes
    )
    return state.model_copy(update={"incomes": tuple(i for i in scaled if i.amount > 0)})


def _op(result: OpResult) -> dict[str, Any]:
    return {"ok": result.ok, "code": result.code, "message": result.message, "data": result.data}


def _plan_summary(plan: Plan) -> dict[str, Any]:
    first = plan.months[0]
    return {
        "strategy": plan.strategy,
        "label": plan.label,
        "horizon_months": plan.horizon_months,
        "reserve": None if plan.reserve is None else {
            "target_satang": plan.reserve.target,
            "saved_now_satang": plan.reserve.saved_now,
            "projected_saved_satang": plan.reserve.projected_saved,
            "reached_month": plan.reserve.reached_month,
        },
        "goals": [
            {
                "id": g.goal_id, "name": g.name, "target_satang": g.target,
                "saved_now_satang": g.saved_now, "projected_saved_satang": g.projected_saved,
                "completion_month": g.completion_month, "deadline": _iso(g.deadline),
                "on_track": g.on_track, "shortfall_at_deadline_satang": g.shortfall_at_deadline,
            }
            for g in plan.goals
        ],
        "first_month": {
            "month": first.month,
            "contributions_satang": first.contributions,
            "extra_debt_satang": first.extra_debt,
            "flexible_total_satang": first.flexible_total,
            "flexible_max_satang": first.flexible_max,
        },
        "months": [
            {
                "month": m.month,
                "contributions_satang": m.contributions,
                "extra_debt_satang": m.extra_debt,
                "flexible_total_satang": m.flexible_total,
                "flexible_max_satang": m.flexible_max,
                "buffer_shortfall_satang": m.buffer_shortfall,
                "closing_unallocated_satang": m.closing_unallocated,
            }
            for m in plan.months
        ],
        "months_below_buffer": list(plan.months_below_buffer),
        "goals_at_risk": list(plan.goals_at_risk),
    }


def _reply(reply: AgentReply) -> dict[str, Any]:
    return {
        "text": reply.text,
        "mode": reply.mode,
        "provider": reply.provider,
        "model": reply.model,
        "notice": reply.notice,
        "tools": [
            {"name": r.name, "tier": r.tier.name if r.tier is not None else None, "ok": r.ok}
            for r in reply.trace
        ],
    }


# --- app ---------------------------------------------------------------------------


def create_app(
    db_path: str | Path | None = None,
    profile: str | Path | None = None,
    *,
    api_token: str | None = None,
    llm_settings: LLMSettings | None = None,
) -> FastAPI:
    db = str(db_path or os.environ.get("LIFECFO_DB_PATH") or DEFAULT_DB)
    if db != ":memory:":
        Path(db).parent.mkdir(parents=True, exist_ok=True)
    profile_path = Path(profile or DEFAULT_PROFILE)
    token = api_token if api_token is not None else os.environ.get("LIFECFO_API_TOKEN", "")

    sandbox = SandboxService(Store(db))
    if sandbox.store.load_state() is None:
        sandbox.reset(load_state(profile_path), actor="SYSTEM")
    # One SQLite connection is shared, so requests are served one at a time.
    lock = threading.Lock()

    if llm_settings is None:
        load_env_file(ROOT / ".env")
        llm_settings = LLMSettings.from_env()
    # Same as the Streamlit chat: the execute tool itself refuses without an approval.
    agent = build_agent(llm_settings, max_tier=Tier.EXECUTE)

    def check_token(authorization: Annotated[str | None, Header()] = None) -> None:
        if not token:
            return
        expected = f"Bearer {token}"
        if authorization is None or not secrets.compare_digest(authorization, expected):
            raise HTTPException(status_code=401, detail="Missing or wrong API token.")

    @contextmanager
    def locked() -> Iterator[SandboxService]:
        with lock:
            yield sandbox

    app = FastAPI(title="LifeCFO AI API", version="0.1.0")
    # Expo web and LAN devices call from other origins; the token (if set) is the guard.
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                       allow_headers=["*"])
    guarded = [Depends(check_token)]

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {"ok": True, "auth_required": bool(token)}

    @app.get("/summary", dependencies=guarded)
    def summary() -> dict[str, Any]:
        with locked() as s:
            state = s.state
            pending = len(s.store.list_plans("PROPOSED"))
            return {
                "as_of": state.as_of.isoformat(),
                "total_cash_satang": state.total_cash,
                "pending_decisions": pending,
                "ai_mode": "llm" if llm_settings.uses_llm and not llm_settings.problem
                           else "offline",
            }

    @app.get("/cashflow", dependencies=guarded)
    def cashflow(
        horizon_days: Annotated[int, Query(ge=7, le=400)] = 92,
        income_change: IncomeChange = 0,
    ) -> dict[str, Any]:
        with locked() as s:
            state = _what_if(s.state, income_change)
        forecast = forecast_cash_flow(state, horizon_days)
        report = check_feasibility(state, horizon_days, planned=forecast)
        return {
            "hypothetical": income_change != 0,
            "as_of": state.as_of.isoformat(),
            "status": report.status.value,
            "first_shortfall_on": _iso(report.first_shortfall_on),
            "max_shortfall_satang": report.max_shortfall,
            "needs_reserves": report.needs_reserves,
            "essential_shortfall_on": _iso(report.essential_shortfall_on),
            "essential_shortfall_satang": report.essential_shortfall,
            "total_cash_satang": state.total_cash,
            "min_unallocated_satang": report.min_unallocated,
            "min_unallocated_on": _iso(report.min_unallocated_on),
            "closing_envelopes_satang": sum(forecast.closing_envelopes.values()),
            "days": [
                {"on": d.on.isoformat(), "unallocated_satang": d.unallocated,
                 "total_cash_satang": d.total_cash}
                for d in forecast.days
            ],
            "months": [m.model_dump() for m in monthly_summary(forecast)],
            "events": [
                {"on": e.on.isoformat(), "kind": e.kind.value, "name": e.name,
                 "amount_satang": e.amount}
                for d in forecast.days for e in d.events
            ],
        }

    @app.get("/plans", dependencies=guarded)
    def plans(
        horizon_months: Annotated[int, Query(ge=1, le=24)] = 12,
        income_change: IncomeChange = 0,
    ) -> dict[str, Any]:
        with locked() as s:
            state = _what_if(s.state, income_change)
        result = generate_plans(state, None, horizon_months)
        feasibility = result.feasibility
        return {
            "hypothetical": income_change != 0,
            "status": result.status.value,
            "position_text": explain.position(position_data(result.position))
                             if result.position else None,
            "essential_shortfall_on": _iso(feasibility.essential_shortfall_on),
            "essential_shortfall_satang": feasibility.essential_shortfall,
            "identical_notes": [note.describe() for note in result.identical],
            "plans": [_plan_summary(p) for p in result.plans],
        }

    @app.post("/plans/propose", dependencies=guarded)
    def propose(body: ProposeIn) -> dict[str, Any]:
        with locked() as s:
            result = generate_plans(s.state, None, body.horizon_months)
            if result.status is not PlanningStatus.OK:
                raise HTTPException(409, f"No plan can be proposed: {result.status.value}.")
            plan = next((p for p in result.plans if p.strategy == body.strategy), None)
            if plan is None:
                raise HTTPException(404, f"Unknown strategy {body.strategy!r}.")
            return _op(s.propose(plan, "USER"))

    @app.get("/sandbox", dependencies=guarded)
    def sandbox_view(audit_limit: Annotated[int, Query(ge=1, le=500)] = 50) -> dict[str, Any]:
        with locked() as s:
            state = s.state
            ready = [a for a in s.store.list_approvals()
                     if a["decision"] == "APPROVED" and a["used_at"] is None]
            entries = s.store.list_audit()
            return {
                "as_of": state.as_of.isoformat(),
                "total_cash_satang": state.total_cash,
                "emergency_balance_satang": state.emergency.balance if state.emergency else 0,
                "audit_intact": s.store.verify_audit_chain(),
                "pending": [
                    {"plan_id": r["id"], "label": r["label"], "strategy": r["strategy"],
                     "created_at": r["created_at"]}
                    for r in s.store.list_plans("PROPOSED")
                ],
                "ready": [
                    {"approval_id": a["id"], "plan_id": a["plan_id"],
                     "label": s.store.get_plan(a["plan_id"])["label"],
                     "decided_at": a["decided_at"]}
                    for a in ready
                ],
                "transactions": [
                    {"id": r["id"], "on": r["effective_on"], "kind": r["kind"], "ref": r["ref"],
                     "from": r["from_envelope"], "to": r["to_envelope"],
                     "amount_satang": r["amount"]}
                    for r in s.store.list_transactions()
                ],
                "audit": [
                    {"seq": e.seq, "ts": e.ts, "actor": e.actor, "action": e.action,
                     "code": e.payload.get("code", ""), "plan_id": e.payload.get("plan_id", ""),
                     "hash": e.hash[:12]}
                    for e in entries[-audit_limit:]
                ],
            }

    @app.post("/sandbox/plans/{plan_id}/decision", dependencies=guarded)
    def decide(plan_id: str, body: DecisionIn) -> dict[str, Any]:
        # The user tapped Approve or Reject in the app.
        with locked() as s:
            return _op(s.decide(plan_id, body.approve, "USER"))

    @app.post("/sandbox/approvals/{approval_id}/execute", dependencies=guarded)
    def execute(approval_id: str) -> dict[str, Any]:
        with locked() as s:
            return _op(s.execute(approval_id, "USER"))

    @app.post("/sandbox/expenses", dependencies=guarded)
    def confirm_expense(body: ExpenseIn) -> dict[str, Any]:
        with locked() as s:
            due = body.due_on or s.state.as_of
            return _op(s.confirm_expense(body.name, thb(body.amount_thb), due))

    @app.post("/sandbox/reserve/withdraw", dependencies=guarded)
    def withdraw(body: WithdrawIn) -> dict[str, Any]:
        with locked() as s:
            return _op(s.withdraw_reserve(thb(body.amount_thb)))

    @app.post("/sandbox/advance", dependencies=guarded)
    def advance(body: AdvanceIn) -> dict[str, Any]:
        with locked() as s:
            return _op(s.advance(body.days))

    @app.post("/sandbox/reset", dependencies=guarded)
    def reset() -> dict[str, Any]:
        with locked() as s:
            return _op(s.reset(load_state(profile_path)))

    @app.post("/chat", dependencies=guarded)
    def chat(body: ChatIn) -> dict[str, Any]:
        with locked() as s:
            hypothetical = body.income_change != 0
            state = _what_if(s.state, body.income_change)
            context = AgentContext(state, None if hypothetical else s)
            past = [(t.role, t.text) for t in body.history]
            return _reply(agent.reply(context, body.message, past))

    @app.get("/rewards", dependencies=guarded)
    def rewards() -> dict[str, Any]:
        with locked() as s:
            return s.rewards.status()

    @app.post("/rewards/opt-in", dependencies=guarded)
    def rewards_opt_in(body: OptInIn) -> dict[str, Any]:
        with locked() as s:
            s.rewards.set_opt_in(body.opted_in)
            return s.rewards.status()

    @app.post("/rewards/review", dependencies=guarded)
    def rewards_review() -> dict[str, Any]:
        with locked() as s:
            recorded = s.rewards.record_review()
            return {"recorded": recorded, "status": s.rewards.status()}

    @app.post("/rewards/pause", dependencies=guarded)
    def rewards_pause() -> dict[str, Any]:
        with locked() as s:
            s.rewards.pause_streaks()
            return s.rewards.status()

    @app.post("/rewards/resume", dependencies=guarded)
    def rewards_resume() -> dict[str, Any]:
        with locked() as s:
            s.rewards.resume_streaks()
            return s.rewards.status()

    return app


__all__ = ["create_app"]
