from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from aimo_gateway.app import create_app
from aimo_gateway.planner import DemoSource, demo_catalog
from aimo_gateway.service import Gateway
from aimo_gateway.store import Store


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    def clock():
        return datetime(2026, 11, 14, 8, tzinfo=timezone.utc)
    gateway = Gateway(Store(tmp_path / "workspace.sqlite", "fixture"), demo_catalog(), DemoSource(clock), clock, "http://testserver")
    credentials = gateway.auth.bootstrap()
    app = create_app(gateway)
    with TestClient(app) as client:
        yield gateway, app.state.workspace, client, credentials


def login(client, credentials, actor):
    response = client.post("/auth/login", json={"loginToken": credentials[actor]}, headers={"Origin": "http://testserver"})
    assert response.status_code == 200
    session = client.get("/workspace/session").json()
    return {"Origin": "http://testserver", "X-CSRF-Token": session["csrfToken"]}


def test_workspace_requires_actual_human_approval(setup):
    gateway, workspace, client, credentials = setup
    headers = login(client, credentials, "chef")
    data = {"brief": "Savory vegetable pies for 100 wedding guests", "servings": 100, "deliveryDate": "2026-11-16",
            "maxGrossMinor": 50000, "dietaryConfirmed": True, "dietaryRequirements": [], "excludedAllergens": [],
            "pantry": {}, "preference": "balanced", "scenario": "shortage", "autoCommit": False}
    response = client.post("/workspace/jobs", json=data, headers={**headers, "X-Request-Key": str(uuid4())})
    assert response.status_code == 201, response.text
    job_id = response.json()["id"]
    workspace.pool.shutdown(wait=True)
    job = client.get("/workspace/jobs/" + job_id).json()
    assert job["state"] == "awaiting_approval", job
    assert "demo-flour" not in [line["productId"] for line in job["plan"]["lines"]]
    assert "demo-flour-alt" in [line["productId"] for line in job["plan"]["lines"]]
    assert job["plan"]["comparison"]["carbonCoverage"] > 0
    assert client.post(f"/workspace/jobs/{job_id}/decision", json={"decision": "approve"}, headers=headers).status_code == 403
    headers = login(client, credentials, "manager")
    assert client.post(f"/workspace/jobs/{job_id}/decision", json={"decision": "approve"}, headers=headers).status_code == 200
    result = client.post(f"/workspace/jobs/{job_id}/commit", json={}, headers=headers)
    assert result.status_code == 200 and result.json()["state"] == "ordered_mock", result.text
    assert result.json()["order"]["committedBy"] == "manager"
    assert client.get(f"/workspace/jobs/{job_id}/export").json()["events"]


def test_workspace_rejects_agent_creation_and_bad_inputs(setup):
    gateway, workspace, client, credentials = setup
    headers = {"Authorization": "Bearer " + credentials["buyer-agent"]}
    assert client.get("/workspace/session", headers=headers).status_code == 401
    headers = login(client, credentials, "chef")
    assert client.post("/workspace/jobs", json={"approved": True}, headers={**headers, "X-Request-Key": str(uuid4())}).status_code == 422


def test_workspace_idempotent_creation(setup):
    gateway, workspace, client, credentials = setup
    headers = login(client, credentials, "chef")
    headers["X-Request-Key"] = str(uuid4())
    data = {"brief": "12 litres lactose-free milk", "servings": 1, "deliveryDate": "2026-11-16", "maxGrossMinor": 10000,
            "dietaryConfirmed": True, "dietaryRequirements": ["lactose_free"], "excludedAllergens": [], "pantry": {}, "preference": "price", "autoCommit": False}
    first = client.post("/workspace/jobs", json=data, headers=headers)
    second = client.post("/workspace/jobs", json=data, headers=headers)
    assert first.status_code == second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    data["servings"] = 2
    assert client.post("/workspace/jobs", json=data, headers=headers).status_code == 409


def test_session_refresh_is_stable_and_logout_is_final(setup):
    _, _, client, credentials = setup
    headers = login(client, credentials, "chef")
    assert client.get("/workspace/session").json()["csrfToken"] == headers["X-CSRF-Token"]
    assert client.post("/workspace/logout", json={}, headers=headers).status_code == 200
    assert client.get("/workspace/session").status_code == 401


def test_processing_failure_cancels_underlying_request(setup, monkeypatch):
    gateway, workspace, client, credentials = setup
    def failure(*args):
        raise RuntimeError("private details")
    monkeypatch.setattr(workspace.agent, "plan", failure)
    headers = login(client, credentials, "chef")
    data = {"brief": "Savory pies", "servings": 100, "deliveryDate": "2026-11-16", "maxGrossMinor": 10000,
            "dietaryConfirmed": True, "dietaryRequirements": [], "excludedAllergens": [], "pantry": {}, "preference": "balanced", "autoCommit": False}
    job = client.post("/workspace/jobs", json=data, headers={**headers, "X-Request-Key": str(uuid4())}).json()
    workspace.pool.shutdown(wait=True)
    result = client.get("/workspace/jobs/" + job["id"]).json()
    assert result["state"] == "failed" and "private details" not in result["error"]
    with gateway.store.transaction() as connection:
        assert gateway.store.get(connection, "request", job["requestId"])["status"] == "cancelled"
    assert client.post(f"/workspace/jobs/{job['id']}/commit", json={}, headers=headers).status_code == 409