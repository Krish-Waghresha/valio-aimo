import argparse
import json
import os
import re
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

import httpx
import uvicorn

from .app import create_app
from .auth import Auth
from .catalog import Catalog
from .common import identity, now
from .service import Gateway
from .store import Store
from .upstream import FixtureSource, HELSINKI, LiveSource


def validate_origin(origin, host):
    parsed = urlsplit(origin)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.path or parsed.query or parsed.fragment or parsed.username:
        raise ValueError("Origin must contain only scheme, hostname and optional port")
    if parsed.scheme == "http" and (parsed.hostname not in ("localhost", "127.0.0.1", "::1") or host not in ("localhost", "127.0.0.1", "::1")):
        raise ValueError("Plain HTTP is permitted only with loopback origin and binding")


def make_gateway(args):
    validate_origin(args.origin, args.host)
    store = Store(args.database, args.mode)
    if args.mode == "fixture":
        if args.workspace:
            from .planner import DemoSource, demo_catalog
            catalog, source = demo_catalog(), DemoSource(now)
        else:
            catalog, source = Catalog.fixture(), FixtureSource(now)
    else:
        key = os.environ.get("VALIO_API_KEY")
        if not key and args.credentials_from_brief:
            match = re.search(r"API key:\s*`([^`]+)`", Path("valio-aimo-challenge.md").read_text())
            key = match.group(1) if match else None
        catalog, source = Catalog.load("data/valio/products.json"), LiveSource(key)
    return Gateway(store, catalog, source, now, args.origin)


def initialize(args):
    path = Path(args.database).with_name("credentials.json")
    if path.exists():
        raise ValueError("Credential file already exists; initialization will not overwrite it")
    credentials = Auth(Store(args.database, args.mode), now, args.origin).bootstrap()
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "w") as output:
        json.dump({"mode": args.mode, "credentials": credentials}, output, indent=2)
    print(f"Initialized {args.mode} database. Owner-only credentials: {path}")
    print("Credentials expire after 8 hours. Never share the credential file with a buyer agent.")


def admin(args):
    store = Store(args.database, args.mode)
    auth = Auth(store, now, args.origin)
    with store.transaction() as connection:
        if args.command == "grant":
            if not args.principal or not args.request:
                raise ValueError("--principal and --request are required")
            auth.grant(connection, args.principal, args.request)
        elif args.command == "revoke":
            principal = store.get(connection, "principal", args.principal)
            if principal is None:
                raise ValueError("Unknown principal")
            principal["revoked"] = True
            store.put(connection, "principal", principal, principal["customerId"])
        else:
            policy = store.get(connection, "policy", "demo-customer")
            if policy is None:
                raise ValueError("Initialize the database first")
            for argument, field in ((args.autonomous_limit, "autonomousLimitMinor"), (args.order_limit, "orderLimitMinor"), (args.daily_limit, "dailyLimitMinor")):
                if argument is not None:
                    if not 0 <= argument <= 1_000_000_000_000:
                        raise ValueError("Limits must be nonnegative EUR cents within supported range")
                    policy[field] = argument
            if policy["autonomousLimitMinor"] > policy["orderLimitMinor"]:
                raise ValueError("Autonomous ceiling cannot exceed the hard order ceiling")
            policy["version"] = identity()
            store.put(connection, "policy", policy, policy["id"])
    print(f"Owner operation complete: {args.command}")


