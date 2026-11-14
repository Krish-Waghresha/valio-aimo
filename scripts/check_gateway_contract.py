"""Check the gateway wire contract; requires jsonschema[format]==4.25.1."""

import copy
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


def main():
    root = Path(__file__).resolve().parents[1]
    spec = json.loads((root / "docs/gateway.openapi.json").read_text())
    for schema in spec["components"]["schemas"].values():
        Draft202012Validator.check_schema(schema)
    checks = 0

    def check(name, value, expected=True):
        nonlocal checks
        schema = {"$ref": "#/components/schemas/" + name, "components": spec["components"]}
        errors = list(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(value))
        if (not errors) != expected:
            raise AssertionError(f"{name}: expected valid={expected}; errors={[error.message for error in errors]}")
        checks += 1

    request = spec["paths"]["/v1/requests"]["post"]["requestBody"]["content"]["application/json"]["example"]
    basket = spec["components"]["requestBodies"]["BasketInput"]["content"]["application/json"]["example"]
    evaluation = spec["components"]["schemas"]["Evaluation"]["examples"][0]
    check("RequestInput", request)
    check("BasketInput", basket)
    check("Evaluation", evaluation)
    check("Problem", spec["components"]["responses"]["Problem"]["content"]["application/problem+json"]["example"])
    for field in ("customerId", "approved", "grossMinor", "mode"):
        check("BasketInput", {**basket, field: "injected"}, False)
    for quantity in (0, -1, 1.5, 10001, "10"):
        invalid = copy.deepcopy(basket)
        invalid["lines"][0]["quantity"] = quantity
        check("BasketInput", invalid, False)
    check("RequestInput", {**request, "requestedDeliveryDate": "2026-99-99"}, False)
    invalid = copy.deepcopy(request)
    invalid["constraints"]["dietaryConfirmed"] = False
    check("RequestInput", invalid, False)
    invalid = copy.deepcopy(evaluation)
    del invalid["totals"]
    check("Evaluation", invalid, False)
    invalid = copy.deepcopy(evaluation)
    del invalid["lines"][0]["pricing"]
    check("Evaluation", invalid, False)
    unconfirmed = {"logisticModel": "Terminal", "quantityConfirmed": False, "salesUnit": "RAS", "salesBlock": False}
    check("LineAvailability", unconfirmed)
    check("LineAvailability", {**unconfirmed, "quantityConfirmed": True, "availableQuantity": "999999"}, False)
    check("LineAvailability", {**unconfirmed, "logisticModel": "Unknown", "availableQuantity": "999999"}, False)
    invalid = copy.deepcopy(evaluation)
    invalid["lines"][0]["availability"] = unconfirmed
    check("Evaluation", invalid, False)
    for field in ("availableDate", "closingTime"):
        invalid = copy.deepcopy(evaluation)
        del invalid["lines"][0]["availability"][field]
        check("Evaluation", invalid, False)
    invalid = copy.deepcopy(evaluation)
    invalid["lines"][0]["availability"]["salesBlock"] = True
    check("Evaluation", invalid, False)
    blocked = copy.deepcopy(evaluation)
    blocked["outcome"] = "blocked"
    del blocked["totals"]
    blocked["lines"][0].pop("pricing")
    blocked["lines"][0]["availability"] = unconfirmed
    blocked["reasons"] = [{"code": "QUANTITY_UNCONFIRMED", "message": "Quantity cannot be verified."}]
    blocked["lines"][0]["reasons"] = blocked["reasons"]
    check("Evaluation", blocked)
    check("DecisionInput", {"decision": "approve"})
    check("DecisionInput", {"decision": "approve", "actorId": "forged-human"}, False)
    check("OrderInput", {"evaluationId": evaluation["id"]})
    check("OrderInput", {"evaluationId": evaluation["id"], "customerId": "other-customer"}, False)

    for name in ("RequestInput", "Constraints", "BasketInput", "BasketLineInput", "DecisionInput", "OrderInput"):
        assert spec["components"]["schemas"][name]["additionalProperties"] is False, name

    operations = 0
    human_only = {"createRequest", "cancelRequest", "decideEvaluation"}
    seen_human_only = set()
    for path in spec["paths"].values():
        for method, operation in path.items():
            if method not in ("get", "post", "put"):
                continue
            operations += 1
            assert operation["x-required-scopes"], operation["operationId"]
            if method == "get":
                continue
            parameters = [spec["components"]["parameters"][item["$ref"].split("/")[-1]] for item in operation["parameters"]]
            assert any(item["name"] == "Idempotency-Key" and item["required"] for item in parameters)
            assert any(item["name"] == "X-CSRF-Token" for item in parameters)
            if operation["operationId"] in human_only:
                seen_human_only.add(operation["operationId"])
                assert operation["security"] == [{"HumanSession": []}]
                assert any(item["name"] == "X-CSRF-Token" and item["required"] for item in parameters)
            if operation["operationId"] in ("replaceBasket", "evaluateBasket"):
                assert any(item["name"] == "X-Expected-Basket-Version" and item["required"] for item in parameters)
    assert seen_human_only == human_only
    print(f"PASS: {checks} schema cases, {operations} operation contracts, 6 strict input objects.")
    print("These are wire-contract checks, not runtime gateway/security tests.")


if __name__ == "__main__":
    main()