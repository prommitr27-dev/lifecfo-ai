from pathlib import Path

import pytest

from lifecfo.domain.loader import load_state
from lifecfo.domain.models import FinancialState

ROOT = Path(__file__).resolve().parents[1]
DEMO_PROFILE = ROOT / "data" / "synthetic" / "profile_demo.yaml"


@pytest.fixture(autouse=True)
def no_llm_provider(monkeypatch):
    """Tests never reach a real provider, whatever the developer's environment says."""
    monkeypatch.setenv("LIFECFO_LLM_PROVIDER", "none")


@pytest.fixture
def demo_state() -> FinancialState:
    return load_state(DEMO_PROFILE)


def with_income(state: FinancialState, **changes) -> FinancialState:
    """Copy of `state` with the first income source modified."""
    first, *rest = state.incomes
    return state.model_copy(update={"incomes": (first.model_copy(update=changes), *rest)})
