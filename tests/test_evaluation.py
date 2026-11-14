from datetime import datetime, timezone
from decimal import Decimal

import pytest
import httpx

from aimo_gateway.catalog import Catalog
from aimo_gateway.common import Problem
from aimo_gateway.evaluation import Evaluator
from aimo_gateway.upstream import FixtureSource, LiveSource, timestamp


NOW = datetime(2026, 11, 14, 8, tzinfo=timezone.utc)
POLICY = {"version": "policy-1", "upstreamCustomer": "123", "sites": ["kitchen"],
          "autonomousLimitMinor": 5000, "orderLimitMinor": 100000, "dailyLimitMinor": 200000}
REQUEST = {"id": "request", "customerId": "customer", "intent": {
    "requestedDeliveryDate": "2026-11-16", "deliverySiteId": "kitchen", "maxGrossMinor": 100000,
    "constraints": {"dietaryRequirements": ["lactose_free"], "excludedAllergens": []},
}}
BASKET = {"id": "basket", "version": 1, "lines": [{"productId": "demo-milk", "quantity": 10, "salesUnit": "CASE"}]}


def evaluate(transform=None):
    evaluator = Evaluator(Catalog.fixture(), FixtureSource(lambda: NOW, transform), lambda: NOW)
    return evaluator.evaluate(REQUEST, BASKET, POLICY, 0)[0]


def stock_change(field, value):
    def transform(data):
        data["availability"]["products"][0][field] = value
        return data
    return transform


def test_price_and_evidence():
    result = evaluate()
    assert result["outcome"] == "allowed"
    assert result["totals"]["grossMinor"] == 2220
    assert result["totals"]["netMinor"] == 1960
    assert result["lines"][0]["constraintEvidence"][0]["state"] == "supported"


@pytest.mark.parametrize("field,value,code", [
    ("scheduleLines", [], "DELIVERY_UNAVAILABLE"),
    ("logisticModel", "Terminal", "QUANTITY_UNCONFIRMED"),
    ("logisticModel", None, "QUANTITY_UNCONFIRMED"),
    ("closingTime", None, "DELIVERY_UNCONFIRMED"),
    ("closingTime", "2026-11-14T07:59:59Z", "CUTOFF_PASSED"),
    ("salesBlock", True, "SALES_BLOCK"),
])
def test_business_blocks(field, value, code):
    result = evaluate(stock_change(field, value))
    assert result["outcome"] == "blocked"
    assert code in [item["code"] for item in result["reasons"]]


@pytest.mark.parametrize("amount,code", [(Decimal("0"), "INSUFFICIENT_STOCK"), (Decimal("999999"), "QUANTITY_UNCONFIRMED")])
def test_quantities(amount, code):
    def change(data):
        data["availability"]["products"][0]["scheduleLines"][0]["availableAmount"] = amount
        return data
    result = evaluate(change)
    assert code in [item["code"] for item in result["reasons"]]


def test_no_price_is_business_block():
    def change(data):
        data["price"]["products"][0]["catalogPrice"] = None
        return data
    result = evaluate(change)
    assert "totals" not in result
    assert result["outcome"] == "blocked"


def test_inconsistent_price_is_error():
    def change(data):
        data["price"]["products"][0]["catalogPrice"]["valueWithTax"] = Decimal("9")
        return data
    with pytest.raises(Problem) as failure:
        evaluate(change)
    assert failure.value.code == "UPSTREAM_INVALID"


def test_date_mismatch_and_clock_skew():
    def early(data):
        data["availability"]["products"][0]["scheduleLines"][0]["availableDate"] = "2026-11-15"
        return data
    assert "DELIVERY_DATE_MISMATCH" in [item["code"] for item in evaluate(early)["reasons"]]
    def skew(data):
        data["availability"]["timeNow"] = "2026-11-14T07:00:00Z"
        return data
    with pytest.raises(Problem) as failure:
        evaluate(skew)
    assert failure.value.code == "UPSTREAM_CLOCK_UNTRUSTED"


def test_offsets_and_dst():
    assert timestamp("2026-11-14T10:00:00+0200") == NOW
    with pytest.raises(Problem):
        timestamp("2026-10-25T03:30:00")
    with pytest.raises(Problem):
        timestamp("2026-03-29T03:30:00")


@pytest.mark.parametrize("status,code", [(422, "UPSTREAM_INVALID"), (401, "UPSTREAM_UNAVAILABLE"), (403, "UPSTREAM_UNAVAILABLE"), (429, "UPSTREAM_UNAVAILABLE"), (500, "UPSTREAM_UNAVAILABLE")])
def test_upstream_errors_are_sanitized(status, code):
    def handler(request):
        assert request.headers["X-API-Key"] == "synthetic-test-key"
        assert "Authorization" not in request.headers and "Cookie" not in request.headers
        return httpx.Response(status, json={"detail": [{"input": "do-not-expose-this"}]})
    source = LiveSource("synthetic-test-key", httpx.MockTransport(handler))
    try:
        with pytest.raises(Problem) as failure:
            source.fetch("123", "2026-11-16", ["demo-milk"])
        assert failure.value.code == code
        assert "do-not-expose" not in failure.value.detail
    finally:
        source.close()