def demo(args):
    if urlsplit(args.origin).hostname not in ("127.0.0.1", "localhost", "::1"):
        raise ValueError("The credential-loading demo runs against loopback only")
    saved = json.loads(Path(args.database).with_name("credentials.json").read_text())
    if saved["mode"] != args.mode:
        raise ValueError("Credential mode mismatch")
    clients = {actor: httpx.Client(base_url=args.origin, timeout=60) for actor in saved["credentials"]}
    headers = {}

    def call(actor, method, path, data=None, expected=201, key=None, version=None):
        extra = {**headers.get(actor, {}), "Idempotency-Key": key or str(uuid4())}
        if version is not None:
            extra["X-Expected-Basket-Version"] = str(version)
        response = clients[actor].request(method, path, json=data, headers=extra)
        if response.status_code != expected:
            raise ValueError(f"{method} {path} failed with {response.status_code}: {response.json().get('code', 'unknown')}")
        return response.json()

    try:
        for actor in ("chef", "manager"):
            headers[actor] = {"Origin": args.origin}
            login = call(actor, "POST", "/auth/login", {"loginToken": saved["credentials"][actor]}, expected=200)
            headers[actor]["X-CSRF-Token"] = login["csrfToken"]
        headers["buyer-agent"] = {"Authorization": "Bearer " + saved["credentials"]["buyer-agent"]}
        product = args.product or ("demo-milk" if args.mode == "fixture" else "460000")
        delivery = (now().astimezone(HELSINKI).date() + timedelta(days=2)).isoformat()
        request = call("chef", "POST", "/v1/requests", {
            "brief": "Technical replenishment demo; no supplier order is submitted", "deliverySiteId": "demo-kitchen",
            "requestedDeliveryDate": delivery, "maxGrossMinor": 100000,
            "constraints": {"dietaryConfirmed": True, "dietaryRequirements": ["lactose_free"] if args.mode == "fixture" else [], "excludedAllergens": []},
        })
        store = Store(args.database, args.mode)
        auth = Auth(store, now, args.origin)
        with store.transaction() as connection:
            for actor in ("buyer-agent", "manager"):
                auth.grant(connection, actor, request["id"])
        products = call("buyer-agent", "GET", "/v1/products?query=" + product, expected=200)["products"]
        selected = next((item for item in products if item["productId"] == product), None)
        if selected is None:
            raise ValueError("Demo product not found in entitled catalog")
        basket = call("buyer-agent", "POST", f"/v1/requests/{request['id']}/baskets", {
            "lines": [{"productId": product, "salesUnit": selected["salesUnit"], "quantity": args.quantity}],
        })
        evaluation = call("buyer-agent", "POST", f"/v1/baskets/{basket['id']}/evaluations", version=1)
        if evaluation["outcome"] == "blocked":
            raise ValueError("Demo correctly blocked: " + ", ".join(item["code"] for item in evaluation["reasons"]))
        key = str(uuid4())
        if evaluation["outcome"] == "approval_required":
            refusal = call("buyer-agent", "POST", "/v1/orders", {"evaluationId": evaluation["id"]}, expected=409, key=key)
            if refusal["code"] != "APPROVAL_REQUIRED":
                raise ValueError("Unexpected commit refusal")
            call("manager", "POST", f"/v1/evaluations/{evaluation['id']}/decisions", {"decision": "approve", "comment": "Synthetic demo authorization"})
        order = call("buyer-agent", "POST", "/v1/orders", {"evaluationId": evaluation["id"]}, key=key)
        replay = call("buyer-agent", "POST", "/v1/orders", {"evaluationId": evaluation["id"]}, key=key)
        if replay != order:
            raise ValueError("Idempotent replay mismatch")
        events = call("chef", "GET", f"/v1/requests/{request['id']}/events", expected=200)
        print(json.dumps({"mode": args.mode, "product": selected["name"], "initialOutcome": evaluation["outcome"],
                          "orderId": order["id"], "status": order["status"], "grossMinor": order["totals"]["grossMinor"],
                          "currency": "EUR", "replayMatched": True, "auditEvents": len(events["events"])}, indent=2))
    finally:
        for client in clients.values():
            client.close()


def main():
    parser = argparse.ArgumentParser(description="Owner-controlled synthetic purchasing gateway")
    parser.add_argument("command", choices=("init", "serve", "demo", "grant", "revoke", "policy"))
    parser.add_argument("--mode", choices=("fixture", "live"), default="fixture")
    parser.add_argument("--database")
    parser.add_argument("--origin", default="http://127.0.0.1:8000")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--credentials-from-brief", action="store_true")
    parser.add_argument("--workspace", action="store_true", help="Use the expanded recipe fixture for the purchasing UI")
    parser.add_argument("--principal")
    parser.add_argument("--request")
    parser.add_argument("--autonomous-limit", type=int)
    parser.add_argument("--order-limit", type=int)
    parser.add_argument("--daily-limit", type=int)
    parser.add_argument("--product")
    parser.add_argument("--quantity", type=int, default=10)
    args = parser.parse_args()
    args.database = args.database or f"data/gateway/{args.mode}/gateway.sqlite"
    try:
        validate_origin(args.origin, args.host)
        if args.command == "init":
            initialize(args)
        elif args.command == "serve":
            gateway = make_gateway(args)
            uvicorn.run(create_app(gateway), host=args.host, port=args.port, proxy_headers=False, access_log=False)
        elif args.command == "demo":
            demo(args)
        else:
            admin(args)
    except (ValueError, OSError, httpx.RequestError) as error:
        parser.exit(1, f"Gateway operation failed: {error}\n")


if __name__ == "__main__":
    main()