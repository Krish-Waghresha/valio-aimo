#!/usr/bin/env python3
"""Act as an external buyer agent against the open /v1 gateway API, for demos.

Usage (repo root, demo server running):
  uv run python scripts/agent_console.py search "lactose-free milk"
  uv run python scripts/agent_console.py guardrails      # needs an order waiting for approval

The agent uses only its own bearer token and the documented OpenAPI operations.
The `guardrails` command reads the newest waiting order's evaluation id via the owner's
chef session (demo convenience only), then tries the two forbidden shortcuts as the agent.
"""

import json
import os
import sys
import time
import uuid
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
CREDS = Path(os.environ.get("AIMO_CREDENTIALS", ROOT / "data" / "gateway" / "demo-current" / "credentials.json"))
URL = os.environ.get("AIMO_URL", "http://127.0.0.1:8003")
TEAL, LIME, RED, GREY, BOLD, END = "\033[36m", "\033[92m", "\033[91m", "\033[90m", "\033[1m", "\033[0m"


def slow(line, pause=0.35):
    print(line, flush=True)
    time.sleep(pause)


def agent_client(credentials):
    return httpx.Client(base_url=URL, timeout=60, headers={"Authorization": "Bearer " + credentials["buyer-agent"]})


def search(query):
    credentials = json.loads(CREDS.read_text())["credentials"]
    slow(f"{BOLD}Hotel Aurora buyer agent{END} {GREY}→ Valio Aimo gateway (open API, OpenAPI 3.1){END}", 0.6)
    slow(f"{TEAL}GET /v1/products?query={query}{END}", 0.6)
    response = agent_client(credentials).get("/v1/products", params={"query": query, "limit": 8})
    body = response.json()
    slow(f"{LIME}{response.status_code} OK{END} {GREY}· catalog {body.get('catalogVersion', '')[:12]}…{END}", 0.4)
    for product in body.get("products", [])[:6]:
        claims = [item["constraint"].replace("_", "-") for item in product.get("constraintEvidence", []) if item.get("state") == "supported"]
        slow(f"  {product['productId']}  {product['name'][:58]:<58} {GREY}{product['salesUnit']:<4} {', '.join(claims)}{END}", 0.25)


def guardrails():
    credentials = json.loads(CREDS.read_text())["credentials"]
    chef = httpx.Client(base_url=URL, timeout=60, headers={"Origin": URL})
    chef.post("/auth/login", json={"loginToken": credentials["chef"]}).raise_for_status()
    waiting = [job for job in chef.get("/workspace/jobs").json() if job.get("state") == "awaiting_approval" and job.get("evaluation")]
    if not waiting:
        sys.exit("No order is waiting for approval. Create one over the limit first.")
    evaluation = waiting[0]["evaluation"]
    total = evaluation["totals"]["grossMinor"] / 100
    agent = agent_client(credentials)
    slow(f"{BOLD}Hotel Aurora buyer agent{END} {GREY}· basket €{total:,.2f} · agent limit €500{END}", 0.8)
    slow(f"{GREY}# try to place the order without the manager{END}", 0.5)
    slow(f"{TEAL}POST /v1/orders{END}", 0.8)
    response = agent.post("/v1/orders", json={"evaluationId": evaluation["id"]}, headers={"Idempotency-Key": str(uuid.uuid4())})
    slow(f"{RED}✗ {response.status_code} · {response.json().get('detail')}{END}", 1.0)
    slow(f"{GREY}# try to approve its own order{END}", 0.5)
    slow(f"{TEAL}POST /v1/evaluations/{evaluation['id'][:8]}…/decisions{END}", 0.8)
    response = agent.post(f"/v1/evaluations/{evaluation['id']}/decisions", json={"decision": "approve"}, headers={"Idempotency-Key": str(uuid.uuid4())})
    slow(f"{RED}✗ {response.status_code} · {response.json().get('detail')}{END}", 1.0)
    slow(f"{LIME}Both refused and logged. Only the kitchen manager can approve this order.{END}")


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "search":
        search(" ".join(sys.argv[2:]))
    elif len(sys.argv) == 2 and sys.argv[1] == "guardrails":
        guardrails()
    else:
        sys.exit(__doc__)
