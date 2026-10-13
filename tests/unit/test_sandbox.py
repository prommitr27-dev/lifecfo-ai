from datetime import UTC, date, datetime

import pytest

from lifecfo.database import Store
from lifecfo.domain import FixedClock, thb
from lifecfo.optimization import generate_plans, state_fingerprint
from lifecfo.services import SandboxService
from lifecfo.services.sandbox import AGENT
from tests.conftest import with_income


@pytest.fixture
def service(demo_state) -> SandboxService:
    clock = FixedClock(datetime(2026, 11, 1, 2, 0, tzinfo=UTC))
    svc = SandboxService(Store(), clock)
    svc.reset(demo_state)
    return svc


def plan_for(service, strategy="BALANCED"):
    return next(p for p in generate_plans(service.state).plans if p.strategy == strategy)


def approved(service, strategy="BALANCED") -> str:
    plan_id = service.propose(plan_for(service, strategy), AGENT).data["plan_id"]
    return service.decide(plan_id, True).data["approval_id"]


def actions(service) -> list[str]:
    return [entry.action for entry in service.store.list_audit()]


def test_happy_path_propose_approve_execute(service):
    before = service.state
    proposed = service.propose(plan_for(service), AGENT)
    assert proposed.ok and proposed.code == "PROPOSED"
    assert service.state == before  # proposing changes nothing

    decided = service.decide(proposed.data["plan_id"], True)
    assert decided.ok and service.state == before  # approving changes nothing either

    executed = service.execute(decided.data["approval_id"], AGENT)
    assert executed.ok and executed.code == "EXECUTED"
    assert service.state != before
    assert service.state.total_cash == before.total_cash  # activation moves no money
    assert service.store.get_plan(proposed.data["plan_id"])["status"] == "EXECUTED"
    assert actions(service) == ["SANDBOX_RESET", "PLAN_PROPOSED", "PLAN_APPROVED",
                                "PLAN_EXECUTED"]


def test_execution_without_any_approval_is_refused(service):
    service.propose(plan_for(service), AGENT)
    before = service.state
    result = service.execute(None, AGENT)
    assert not result.ok and result.code == "NO_APPROVAL"
    assert service.execute("apr-doesnotexist", AGENT).code == "NO_APPROVAL"
    assert service.state == before
    assert actions(service).count("EXECUTION_REFUSED") == 2


def test_agent_cannot_approve(service):
    plan_id = service.propose(plan_for(service), AGENT).data["plan_id"]
    result = service.decide(plan_id, True, actor=AGENT)
    assert not result.ok and result.code == "ONLY_USER_CAN_DECIDE"
    assert service.store.get_plan(plan_id)["status"] == "PROPOSED"
    assert service.store.list_approvals() == []
    assert actions(service)[-1] == "APPROVAL_REFUSED"


def test_rejected_plan_cannot_be_executed(service):
    plan_id = service.propose(plan_for(service), AGENT).data["plan_id"]
    approval_id = service.decide(plan_id, False).data["approval_id"]
    result = service.execute(approval_id, AGENT)
    assert not result.ok and result.code == "NOT_APPROVED"


def test_duplicate_execution_changes_nothing(service):
    approval_id = approved(service)
    assert service.execute(approval_id, AGENT).ok
    after_first = service.state
    transactions = len(service.store.list_transactions())

    for _ in range(3):
        again = service.execute(approval_id, AGENT)
        assert not again.ok and again.code == "ALREADY_EXECUTED"
    assert service.state == after_first
    assert len(service.store.list_transactions()) == transactions
    assert actions(service).count("DUPLICATE_EXECUTION_BLOCKED") == 3
    # With no id given there is no unused approval left either.
    assert service.execute(None, AGENT).code == "NO_APPROVAL"


def test_approval_is_void_when_the_state_changes(service):
    approval_id = approved(service)
    with service.store.transaction():
        service.store.save_state(with_income(service.state, amount=thb(24000)))
    result = service.execute(approval_id, AGENT)
    assert not result.ok and result.code == "STALE_APPROVAL"


def test_stale_plan_cannot_be_approved(service):
    plan_id = service.propose(plan_for(service), AGENT).data["plan_id"]
    with service.store.transaction():
        service.store.save_state(with_income(service.state, amount=thb(24000)))
    result = service.decide(plan_id, True)
    assert not result.ok and result.code == "STALE_PLAN"
    assert service.store.get_plan(plan_id)["status"] == "SUPERSEDED"


