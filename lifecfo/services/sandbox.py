"""Sandbox service: propose, approve, execute, and move time forward.

Every change to stored state goes through this class. The rules it enforces:

1. A plan is stored only if it passes `validate_plan` against the current state.
2. Only the actor "USER" can approve or reject. The agent has no way to call
   `decide`; it is wired to the buttons in the app.
3. An approval is bound to the plan's hash and the state's hash. If either has
   changed, execution is refused.
4. An approval can be used once. A repeated execution changes nothing; the
   unique idempotency key on the transaction makes that hold at database level.
5. The plan is validated again immediately before execution.
6. Every outcome, including refusals and failures, is written to the audit log.

Nothing here touches a real account. "Execution" activates the plan in the
sandbox state, and `advance` posts the scheduled cash events as sandbox
transactions.
"""

import hashlib
import sqlite3
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from lifecfo.cashflow.forecast import EventKind, forecast_cash_flow
from lifecfo.database.store import Store
from lifecfo.domain.clock import Clock, SystemClock
from lifecfo.domain.models import (
    EnvelopeKind,
    Expense,
    ExpenseCategory,
    FinancialState,
    Frequency,
)
from lifecfo.domain.money import format_thb
from lifecfo.optimization.plan import Plan, apply_plan, state_fingerprint, validate_plan
from lifecfo.rewards.service import RewardsService

USER = "USER"
AGENT = "AGENT"
SYSTEM = "SYSTEM"


@dataclass(frozen=True)
class OpResult:
    ok: bool
    code: str
    message: str
    data: dict[str, Any] = field(default_factory=dict)


