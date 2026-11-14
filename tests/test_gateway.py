from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from threading import Barrier, Event
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from aimo_gateway.app import create_app
from aimo_gateway.catalog import Catalog
from aimo_gateway.service import Gateway
from aimo_gateway.store import Store
from aimo_gateway.upstream import FixtureSource


class Clock:
    def __init__(self):
        self.value = datetime(2026, 11, 14, 8, tzinfo=timezone.utc)

    def __call__(self):
        return self.value


class Harness:
    def __init__(self, path):
        self.clock = Clock()
        self.gateway = Gateway(Store(path, "fixture"), Catalog.fixture(), FixtureSource(self.clock), self.clock, "http://testserver")
        self.credentials = self.gateway.auth.bootstrap()
        self.clients, self.headers = {}, {}
        for actor in ("chef", "manager", "buyer-agent"):
            client = TestClient(create_app(self.gateway))
            self.clients[actor] = client
            if actor == "buyer-agent":
                self.headers[actor] = {"Authorization": "Bearer " + self.credentials[actor]}
            else:
                response = client.post("/auth/login", json={"loginToken": self.credentials[actor]}, headers={"Origin": "http://testserver"})
                assert response.status_code == 200, response.text
                self.headers[actor] = {"Origin": "http://testserver", "X-CSRF-Token": response.json()["csrfToken"]}

    def call(self, actor, method, path, data=None, key=None, version=None):
        headers = {**self.headers[actor], "Idempotency-Key": key or str(uuid4())}
        if version is not None:
            headers["X-Expected-Basket-Version"] = str(version)
        return self.clients[actor].request(method, path, json=data, headers=headers)

    def prepare(self, quantity=10, extra=False):
        response = self.call("chef", "POST", "/v1/requests", {
            "brief": "Restock milk", "deliverySiteId": "demo-kitchen", "requestedDeliveryDate": "2026-11-16",
            "maxGrossMinor": 100000, "constraints": {"dietaryConfirmed": True, "dietaryRequirements": [] if extra else ["lactose_free"], "excludedAllergens": []},
        })
        assert response.status_code == 201, response.text
        request = response.json()
        with self.gateway.store.transaction() as connection:
            for actor in ("manager", "buyer-agent"):
                self.gateway.auth.grant(connection, actor, request["id"])
        response = self.call("buyer-agent", "POST", f"/v1/requests/{request['id']}/baskets", {
            "lines": [{"productId": "demo-milk", "salesUnit": "CASE", "quantity": quantity}] +
                     ([{"productId": "demo-flour", "salesUnit": "BAG", "quantity": 1}] if extra else []),
        })
        assert response.status_code == 201, response.text
        basket = response.json()
        response = self.call("buyer-agent", "POST", f"/v1/baskets/{basket['id']}/evaluations", version=1)
        assert response.status_code == 201, response.text
        return request, basket, response.json()


@pytest.fixture
def harness(tmp_path):
    instance = Harness(tmp_path / "gateway.sqlite")
    yield instance
    for client in instance.clients.values():
        client.close()


def test_full_approval_order_flow(harness):
    request, basket, evaluation = harness.prepare()
    assert evaluation["outcome"] == "approval_required"
    response = harness.call("buyer-agent", "POST", "/v1/orders", {"evaluationId": evaluation["id"]})
    assert response.status_code == 409
    response = harness.call("buyer-agent", "POST", f"/v1/evaluations/{evaluation['id']}/decisions", {"decision": "approve"})
    assert response.status_code == 403
    response = harness.call("manager", "POST", f"/v1/evaluations/{evaluation['id']}/decisions", {"decision": "approve"})
    assert response.status_code == 201, response.text
    key = str(uuid4())
    order = harness.call("buyer-agent", "POST", "/v1/orders", {"evaluationId": evaluation["id"]}, key)
    assert order.status_code == 201, order.text
    assert order.json()["status"] == "ordered_mock"
    assert order.json()["totals"]["grossMinor"] == 2220
    harness.clock.value += timedelta(minutes=3)
    replay = harness.call("buyer-agent", "POST", "/v1/orders", {"evaluationId": evaluation["id"]}, key)
    assert replay.json() == order.json()
    repeated = harness.call("buyer-agent", "POST", "/v1/orders", {"evaluationId": evaluation["id"]})
    assert repeated.json()["code"] == "REQUEST_ALREADY_ORDERED"
    events = harness.call("chef", "GET", f"/v1/requests/{request['id']}/events").json()["events"]
    assert len([item for item in events if item["type"] == "order.created"]) == 1
    assert harness.call("chef", "GET", f"/v1/baskets/{basket['id']}").json()["state"] == "ordered_mock"