def test_tampered_stored_plan_is_not_executed(service):
    approval_id = approved(service)
    plan_id = service.store.get_approval(approval_id)["plan_id"]
    other = plan_for(service, "GOAL_FIRST")
    service.store.db.execute("UPDATE plans SET plan_json = ? WHERE id = ?",
                             (other.model_dump_json(), plan_id))
    before = service.state
    result = service.execute(approval_id, AGENT)
    assert not result.ok and result.code == "PLAN_CHANGED"
    assert service.state == before


def test_invalid_plan_is_not_stored(service):
    plan = plan_for(service)
    greedy = plan.months[0].model_copy(update={"contributions": {"env-laptop": thb(25000)}})
    result = service.propose(plan.model_copy(update={"months": (greedy, *plan.months[1:])}),
                             AGENT)
    assert not result.ok and result.code == "INVALID_PLAN"
    assert service.store.list_plans() == []
    assert actions(service)[-1] == "PROPOSAL_REFUSED"


def test_proposing_the_same_plan_twice_is_idempotent(service):
    first = service.propose(plan_for(service), AGENT)
    second = service.propose(plan_for(service), AGENT)
    assert second.ok and second.code == "ALREADY_PROPOSED"
    assert second.data["plan_id"] == first.data["plan_id"]
    assert len(service.store.list_plans()) == 1


def test_decisions_apply_only_to_pending_plans(service):
    plan_id = service.propose(plan_for(service), AGENT).data["plan_id"]
    assert service.decide(plan_id, True).ok
    assert service.decide(plan_id, True).code == "NOT_PENDING"
    assert service.decide("plan-unknown", True).code == "UNKNOWN_PLAN"


def test_advancing_time_posts_transactions_and_matches_the_forecast(service):
    service.execute(approved(service, "BALANCED"), AGENT)
    start_cash = service.state.total_cash
    result = service.advance(30)  # 1 Nov .. 30 Nov
    assert result.ok and service.state.as_of == date(2026, 12, 1)

    rows = service.store.list_transactions()
    kinds = [r["kind"] for r in rows]
    assert kinds[0] == "PLAN_ACTIVATION" and kinds.count("INCOME") == 1
    income = sum(r["amount"] for r in rows if r["kind"] == "INCOME")
    spent = sum(r["amount"] for r in rows if r["kind"].endswith("EXPENSE"))
    saved = sum(r["amount"] for r in rows if r["kind"] == "SAVINGS_TRANSFER")
    assert service.state.total_cash == start_cash + income - spent
    envelopes = {e.id: e.balance for e in service.state.envelopes}
    assert envelopes["emergency"] + envelopes["env-laptop"] + envelopes["env-travel"] == (
        thb(6000) + saved)
    assert envelopes["unallocated"] >= 0


def test_advancing_is_blocked_when_cash_would_run_short(service):
    with service.store.transaction():
        service.store.save_state(with_income(service.state, amount=thb(24000)))
    before = service.state
    result = service.advance(30)
    assert not result.ok and result.code == "CASH_SHORTFALL"
    assert service.state == before and service.store.list_transactions() == []
    assert actions(service)[-1] == "ADVANCE_BLOCKED"


def test_audit_chain_detects_tampering(service):
    service.execute(approved(service), AGENT)
    assert service.store.verify_audit_chain()
    entries = service.store.list_audit()
    assert entries[-1].payload["state_hash_after"] == state_fingerprint(service.state)
    assert all(entry.ts == "2026-11-01T02:00:00+00:00" for entry in entries)

    service.store.db.execute("UPDATE audit SET actor = 'USER' WHERE action = 'PLAN_PROPOSED'")
    assert not service.store.verify_audit_chain()


def test_audit_chain_detects_a_deleted_entry(service):
    service.execute(approved(service), AGENT)
    service.store.db.execute("DELETE FROM audit WHERE action = 'PLAN_APPROVED'")
    assert not service.store.verify_audit_chain()


def test_state_survives_reopening_the_database(tmp_path, demo_state):
    path = tmp_path / "nested" / "sandbox.db"
    first = SandboxService(Store(path))
    first.reset(demo_state)
    approval_id = approved(first)
    first.store.db.close()

    second = SandboxService(Store(path))
    assert second.state == demo_state
    assert second.execute(approval_id, AGENT).ok
    assert second.store.verify_audit_chain()