class SandboxService:
    def __init__(self, store: Store, clock: Clock | None = None) -> None:
        self.store = store
        self.clock = clock or SystemClock()
        # Rewards listen to validated events only; they never change financial state.
        self.rewards = RewardsService(store, self.clock)

    def _now(self) -> str:
        return self.clock.now().isoformat(timespec="seconds")

    def _audit(self, actor: str, action: str, **payload: Any) -> None:
        self.store.append_audit(self._now(), actor, action, payload)

    def _refuse(self, actor: str, action: str, code: str, message: str, **payload: Any) -> OpResult:
        self._audit(actor, action, code=code, reason=message, **payload)
        return OpResult(False, code, message, payload)

    # --- state -------------------------------------------------------------------------

    @property
    def state(self) -> FinancialState:
        state = self.store.load_state()
        if state is None:
            raise RuntimeError("sandbox has no state; call reset() first")
        return state

    def reset(self, state: FinancialState, actor: str = USER) -> OpResult:
        """Start a fresh sandbox from `state`. Clears plans, approvals, and logs."""
        with self.store.transaction():
            self.store.clear()
            self.store.save_state(state)
            self._audit(actor, "SANDBOX_RESET", state_hash=state_fingerprint(state),
                        as_of=state.as_of.isoformat())
        return OpResult(True, "RESET", "Sandbox reset.")

    # --- propose -----------------------------------------------------------------------

    def propose(self, plan: Plan, actor: str) -> OpResult:
        state = self.state
        validation = validate_plan(state, plan)
        if not validation.ok:
            return self._refuse(actor, "PROPOSAL_REFUSED", "INVALID_PLAN",
                                "The plan failed validation and was not stored.",
                                strategy=plan.strategy, violations=list(validation.violations))

        plan_hash = plan.fingerprint()
        plan_id = f"plan-{plan_hash[:10]}"
        existing = self.store.get_plan(plan_id)
        if existing is not None:
            return OpResult(True, "ALREADY_PROPOSED", "This plan was already proposed.",
                            {"plan_id": plan_id, "status": existing["status"]})
        with self.store.transaction():
            self.store.insert_plan({
                "id": plan_id, "strategy": plan.strategy, "label": plan.label,
                "plan_json": plan.model_dump_json(), "plan_hash": plan_hash,
                "state_hash": plan.state_hash, "status": "PROPOSED", "created_at": self._now(),
            })
            self._audit(actor, "PLAN_PROPOSED", plan_id=plan_id, strategy=plan.strategy,
                        plan_hash=plan_hash, state_hash=plan.state_hash)
        return OpResult(True, "PROPOSED", "Plan stored. It needs the user's approval in the app.",
                        {"plan_id": plan_id, "status": "PROPOSED"})

    # --- decide ------------------------------------------------------------------------

    def decide(self, plan_id: str, approve: bool, actor: str = USER) -> OpResult:
        if actor != USER:
            return self._refuse(actor, "APPROVAL_REFUSED", "ONLY_USER_CAN_DECIDE",
                                "Only the user can approve or reject a plan.", plan_id=plan_id)
        row = self.store.get_plan(plan_id)
        if row is None:
            return self._refuse(actor, "APPROVAL_REFUSED", "UNKNOWN_PLAN",
                                "No such plan.", plan_id=plan_id)
        if row["status"] != "PROPOSED":
            return self._refuse(actor, "APPROVAL_REFUSED", "NOT_PENDING",
                                f"Plan is {row['status']}, not waiting for a decision.",
                                plan_id=plan_id)
        if approve and row["state_hash"] != state_fingerprint(self.state):
            with self.store.transaction():
                self.store.set_plan_status(plan_id, "SUPERSEDED")
                self._audit(actor, "APPROVAL_REFUSED", code="STALE_PLAN", plan_id=plan_id,
                            reason="The financial state changed after the plan was made.")
            return OpResult(False, "STALE_PLAN",
                            "Your finances changed after this plan was made. Generate a new plan.",
                            {"plan_id": plan_id})

        decided_at = self._now()
        decision = "APPROVED" if approve else "REJECTED"
        digest = hashlib.sha256(f"{row['plan_hash']}|{decided_at}".encode()).hexdigest()
        approval_id = f"apr-{digest[:10]}"
        with self.store.transaction():
            self.store.insert_approval({
                "id": approval_id, "plan_id": plan_id, "plan_hash": row["plan_hash"],
                "state_hash": row["state_hash"], "decision": decision, "decided_at": decided_at,
            })
            self.store.set_plan_status(plan_id, decision)
            self._audit(actor, f"PLAN_{decision}", plan_id=plan_id, approval_id=approval_id,
                        plan_hash=row["plan_hash"], state_hash=row["state_hash"])
        if approve:
            self.rewards.on_plan_approved(plan_id)
        return OpResult(True, decision, f"Plan {decision.lower()}.",
                        {"plan_id": plan_id, "approval_id": approval_id})

    # --- execute -----------------------------------------------------------------------

    def execute(self, approval_id: str | None, actor: str) -> OpResult:
        """Activate an approved plan. `approval_id=None` means the latest unused approval."""
        approval = (self.store.get_approval(approval_id) if approval_id
                    else self.store.latest_usable_approval())
        if approval is None:
            return self._refuse(actor, "EXECUTION_REFUSED", "NO_APPROVAL",
                                "There is no approved plan to execute. The user must approve "
                                "a plan in the app first.", approval_id=approval_id)
        approval_id = approval["id"]
        plan_id = approval["plan_id"]
        if approval["decision"] != "APPROVED":
            return self._refuse(actor, "EXECUTION_REFUSED", "NOT_APPROVED",
                                "The user rejected this plan.", approval_id=approval_id,
                                plan_id=plan_id)
        if approval["used_at"] is not None:
            return self._refuse(actor, "DUPLICATE_EXECUTION_BLOCKED", "ALREADY_EXECUTED",
                                "This approval was already used. Nothing was changed.",
                                approval_id=approval_id, plan_id=plan_id)

        row = self.store.get_plan(plan_id)
        plan = Plan.model_validate_json(row["plan_json"])
        if plan.fingerprint() != approval["plan_hash"]:
            return self._refuse(actor, "EXECUTION_REFUSED", "PLAN_CHANGED",
                                "The stored plan does not match what was approved.",
                                approval_id=approval_id, plan_id=plan_id)
        state = self.state
        before = state_fingerprint(state)
        if before != approval["state_hash"]:
            return self._refuse(actor, "EXECUTION_REFUSED", "STALE_APPROVAL",
                                "Your finances changed after the approval. Approve a new plan.",
                                approval_id=approval_id, plan_id=plan_id)
        validation = validate_plan(state, plan)
        if not validation.ok:
            return self._refuse(actor, "EXECUTION_REFUSED", "INVALID_PLAN",
                                "The plan no longer passes validation.",
                                approval_id=approval_id, plan_id=plan_id,
                                violations=list(validation.violations))

        new_state = apply_plan(state, plan)
        now = self._now()
        try:
            with self.store.transaction():
                self.store.insert_transaction({
                    "idempotency_key": f"execute:{approval_id}", "kind": "PLAN_ACTIVATION",
                    "ref": plan_id, "from_envelope": None, "to_envelope": None, "amount": 0,
                    "effective_on": state.as_of.isoformat(), "plan_id": plan_id,
                    "created_at": now,
                })
                self.store.save_state(new_state)
                self.store.mark_approval_used(approval_id, now)
                self.store.set_plan_status(plan_id, "EXECUTED")
                self._audit(actor, "PLAN_EXECUTED", approval_id=approval_id, plan_id=plan_id,
                            strategy=plan.strategy, state_hash_before=before,
                            state_hash_after=state_fingerprint(new_state))
        except sqlite3.IntegrityError:
            return self._refuse(actor, "DUPLICATE_EXECUTION_BLOCKED", "ALREADY_EXECUTED",
                                "This approval was already used. Nothing was changed.",
                                approval_id=approval_id, plan_id=plan_id)
        self.rewards.on_state_changed()
        return OpResult(True, "EXECUTED",
                        f"The {plan.label} plan is now active in the sandbox.",
                        {"approval_id": approval_id, "plan_id": plan_id,
                         "strategy": plan.label})

    # --- time --------------------------------------------------------------------------

    def advance(self, days: int, actor: str = USER) -> OpResult:
        """Post the scheduled cash events of the next `days` days as sandbox transactions."""
        if days < 1:
            return OpResult(False, "INVALID_DAYS", "days must be at least 1")
        state = self.state
        forecast = forecast_cash_flow(state, days)
        if forecast.max_shortfall > 0:
            return self._refuse(
                actor, "ADVANCE_BLOCKED", "CASH_SHORTFALL",
                f"Cash would run short on {forecast.first_shortfall_on}. Replan first.",
                first_shortfall_on=forecast.first_shortfall_on.isoformat(),
                shortfall=forecast.max_shortfall)

        unallocated_id = state.unallocated.id
        debt_paid: dict[str, int] = {}
        now = self._now()
        rows = []
        for day in forecast.days:
            for event in day.events:
                is_income = event.kind is EventKind.INCOME
                is_transfer = event.kind is EventKind.SAVINGS_TRANSFER
                if event.kind is EventKind.DEBT_MINIMUM:
                    debt_paid[event.ref_id] = debt_paid.get(event.ref_id, 0) + event.amount
                rows.append({
                    "idempotency_key": f"{event.kind.value}:{event.ref_id}:{event.on.isoformat()}",
                    "kind": event.kind.value, "ref": event.ref_id,
                    "from_envelope": None if is_income else unallocated_id,
                    "to_envelope": (unallocated_id if is_income
                                    else event.envelope_id if is_transfer else None),
                    "amount": event.amount, "effective_on": event.on.isoformat(),
                    "plan_id": None, "created_at": now,
                })

        envelopes = tuple(
            e.model_copy(update={"balance": (forecast.days[-1].unallocated if e.id == unallocated_id
                                             else forecast.closing_envelopes[e.id])})
            for e in state.envelopes
        )
        debts = tuple(
            d.model_copy(update={"balance": d.balance - debt_paid.get(d.id, 0)})
            for d in state.debts
        )
        new_state = state.model_copy(update={
            "as_of": state.as_of + timedelta(days=days), "envelopes": envelopes, "debts": debts,
        })
        try:
            with self.store.transaction():
                for row in rows:
                    self.store.insert_transaction(row)
                self.store.save_state(new_state)
                self._audit(actor, "TIME_ADVANCED", days=days,
                            from_date=state.as_of.isoformat(),
                            to_date=new_state.as_of.isoformat(), transactions=len(rows),
                            state_hash_before=state_fingerprint(state),
                            state_hash_after=state_fingerprint(new_state))
        except sqlite3.IntegrityError:
            return self._refuse(actor, "ADVANCE_BLOCKED", "DUPLICATE_TRANSACTION",
                                "These events were already posted. Nothing was changed.")
        self.rewards.on_state_changed()
        return OpResult(True, "ADVANCED",
                        f"Posted {len(rows)} transactions; the sandbox date is now "
                        f"{new_state.as_of}.",
                        {"transactions": len(rows), "as_of": new_state.as_of.isoformat()})

    # --- confirmed shocks and reserve withdrawals (rules D4, C9) -------------------------

    def confirm_expense(self, name: str, amount: int, on_date, actor: str = USER) -> OpResult:
        """Record an unexpected expense the user says has really happened.

        It becomes an essential obligation in the sandbox state, so every earlier
        proposal and approval no longer matches the state and must be redone. Only
        the user can confirm a real event; simulations never reach this method.
        """
        if actor != USER:
            return self._refuse(actor, "SHOCK_REFUSED", "ONLY_USER_CAN_CONFIRM",
                                "Only the user can confirm that an expense happened.")
        state = self.state
        if amount <= 0:
            return self._refuse(actor, "SHOCK_REFUSED", "INVALID_AMOUNT",
                                "The amount must be positive.")
        if on_date < state.as_of:
            return self._refuse(actor, "SHOCK_REFUSED", "IN_THE_PAST",
                                "The sandbox has already posted that date.")
        shock_id = f"shock-{len([e for e in state.expenses if e.id.startswith('shock-')]) + 1}"
        expense = Expense(id=shock_id, name=f"Confirmed: {name}"[:80],
                          category=ExpenseCategory.ESSENTIAL, amount=amount,
                          frequency=Frequency.ONE_TIME, on_date=on_date)
        new_state = state.model_copy(update={"expenses": (*state.expenses, expense)})
        with self.store.transaction():
            self.store.save_state(new_state)
            self._audit(actor, "SHOCK_CONFIRMED", shock_id=shock_id, amount=amount,
                        due_on=on_date.isoformat(),
                        state_hash_before=state_fingerprint(state),
                        state_hash_after=state_fingerprint(new_state))
        self.rewards.on_shock_confirmed(shock_id)
        return OpResult(True, "SHOCK_CONFIRMED",
                        f"{format_thb(amount)} due {on_date} recorded. Earlier proposals no "
                        "longer match your finances; generate a recovery plan.",
                        {"shock_id": shock_id})

    def withdraw_reserve(self, amount: int, actor: str = USER) -> OpResult:
        """Move money from the emergency reserve to unallocated cash, on the user's word."""
        if actor != USER:
            return self._refuse(actor, "WITHDRAWAL_REFUSED", "ONLY_USER_CAN_WITHDRAW",
                                "Only the user can withdraw from the emergency reserve.")
        state = self.state
        reserve = state.emergency
        if reserve is None or amount <= 0 or amount > reserve.balance:
            return self._refuse(actor, "WITHDRAWAL_REFUSED", "INVALID_AMOUNT",
                                "The amount must be positive and no more than the reserve.",
                                amount=amount)
        envelopes = tuple(
            e.model_copy(update={"balance": e.balance - amount}) if e.kind is EnvelopeKind.EMERGENCY
            else e.model_copy(update={"balance": e.balance + amount})
            if e.kind is EnvelopeKind.UNALLOCATED else e
            for e in state.envelopes)
        new_state = state.model_copy(update={"envelopes": envelopes})
        now = self._now()
        with self.store.transaction():
            self.store.insert_transaction({
                "idempotency_key": f"withdraw:{now}:{amount}", "kind": "RESERVE_WITHDRAWAL",
                "ref": reserve.id, "from_envelope": reserve.id,
                "to_envelope": state.unallocated.id, "amount": amount,
                "effective_on": state.as_of.isoformat(), "plan_id": None, "created_at": now})
            self.store.save_state(new_state)
            target = new_state.emergency_target
            self._audit(actor, "RESERVE_WITHDRAWN", amount=amount,
                        reserve_after=reserve.balance - amount,
                        gap_after=max(0, target - (reserve.balance - amount)),
                        state_hash_before=state_fingerprint(state),
                        state_hash_after=state_fingerprint(new_state))
        return OpResult(True, "RESERVE_WITHDRAWN",
                        f"{format_thb(amount)} moved from the emergency reserve. It now holds "
                        f"{format_thb(reserve.balance - amount)}; the gap to its target is "
                        f"{format_thb(max(0, target - (reserve.balance - amount)))}.",
                        {"reserve_after": reserve.balance - amount})