def test_autonomous_order(harness):
    _, _, evaluation = harness.prepare(1)
    assert evaluation["outcome"] == "allowed"
    response = harness.call("buyer-agent", "POST", "/v1/orders", {"evaluationId": evaluation["id"]})
    assert response.status_code == 201, response.text


def test_stale_edit_and_approval_invalidation(harness):
    _, basket, evaluation = harness.prepare()
    assert harness.call("manager", "POST", f"/v1/evaluations/{evaluation['id']}/decisions", {"decision": "approve"}).status_code == 201
    changed = {"lines": [{"productId": "demo-milk", "salesUnit": "CASE", "quantity": 11}]}
    assert harness.call("buyer-agent", "PUT", f"/v1/baskets/{basket['id']}", changed, version=9).status_code == 412
    assert harness.call("buyer-agent", "PUT", f"/v1/baskets/{basket['id']}", changed, version=1).status_code == 200
    response = harness.call("buyer-agent", "POST", "/v1/orders", {"evaluationId": evaluation["id"]})
    assert response.json()["code"] == "EVALUATION_SUPERSEDED"


def test_rejection_survives_noop(harness):
    _, basket, evaluation = harness.prepare(extra=True)
    assert harness.call("manager", "POST", f"/v1/evaluations/{evaluation['id']}/decisions", {"decision": "reject"}).status_code == 201
    response = harness.call("buyer-agent", "PUT", f"/v1/baskets/{basket['id']}", {"lines": list(reversed(basket["lines"]))}, version=1)
    assert response.json()["state"] == "rejected"
    assert harness.call("buyer-agent", "POST", f"/v1/baskets/{basket['id']}/evaluations", version=1).status_code == 409


def test_agent_cannot_create_human_context(harness):
    response = harness.call("buyer-agent", "POST", "/v1/requests", {
        "brief": "test", "deliverySiteId": "demo-kitchen", "requestedDeliveryDate": "2026-11-16", "maxGrossMinor": 100,
        "constraints": {"dietaryConfirmed": True, "excludedAllergens": [], "dietaryRequirements": []},
    })
    assert response.status_code == 403


def test_unknown_fields_and_idempotency_conflict(harness):
    request, _, _ = harness.prepare(1)
    value = {"lines": [{"productId": "demo-milk", "salesUnit": "CASE", "quantity": 1}]}
    endpoint = f"/v1/requests/{request['id']}/baskets"
    assert harness.call("buyer-agent", "POST", endpoint, {**value, "approved": True}).status_code == 422
    key = str(uuid4())
    assert harness.call("buyer-agent", "POST", endpoint, value, key).status_code == 201
    value["lines"][0]["quantity"] = 2
    assert harness.call("buyer-agent", "POST", endpoint, value, key).json()["code"] == "IDEMPOTENCY_CONFLICT"


def approve(harness, evaluation):
    response = harness.call("manager", "POST", f"/v1/evaluations/{evaluation['id']}/decisions", {"decision": "approve"})
    assert response.status_code == 201, response.text


def set_policy(harness, **changes):
    with harness.gateway.store.transaction() as connection:
        policy = harness.gateway.store.get(connection, "policy", "demo-customer")
        policy.update(changes)
        harness.gateway.store.put(connection, "policy", policy, "demo-customer")


@pytest.mark.parametrize("foreign", [False, True])
def test_ungranted_and_foreign_objects_are_hidden(harness, foreign):
    request, basket, evaluation = harness.prepare(1)
    order = harness.call("buyer-agent", "POST", "/v1/orders", {"evaluationId": evaluation["id"]}).json()
    with harness.gateway.store.transaction() as connection:
        principal = harness.gateway.store.get(connection, "principal", "buyer-agent")
        principal = {**principal, "id": "outsider", "customerId": "other-customer" if foreign else "demo-customer"}
        harness.gateway.store.put(connection, "principal", principal, principal["customerId"])
        token = harness.gateway.auth.issue(connection, principal, "agent")
    with TestClient(create_app(harness.gateway)) as client:
        for path in (f"/v1/requests/{request['id']}", f"/v1/baskets/{basket['id']}",
                     f"/v1/evaluations/{evaluation['id']}", f"/v1/orders/{order['id']}",
                     f"/v1/requests/{request['id']}/events"):
            response = client.get(path, headers={"Authorization": "Bearer " + token})
            assert response.status_code == 404, response.text


