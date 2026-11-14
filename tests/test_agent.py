import json

import httpx
import pytest

from aimo_gateway.agent import PurchasingAgent
from aimo_gateway.common import Problem
from aimo_gateway.planner import Planner, demo_catalog


def test_grok_tool_call_preserves_constraints():
    def handler(request):
        data = json.loads(request.content)
        assert "constraints" not in json.loads(data["messages"][-1]["content"])
        assert data["tools"][0]["function"]["name"] == "plan_purchase"
        assert "approval" not in data["tools"][0]["function"]["parameters"]["properties"]
        return httpx.Response(200, json={"choices": [{"message": {"tool_calls": [{"function": {
            "name": "plan_purchase", "arguments": '{"recipeId":"vegan-vegetable-pie"}',
        }}]}}]})
    agent = PurchasingAgent(Planner(demo_catalog()), "test-key", transport=httpx.MockTransport(handler))
    plan = agent.plan("Savory vegan pies for a wedding", 100, {"dietaryConfirmed": True, "excludedAllergens": [], "dietaryRequirements": ["vegan"]}, {}, "balanced")
    assert plan["agentMode"] == "grok" and plan["lines"]
    assert "demo-egg" not in [line["productId"] for line in plan["lines"]]


def test_model_cannot_supply_authority():
    def handler(request):
        return httpx.Response(200, json={"choices": [{"message": {"tool_calls": [{"function": {
            "name": "plan_purchase", "arguments": '{"recipeId":"vegetable-pie","approved":true}',
        }}]}}]})
    agent = PurchasingAgent(Planner(demo_catalog()), "test-key", transport=httpx.MockTransport(handler))
    with pytest.raises(Problem):
        agent.plan("pies", 100, {}, {}, "balanced")


def test_provider_failure_is_not_hidden():
    agent = PurchasingAgent(Planner(demo_catalog()), "test-key", transport=httpx.MockTransport(lambda request: httpx.Response(401)))
    with pytest.raises(Problem) as failure:
        agent.plan("pies", 100, {}, {}, "balanced")
    assert "no deterministic fallback" in failure.value.detail


def test_model_cannot_turn_milk_request_into_a_recipe():
    def handler(request):
        return httpx.Response(200, json={"choices": [{"message": {"tool_calls": [{"function": {
            "name": "plan_purchase", "arguments": '{"recipeId":"sweet-pie"}',
        }}]}}]})
    agent = PurchasingAgent(Planner(demo_catalog()), "test-key", transport=httpx.MockTransport(handler))
    with pytest.raises(Problem):
        agent.plan("12 litres lactose-free milk", 1, {"dietaryConfirmed": True, "dietaryRequirements": [], "excludedAllergens": []}, {}, "balanced")