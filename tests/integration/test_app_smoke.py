import os
from pathlib import Path

from streamlit.testing.v1 import AppTest

from lifecfo.services import SandboxService

APP = Path(__file__).resolve().parents[2] / "app" / "main.py"


def run_app(view: str | None = None) -> AppTest:
    at = AppTest.from_file(str(APP), default_timeout=60)
    if view is not None:
        at.session_state["view"] = view
    return at.run()


def test_home_shows_money_bills_and_goals():
    at = run_app()
    assert not at.exception
    page = " ".join(h.proto.body for h in at.get("html"))
    assert "Yours to spend" in page and "funded every day" in page
    assert "Rent" in page and "Emergency fund" in page and "New laptop" in page


def test_home_buttons_open_the_detail_tabs():
    at = run_app()
    at.button(key="home-bills").click().run()
    assert not at.exception
    assert at.session_state["view"] == "Cash flow"
    assert any("FEASIBLE" in s.value for s in at.success)


def test_app_renders_baseline_as_feasible():
    at = run_app("Cash flow")
    assert not at.exception
    assert any("FEASIBLE" in s.value for s in at.success)


def save_income_change(at, percent: int) -> None:
    at.sidebar.slider[0].set_value(percent).run()
    next(b for b in at.button if "real income" in b.label).click().run()


def test_app_flags_income_cut_as_infeasible():
    at = run_app("Cash flow")
    at.sidebar.slider[0].set_value(-20).run()
    assert not at.exception
    assert not any("PLAN_INFEASIBLE" in w.value for w in at.warning)  # not saved yet
    save_income_change(at, -20)
    assert not at.exception
    assert any("PLAN_INFEASIBLE" in w.value for w in at.warning)


def test_personal_cfo_view_shows_three_validated_plans():
    at = run_app("Personal CFO")
    assert not at.exception
    assert any("3 plans generated" in s.value for s in at.success)
    labels = set(at.dataframe[0].value["Strategy"])
    assert labels == {"Safety First", "Balanced", "Goal First"}


def test_personal_cfo_view_reports_essential_shortfall_without_a_plan():
    at = run_app("Personal CFO")
    save_income_change(at, -50)
    assert not at.exception
    assert any("ESSENTIAL_SHORTFALL" in e.value for e in at.error)
    assert len(at.dataframe) == 0


def test_chat_view_answers_offline_with_tool_trace():
    at = run_app("AI CFO chat")
    assert not at.exception
    at.chat_input[0].set_value("What if my income drops 20%?").run()
    assert not at.exception
    text = " ".join(m.value for m in at.markdown)
    assert "Hypothetical scenario" in text and "24,000 THB" in text
    assert any("Offline engine" in c.value for c in at.caption)


def test_public_mode_gives_each_visitor_a_private_sandbox(monkeypatch):
    monkeypatch.setenv("LIFECFO_SANDBOX", "session")
    first = run_app("Sandbox")
    assert not first.exception
    store = first.session_state["visitor_store"]
    start = store.load_state().as_of
    assert SandboxService(store).advance(30).ok

    second = run_app("Sandbox")
    assert not second.exception
    other = second.session_state["visitor_store"]
    assert other is not store
    assert other.load_state().as_of == start
    assert not Path(os.environ["LIFECFO_DB_PATH"]).exists()