def test_http_csrf_and_mixed_credentials(harness):
    request, _, _ = harness.prepare(1)
    endpoint = f"/v1/requests/{request['id']}/cancel"
    for headers in ({"Origin": "http://testserver"},
                    {**harness.headers["chef"], "Origin": "https://attacker.invalid"},
                    {**harness.headers["chef"], **harness.headers["buyer-agent"]}):
        response = harness.clients["chef"].post(endpoint, headers={**headers, "Idempotency-Key": str(uuid4())})
        assert response.status_code in (401, 403)


def test_expiry_policy_change_and_missing_precondition(harness):
    _, basket, evaluation = harness.prepare(1)
    assert harness.call("buyer-agent", "POST", f"/v1/baskets/{basket['id']}/evaluations").status_code == 428
    set_policy(harness, autonomousLimitMinor=999)
    response = harness.call("buyer-agent", "POST", "/v1/orders", {"evaluationId": evaluation["id"]})
    assert response.json()["code"] == "EVALUATION_EXPIRED"
    _, _, current = harness.prepare(1)
    harness.clock.value += timedelta(seconds=121)
    assert harness.call("buyer-agent", "POST", "/v1/orders", {"evaluationId": current["id"]}).status_code == 410


def test_approval_revocation_changes_readiness(harness):
    _, basket, evaluation = harness.prepare()
    approve(harness, evaluation)
    with harness.gateway.store.transaction() as connection:
        manager = harness.gateway.store.get(connection, "principal", "manager")
        manager["revoked"] = True
        harness.gateway.store.put(connection, "principal", manager, manager["customerId"])
    assert harness.call("chef", "GET", f"/v1/baskets/{basket['id']}").json()["state"] == "expired"
    assert harness.call("buyer-agent", "POST", "/v1/orders", {"evaluationId": evaluation["id"]}).status_code == 403


def test_fresh_price_change_requires_new_evaluation(harness):
    _, _, evaluation = harness.prepare()
    approve(harness, evaluation)
    def change(data):
        product = data["price"]["products"][0]
        product["catalogPrice"].update(value=Decimal("2"), valueWithTax=Decimal("2.27"))
        product["priceWithTax"]["value"] = Decimal("2.27")
        product["tax"]["taxValue"] = Decimal("0.27")
        return data
    harness.gateway.source.transform = change
    response = harness.call("buyer-agent", "POST", "/v1/orders", {"evaluationId": evaluation["id"]})
    assert response.json()["code"] == "EVALUATION_REQUIRED"


def test_two_orders_cannot_race_daily_budget(harness):
    set_policy(harness, dailyLimitMinor=1000)
    first = harness.prepare(3)[2]
    second = harness.prepare(3)[2]
    barrier = Barrier(2)
    def synchronize(data):
        barrier.wait(timeout=5)
        return data
    harness.gateway.source.transform = synchronize
    def commit(evaluation):
        return harness.call("buyer-agent", "POST", "/v1/orders", {"evaluationId": evaluation["id"]})
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(commit, [first, second]))
    assert sorted(result.status_code for result in results) == [201, 409]
    with harness.gateway.store.transaction() as connection:
        assert harness.gateway.store.spent(connection, "demo-customer", "2026-11-14") == 666


@pytest.mark.parametrize("action", ["edit", "cancel", "revoke"])
def test_changed_authority_or_content_during_network_cannot_commit(harness, action):
    request, basket, evaluation = harness.prepare(1)
    entered, release = Event(), Event()
    def pause(data):
        entered.set()
        assert release.wait(timeout=5)
        return data
    harness.gateway.source.transform = pause
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(harness.call, "buyer-agent", "POST", "/v1/orders", {"evaluationId": evaluation["id"]})
        try:
            assert entered.wait(timeout=5)
            if action == "edit":
                replacement = {"lines": [{"productId": "demo-milk", "salesUnit": "CASE", "quantity": 2}]}
                assert harness.call("chef", "PUT", f"/v1/baskets/{basket['id']}", replacement, version=1).status_code == 200
            elif action == "cancel":
                assert harness.call("chef", "POST", f"/v1/requests/{request['id']}/cancel").status_code == 200
            else:
                with harness.gateway.store.transaction() as connection:
                    agent = harness.gateway.store.get(connection, "principal", "buyer-agent")
                    agent["revoked"] = True
                    harness.gateway.store.put(connection, "principal", agent, agent["customerId"])
        finally:
            release.set()
        response = future.result(timeout=5)
    assert response.status_code == {"edit": 412, "cancel": 409, "revoke": 401}[action], response.text
    with harness.gateway.store.transaction() as connection:
        assert connection.execute("SELECT count(*) FROM orders").fetchone()[0] == 0


