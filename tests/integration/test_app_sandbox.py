"""End-to-end through the UI: propose, approve, execute, post transactions, audit."""

import os
from pathlib import Path

from streamlit.testing.v1 import AppTest

from lifecfo.database import Store

APP = Path(__file__).resolve().parents[2] / "app" / "main.py"


def open_view(view: str) -> AppTest:
    at = AppTest.from_file(str(APP), default_timeout=60)
    at.session_state["view"] = view
    return at.run()


def button(at: AppTest, label_part: str):
    return next(b for b in at.button if label_part in b.label)


def store() -> Store:
    return Store(os.environ["LIFECFO_DB_PATH"])


def test_user_approves_and_executes_a_plan_through_the_app():
    cfo = open_view("Personal CFO")
    assert not cfo.exception
    button(cfo, "Request approval").click().run()
    assert any("PROPOSED" in s.value for s in cfo.success)

    sandbox = open_view("Sandbox")
    assert not sandbox.exception
    button(sandbox, "Approve").click().run()
    assert any("APPROVED" in s.value for s in sandbox.success)

    button(sandbox, "Execute in sandbox").click().run()
    assert any("EXECUTED" in s.value for s in sandbox.success)
    assert not [b for b in sandbox.button if "Execute in sandbox" in b.label]

    button(sandbox, "Post scheduled transactions").click().run()
    assert any("ADVANCED" in s.value for s in sandbox.success)

    db = store()
    actions = [entry.action for entry in db.list_audit()]
    assert actions == ["SANDBOX_RESET", "PLAN_PROPOSED", "PLAN_APPROVED", "PLAN_EXECUTED",
                       "TIME_ADVANCED"]
    assert [e.actor for e in db.list_audit()][1:4] == ["USER", "USER", "USER"]
    assert db.verify_audit_chain()
    assert any(r["kind"] == "SAVINGS_TRANSFER" for r in db.list_transactions())
    assert db.load_state().as_of.isoformat() == "2026-12-01"


def test_rejecting_leaves_nothing_to_execute():
    cfo = open_view("Personal CFO")
    button(cfo, "Request approval").click().run()
    sandbox = open_view("Sandbox")
    button(sandbox, "Reject").click().run()
    assert any("REJECTED" in s.value for s in sandbox.success)
    assert not [b for b in sandbox.button if "Execute in sandbox" in b.label]
    assert store().list_plans()[0]["status"] == "REJECTED"


def test_what_if_view_cannot_propose():
    cfo = open_view("Personal CFO")
    cfo.sidebar.slider[0].set_value(-20).run()
    assert not cfo.exception
    assert not [b for b in cfo.button if "Request approval" in b.label]
    assert any("what-if view" in i.value for i in cfo.info)
    assert store().list_plans() == []


def test_chat_can_propose_but_execution_waits_for_the_user():
    chat = open_view("AI CFO chat")
    chat.chat_input[0].set_value("Propose the Goal First plan").run()
    chat.chat_input[0].set_value("Execute the plan").run()
    assert not chat.exception
    text = " ".join(m.value for m in chat.markdown)
    assert "waiting for your decision" in text and "Nothing was executed (NO_APPROVAL)" in text

    db = store()
    assert db.list_plans()[0]["status"] == "PROPOSED"
    assert [e.action for e in db.list_audit()][-1] == "EXECUTION_REFUSED"

    sandbox = open_view("Sandbox")
    button(sandbox, "Approve").click().run()
    chat = open_view("AI CFO chat")
    chat.chat_input[0].set_value("Execute the approved plan").run()
    assert "executed under your approval" in " ".join(m.value for m in chat.markdown)
    assert store().list_plans()[0]["status"] == "EXECUTED"


def test_reset_returns_the_sandbox_to_the_demo_profile():
    cfo = open_view("Personal CFO")
    button(cfo, "Request approval").click().run()
    sandbox = open_view("Sandbox")
    button(sandbox, "Reset sandbox").click().run()
    db = store()
    assert db.list_plans() == []
    assert [e.action for e in db.list_audit()] == ["SANDBOX_RESET"]
