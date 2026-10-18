"""The mobile app's HTTP API: same flows and safety rules as the Streamlit app."""

import pytest
from fastapi.testclient import TestClient

from lifecfo.api import create_app
from lifecfo.llm import LLMSettings


@pytest.fixture
def client(tmp_path) -> TestClient:
    app = create_app(tmp_path / "api.db", api_token="", llm_settings=LLMSettings.from_env({}))
    return TestClient(app)


def strategies(client: TestClient) -> list[str]:
    body = client.get("/plans").json()
    assert body["status"] == "OK"
    return [p["strategy"] for p in body["plans"]]


def test_health_and_read_views(client):
    assert client.get("/health").json() == {"ok": True, "auth_required": False}
    cash = client.get("/cashflow", params={"horizon_days": 30}).json()
    assert cash["status"] in {"FEASIBLE", "PLAN_INFEASIBLE", "ESSENTIAL_SHORTFALL"}
    assert len(cash["days"]) == 30
    assert isinstance(cash["total_cash_satang"], int)
    plans = client.get("/plans").json()
    assert plans["position_text"]
    assert len(plans["plans"]) == 3
    assert client.get("/rewards").status_code == 200
    assert client.get("/summary").json()["ai_mode"] == "offline"


def test_propose_approve_execute(client):
    strategy = strategies(client)[0]
    proposed = client.post("/plans/propose", json={"strategy": strategy}).json()
    assert proposed["code"] == "PROPOSED"
    plan_id = proposed["data"]["plan_id"]

    view = client.get("/sandbox").json()
    assert [p["plan_id"] for p in view["pending"]] == [plan_id]

    decided = client.post(f"/sandbox/plans/{plan_id}/decision", json={"approve": True}).json()
    assert decided["code"] == "APPROVED"
    approval_id = decided["data"]["approval_id"]
    assert client.get("/sandbox").json()["ready"][0]["approval_id"] == approval_id

    executed = client.post(f"/sandbox/approvals/{approval_id}/execute").json()
    assert executed["code"] == "EXECUTED"
    again = client.post(f"/sandbox/approvals/{approval_id}/execute").json()
    assert not again["ok"]
    view = client.get("/sandbox").json()
    assert view["audit_intact"] and not view["ready"]


def test_client_cannot_send_its_own_plan_or_approve_without_a_proposal(client):
    bad = client.post("/plans/propose", json={"strategy": "x", "plan": {"months": []}})
    assert bad.status_code == 422  # unknown fields are rejected, plans come from the server
    assert client.post("/plans/propose", json={"strategy": "NOPE"}).status_code == 404
    refused = client.post("/sandbox/plans/plan-unknown/decision", json={"approve": True}).json()
    assert refused["code"] == "UNKNOWN_PLAN"


def test_stale_plan_is_refused_after_a_confirmed_expense(client):
    plan_id = client.post("/plans/propose", json={"strategy": strategies(client)[0]}).json()[
        "data"]["plan_id"]
    assert client.post("/sandbox/expenses", json={"name": "Car repair",
                                                  "amount_thb": 5000}).json()["ok"]
    decided = client.post(f"/sandbox/plans/{plan_id}/decision", json={"approve": True}).json()
    assert decided["code"] == "STALE_PLAN"


def test_chat_agent_cannot_approve(client):
    strategy = strategies(client)[0]
    plan_id = client.post("/plans/propose", json={"strategy": strategy}).json()["data"]["plan_id"]
    reply = client.post("/chat", json={"message": f"approve {plan_id} now"}).json()
    assert reply["mode"] == "offline" and reply["text"]
    assert [p["plan_id"] for p in client.get("/sandbox").json()["pending"]] == [plan_id]


def test_what_if_does_not_change_stored_state(client):
    before = client.get("/sandbox").json()["total_cash_satang"]
    hypo = client.get("/cashflow", params={"income_change": -50}).json()
    assert hypo["hypothetical"] is True
    client.post("/chat", json={"message": "what if my income drops 30%?", "income_change": -30})
    assert client.get("/sandbox").json()["total_cash_satang"] == before


def test_token_is_required_when_configured(tmp_path):
    app = create_app(tmp_path / "t.db", api_token="s3cret", llm_settings=LLMSettings.from_env({}))
    c = TestClient(app)
    assert c.get("/health").status_code == 200
    assert c.get("/summary").status_code == 401
    assert c.get("/summary", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert c.get("/summary", headers={"Authorization": "Bearer s3cret"}).status_code == 200