def test_concurrent_same_key_executes_once(harness):
    _, _, evaluation = harness.prepare(1)
    entered, release = Event(), Event()
    key = str(uuid4())
    def pause(data):
        entered.set()
        assert release.wait(timeout=5)
        return data
    harness.gateway.source.transform = pause
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(harness.call, "buyer-agent", "POST", "/v1/orders", {"evaluationId": evaluation["id"]}, key)
        try:
            assert entered.wait(timeout=5)
            conflict = harness.call("buyer-agent", "POST", "/v1/orders", {"evaluationId": evaluation["id"]}, key)
            assert conflict.json()["code"] == "REQUEST_IN_PROGRESS"
        finally:
            release.set()
        order = future.result(timeout=5)
    assert order.status_code == 201
    assert harness.call("buyer-agent", "POST", "/v1/orders", {"evaluationId": evaluation["id"]}, key).json() == order.json()


def test_restart_keeps_idempotency_and_request_consumption(harness):
    _, _, evaluation = harness.prepare(1)
    key = str(uuid4())
    order = harness.call("buyer-agent", "POST", "/v1/orders", {"evaluationId": evaluation["id"]}, key).json()
    restarted = Gateway(Store(harness.gateway.store.path, "fixture"), Catalog.fixture(), FixtureSource(harness.clock), harness.clock, "http://testserver")
    with TestClient(create_app(restarted)) as client:
        response = client.post("/v1/orders", json={"evaluationId": evaluation["id"]}, headers={**harness.headers["buyer-agent"], "Idempotency-Key": key})
        assert response.status_code == 201 and response.json() == order
        response = client.post("/v1/orders", json={"evaluationId": evaluation["id"]}, headers={**harness.headers["buyer-agent"], "Idempotency-Key": str(uuid4())})
        assert response.json()["code"] == "REQUEST_ALREADY_ORDERED"


def test_rate_limit_and_pagination(harness):
    request, _, _ = harness.prepare(1)
    first = harness.call("chef", "GET", f"/v1/requests/{request['id']}/events?limit=1").json()
    second = harness.call("chef", "GET", f"/v1/requests/{request['id']}/events?limit=1&afterSequence={first['nextAfterSequence']}").json()
    assert first["events"][0]["sequence"] < second["events"][0]["sequence"]
    with harness.gateway.store.transaction() as connection:
        connection.execute("UPDATE throttle SET count=120 WHERE principal='demo-customer:chef'")
    response = harness.call("chef", "GET", f"/v1/requests/{request['id']}")
    assert response.status_code == 429 and response.headers["Retry-After"]


def test_two_baskets_on_one_request_cannot_both_order(harness):
    request, _, first = harness.prepare(1)
    basket = harness.call("buyer-agent", "POST", f"/v1/requests/{request['id']}/baskets", {
        "lines": [{"productId": "demo-milk", "salesUnit": "CASE", "quantity": 2}],
    }).json()
    second = harness.call("buyer-agent", "POST", f"/v1/baskets/{basket['id']}/evaluations", version=1).json()
    barrier = Barrier(2)
    def synchronize(data):
        barrier.wait(timeout=5)
        return data
    harness.gateway.source.transform = synchronize
    def commit(evaluation):
        return harness.call("buyer-agent", "POST", "/v1/orders", {"evaluationId": evaluation["id"]})
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(commit, [first, second]))
    assert sorted(response.status_code for response in responses) == [201, 409]
    assert next(response for response in responses if response.status_code == 409).json()["code"] == "REQUEST_ALREADY_ORDERED"


def test_canonical_line_order_replays(harness):
    request, basket, _ = harness.prepare(extra=True)
    key = str(uuid4())
    endpoint = f"/v1/requests/{request['id']}/baskets"
    original = harness.call("buyer-agent", "POST", endpoint, {"lines": basket["lines"]}, key)
    replay = harness.call("buyer-agent", "POST", endpoint, {"lines": list(reversed(basket["lines"]))}, key)
    assert original.status_code == replay.status_code == 201
    assert original.json() == replay.json()


