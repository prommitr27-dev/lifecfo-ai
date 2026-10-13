from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[2] / "app" / "main.py"


def test_app_renders_baseline_as_feasible():
    at = AppTest.from_file(str(APP), default_timeout=30).run()
    assert not at.exception
    assert any("FEASIBLE" in s.value for s in at.success)


def test_app_flags_income_cut_as_infeasible():
    at = AppTest.from_file(str(APP), default_timeout=30).run()
    at.sidebar.slider[0].set_value(-20).run()
    assert not at.exception
    assert any("PLAN_INFEASIBLE" in w.value for w in at.warning)