def test_json_numbers_are_decoded_directly_as_decimals():
    import json
    def handler(request):
        data = FixtureSource(lambda: NOW).fetch("123", "2026-11-16", ["demo-milk"])
        endpoint = request.url.path.rsplit("/", 1)[-1]
        return httpx.Response(200, content=json.dumps(data[endpoint], default=float).encode())
    source = LiveSource("synthetic-test-key", httpx.MockTransport(handler))
    try:
        result = source.fetch("123", "2026-11-16", ["demo-milk"])
        assert result["price"]["products"][0]["catalogPrice"]["value"] == Decimal("1.96")
        assert isinstance(result["price"]["products"][0]["quantity"], Decimal)
        assert isinstance(result["availability"]["products"][0]["scheduleLines"][0]["availableAmount"], Decimal)
    finally:
        source.close()


def test_unknown_dietary_evidence_blocks_and_lactose_is_not_milk():
    import copy
    request = copy.deepcopy(REQUEST)
    request["intent"]["constraints"]["excludedAllergens"] = ["milk", "sesame"]
    evaluator = Evaluator(Catalog.fixture(), FixtureSource(lambda: NOW), lambda: NOW)
    result, _ = evaluator.evaluate(request, BASKET, POLICY, 0)
    assert result["outcome"] == "blocked"
    assert {item["code"] for item in result["reasons"]} == {"DIETARY_CONFLICT", "DIETARY_UNCONFIRMED"}


def test_lot_deposit_and_evidence_allowlist():
    catalog = Catalog.fixture()
    catalog.products["demo-milk"]["allowedLotSize"] = 3
    catalog.products["demo-milk"]["deposits"] = [{"material": "deposit"}]
    def change(data):
        data["price"]["unexpectedDebugSecret"] = "never-retain"
        data["price"]["products"][0]["unexpectedDebugSecret"] = "never-retain"
        return data
    evaluator = Evaluator(catalog, FixtureSource(lambda: NOW, change), lambda: NOW)
    result, evidence = evaluator.evaluate(REQUEST, BASKET, POLICY, 0)
    assert {item["code"] for item in result["reasons"]} == {"UNIT_UNCONFIRMED", "PRODUCT_NOT_ELIGIBLE"}
    assert "never-retain" not in str(evidence)


@pytest.mark.parametrize("field,bound,value", [
    ("catalogPrice", "validFrom", "2026-11-17T00:00:00+0200"),
    ("catalogPrice", "validTo", "2026-11-15T00:00:00+0200"),
    ("priceWithTax", "validFrom", "2026-11-17T00:00:00+0200"),
    ("priceWithTax", "validTo", "2026-11-15T00:00:00+0200"),
])
def test_nested_price_validity(field, bound, value):
    def change(data):
        data["price"]["products"][0][field][bound] = value
        return data
    with pytest.raises(Problem) as failure:
        evaluate(change)
    assert failure.value.code == "UPSTREAM_INVALID"


@pytest.mark.parametrize("units,state", [(["FREE_FROM"], "supported"), (["CONTAINS"], "contradicted"),
                                       (["MAY_CONTAIN"], "contradicted"), ([], "unknown"),
                                       (["FREE_FROM", "CONTAINS"], "contradicted"), (["UNSPECIFIED"], "unknown")])
def test_live_synkka_allergen_mapping(units, state):
    product = {"id": "milk-test", "salesUnit": "CASE", "synkkaData": {"classifications": [
        {"name": "allergen", "values": [{"id": "AM", "unit": unit} for unit in units]},
        {"name": "nutritionalClaim", "values": [{"id": "FREE_FROM_LACTOSE", "unit": "FREE_FROM"}]},
    ]}}
    catalog = Catalog([product], "test", "live")
    evidence = catalog.evidence("milk-test", {"dietaryRequirements": ["lactose_free"], "excludedAllergens": ["milk"]})
    assert evidence[0]["state"] == "supported"
    assert evidence[1]["state"] == state


def test_aggregate_free_from_does_not_override_subtype_conflict():
    product = {"id": "test", "salesUnit": "BAG", "synkkaData": {"classifications": [
        {"name": "nonAllergen", "values": [{"id": "AW", "unit": "FREE_FROM"}]},
        {"name": "allergen", "values": [{"id": "UW", "unit": "MAY_CONTAIN"}]},
    ]}}
    catalog = Catalog([product], "test", "live")
    assert catalog.evidence("test", {"dietaryRequirements": [], "excludedAllergens": ["gluten_cereals"]})[0]["state"] == "contradicted"


def test_fractional_cent_rounding_and_comparison_prices():
    import copy
    basket = copy.deepcopy(BASKET)
    basket["lines"][0]["quantity"] = 3
    def change(data):
        record = data["price"]["products"][0]
        record["catalogPrice"].update(value=Decimal("0.015"), valueWithTax=Decimal("0.02"))
        record["priceWithTax"]["value"] = Decimal("0.02")
        record["tax"] = {"taxRate": Decimal("33.333333"), "taxValue": Decimal("0.005")}
        record["comparisonPrice"] = {"value": Decimal("999")}
        record["listPrice"] = {"value": Decimal("999")}
        return data
    evaluator = Evaluator(Catalog.fixture(), FixtureSource(lambda: NOW, change), lambda: NOW)
    result, _ = evaluator.evaluate(REQUEST, basket, POLICY, 0)
    assert result["totals"] == {"netMinor": 5, "grossMinor": 6, "taxMinor": 1, "currency": "EUR", "basis": "goods_only"}