def test_agent_with_approval_scope_still_cannot_approve(harness):
    _, _, evaluation = harness.prepare()
    with harness.gateway.store.transaction() as connection:
        agent = harness.gateway.store.get(connection, "principal", "buyer-agent")
        agent["scopes"].append("approvals:decide")
        harness.gateway.store.put(connection, "principal", agent, agent["customerId"])
    assert harness.call("buyer-agent", "POST", f"/v1/evaluations/{evaluation['id']}/decisions", {"decision": "approve"}).status_code == 403


def test_method_error_and_internal_error_have_distinct_codes(harness, monkeypatch):
    response = harness.call("buyer-agent", "DELETE", "/v1/orders")
    assert response.status_code == 405 and response.json()["code"] == "METHOD_NOT_ALLOWED"
    def failure(*args):
        raise RuntimeError("secret diagnostics")
    monkeypatch.setattr(harness.gateway.catalog, "search", failure)
    response = harness.call("buyer-agent", "GET", "/v1/products?query=milk")
    assert response.status_code == 500 and response.json()["code"] == "INTERNAL_ERROR"
    assert "secret diagnostics" not in response.text


def test_revoked_approver_grant_is_forbidden(harness):
    request, _, evaluation = harness.prepare()
    approve(harness, evaluation)
    with harness.gateway.store.transaction() as connection:
        grant = harness.gateway.store.get(connection, "grant", "manager:" + request["id"])
        grant["revoked"] = True
        harness.gateway.store.put(connection, "grant", grant, "demo-customer")
    response = harness.call("buyer-agent", "POST", "/v1/orders", {"evaluationId": evaluation["id"]})
    assert response.status_code == 403


def test_late_evaluation_cannot_replace_edited_basket(harness):
    _, basket, _ = harness.prepare(1)
    entered, release = Event(), Event()
    def pause(data):
        entered.set()
        assert release.wait(timeout=5)
        return data
    harness.gateway.source.transform = pause
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(harness.call, "buyer-agent", "POST", f"/v1/baskets/{basket['id']}/evaluations", version=1)
        try:
            assert entered.wait(timeout=5)
            response = harness.call("chef", "PUT", f"/v1/baskets/{basket['id']}", {
                "lines": [{"productId": "demo-milk", "salesUnit": "CASE", "quantity": 2}],
            }, version=1)
            assert response.status_code == 200
        finally:
            release.set()
        assert future.result(timeout=5).status_code == 412
    current = harness.call("chef", "GET", f"/v1/baskets/{basket['id']}").json()
    assert current["state"] == "draft" and "activeEvaluationId" not in current


def test_failed_upstream_never_replaces_evaluation(harness):
    from aimo_gateway.common import Problem
    _, basket, evaluation = harness.prepare(1)
    def fail(data):
        raise Problem(503, "UPSTREAM_UNAVAILABLE")
    harness.gateway.source.transform = fail
    response = harness.call("buyer-agent", "POST", f"/v1/baskets/{basket['id']}/evaluations", version=1)
    assert response.status_code == 503
    assert harness.call("chef", "GET", f"/v1/baskets/{basket['id']}").json()["activeEvaluationId"] == evaluation["id"]
    assert harness.call("buyer-agent", "POST", "/v1/orders", {"evaluationId": evaluation["id"]}).status_code == 503


def test_human_cannot_approve_a_hard_failure(harness):
    _, basket, _ = harness.prepare(1)
    def missing_stock(data):
        data["availability"]["products"][0]["scheduleLines"] = []
        return data
    harness.gateway.source.transform = missing_stock
    evaluation = harness.call("buyer-agent", "POST", f"/v1/baskets/{basket['id']}/evaluations", version=1).json()
    assert evaluation["outcome"] == "blocked"
    response = harness.call("manager", "POST", f"/v1/evaluations/{evaluation['id']}/decisions", {"decision": "approve"})
    assert response.status_code == 409 and response.json()["code"] == "POLICY_BLOCKED"


@pytest.mark.parametrize("field", ["customerId", "price", "mode"])
def test_agent_cannot_inject_authority_or_prices(harness, field):
    request, _, _ = harness.prepare(1)
    response = harness.call("buyer-agent", "POST", f"/v1/requests/{request['id']}/baskets", {
        "lines": [{"productId": "demo-milk", "salesUnit": "CASE", "quantity": 1}], field: "injected",
    })
    assert response.status_code == 422