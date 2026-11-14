from datetime import datetime, timezone
from decimal import Decimal

import pytest

from aimo_gateway.catalog import Catalog
from aimo_gateway.evaluation import Evaluator
from aimo_gateway.planner import AGENT_MODE, DemoSource, Planner, demo_catalog
from aimo_gateway.upstream import FixtureSource


NOW = datetime(2026, 11, 14, 8, tzinfo=timezone.utc)
POLICY = {
    "version": "policy-1", "upstreamCustomer": "123", "sites": ["kitchen"],
    "autonomousLimitMinor": 100_000_000, "orderLimitMinor": 100_000_000, "dailyLimitMinor": 100_000_000,
}

def test_fractional_lot_can_produce_integer_sales_units():
    from aimo_gateway.planner import _packs
    assert _packs(Decimal("4"), Decimal("2"), Decimal("0.01")) == (2, Decimal("0"))
    assert _packs(Decimal("4"), Decimal("2"), Decimal("1.5")) == (3, Decimal("2"))


def test_live_pack_uses_structured_weight_only():
    from aimo_gateway.planner import _live_pack
    raw = {"salesUnit": "BAG", "baseUnit": "BAG", "synkkaData": {"unitConversions": [
        {"synkkaPackagingType": "BASE_UNIT_OR_EACH", "netWeight": {"unit": "GRM", "value": 2000}},
    ]}}
    assert _live_pack(raw, "kg") == Decimal("2")
    raw["salesUnit"] = "PAL"
    assert _live_pack(raw, "kg") is None


def test_contradicted_claims_are_not_positive_labels():
    from aimo_gateway.planner import _labels
    labels = _labels(demo_catalog().products["demo-flour"])
    assert "FREE_FROM_GLUTEN" not in labels
    assert "VEGAN" in labels


def test_live_direct_quantity_uses_catalog_unit():
    raw = {"id": "460000", "salesUnit": "RAS", "baseUnit": "RAS", "allowedLotSize": Decimal("0.01"),
           "synkkaData": {"names": [{"language": "en", "value": "Catalog product"}]}}
    result = Planner(Catalog([raw], "test", "live")).plan("10 RAS of 460000", 1, constraints())
    assert result["lines"] == [{"productId": "460000", "salesUnit": "RAS", "quantity": 10}]


def test_piece_sales_unit_is_not_an_individual_egg():
    from aimo_gateway.planner import _live_pack
    raw = {"id": "468269", "salesUnit": "ST", "baseUnit": "ST", "synkkaData": {"unitConversions": [
        {"synkkaPackagingType": "BASE_UNIT_OR_EACH", "netWeight": {"unit": "GRM", "value": 1000}, "volume": {"unit": "GRM", "value": 1000}},
    ]}}
    assert _live_pack(raw, "pc") is None
    assert _live_pack(raw, "kg") == Decimal("1")


def test_live_recipe_never_uses_broad_name_matches():
    raw = {"id": "unreviewed", "salesUnit": "ST", "baseUnit": "ST", "allowedLotSize": 1,
           "synkkaData": {"names": [{"language": "en", "value": "Cashew nut butter milk based infant formula"}],
                          "unitConversions": [{"synkkaPackagingType": "BASE_UNIT_OR_EACH", "netWeight": {"unit": "GRM", "value": 1000}, "volume": {"unit": "LTR", "value": 1}}]}}
    planner = Planner(Catalog([raw], "test", "live"))
    assert planner._live_candidates("butter", "kg") == []
    assert planner._live_candidates("milk", "l") == []


def constraints(**extra):
    value = {"dietaryConfirmed": True, "dietaryRequirements": [], "excludedAllergens": []}
    value.update(extra)
    return value


def plan(brief, servings=100, pantry=None, preference="balanced", catalog=None, **extra):
    return Planner(catalog or demo_catalog()).plan(brief, servings, constraints(**extra), pantry, preference)


def codes(items):
    return [item["code"] for item in items]


def ingredient(result, key):
    return next(item for item in result["ingredients"] if item["key"] == key)


def evaluate(lines, source, dietary=None, allergens=None):
    request = {"id": "request", "customerId": "customer", "intent": {
        "requestedDeliveryDate": "2026-11-16", "deliverySiteId": "kitchen", "maxGrossMinor": 100_000_000,
        "constraints": {"dietaryRequirements": dietary or [], "excludedAllergens": allergens or []},
    }}
    basket = {"id": "basket", "version": 1, "lines": lines}
    return Evaluator(demo_catalog(), source, lambda: NOW).evaluate(request, basket, POLICY, 0)[0]


def test_demo_catalog_retains_gateway_fixture_identity():
    catalog = demo_catalog()
    original = Catalog.fixture()
    assert catalog.mode == "fixture"
    assert catalog.version == "demo-planner-catalog-1"
    for product_id in ("demo-milk", "demo-flour"):
        raw, prior = catalog.products[product_id], original.products[product_id]
        assert raw["salesUnit"] == prior["salesUnit"]
        assert raw["allowedLotSize"] == prior["allowedLotSize"]
        assert raw["synkkaData"]["names"] == prior["synkkaData"]["names"]
        for key, state in prior["fixtureEvidence"].items():
            assert raw["fixtureEvidence"][key] == state
        assert raw["planner"]["packAmount"]
        assert "deposits" not in raw
        assert raw.get("synkkaData", {}).get("variableUnit") is not True
    milk = catalog.evidence("demo-milk", {"dietaryRequirements": ["lactose_free"], "excludedAllergens": ["milk", "peanuts"]})
    assert [item["state"] for item in milk] == ["supported", "contradicted", "supported"]
    assert catalog.evidence("demo-flour", {"dietaryRequirements": [], "excludedAllergens": ["gluten_cereals"]})[0]["state"] == "contradicted"
    assert original.evidence("demo-milk", {"dietaryRequirements": ["gluten_free"], "excludedAllergens": []})[0]["state"] == "unknown"
    assert len(catalog.products) == len(set(catalog.products)) > 2


def test_recipes_identify_deterministic_mode():
    recipes = Planner(demo_catalog()).recipes()
    assert [item["id"] for item in recipes] == ["vegetable-pie", "sweet-pie", "vegan-vegetable-pie"]
    assert all(item["agentMode"] == AGENT_MODE and item["imageUrl"] is None and item["servings"] == 100 for item in recipes)
    assert Planner.agent_mode == "deterministic"


def test_ambiguous_pies_do_not_guess_a_recipe():
    result = plan("Pies for 100 wedding guests")
    assert result["complete"] is False
    assert result["lines"] == []
    assert "RECIPE_STYLE_REQUIRED" in codes(result["questions"])
    assert result["agentMode"] == "deterministic"
    assert any(item["code"] == "AUTHORITY" for item in result["explanations"])


def test_vegetable_plan_scales_and_deducts_pantry():
    baked = plan("Vegetable pies for the wedding", pantry={"flour": "1"})
    flour = ingredient(baked, "flour")
    assert baked["recipeId"] == "vegetable-pie"
    assert baked["title"] == "Vegetable wedding pies"
    assert baked["recipeSource"] == "Curated synthetic demo recipe v1"
    assert flour["required"] == "5"
    assert flour["pantry"] == "1"
    assert flour["needed"] == "4"
    assert flour["productId"] == "demo-flour"
    assert flour["quantity"] == 2
    assert flour["packAmount"] == "2"
    assert flour["overage"] == "0"
    assert baked["lines"][0] == {"productId": "demo-flour", "salesUnit": "BAG", "quantity": 2}
    larger = plan("Vegetable pies", 150)
    assert ingredient(larger, "flour")["required"] == "7.5"
    assert ingredient(larger, "flour")["quantity"] == 4
    assert ingredient(plan("Vegetable pies", 100), "flour")["quantity"] == 3
    assert larger["lines"] != plan("Vegetable pies", 100)["lines"]


def test_preference_changes_only_equivalent_products():
    balanced = ingredient(plan("Vegetable pies", preference="balanced"), "potato")
    priced = ingredient(plan("Vegetable pies", preference="price"), "potato")
    green = ingredient(plan("Vegetable pies", preference="sustainability"), "flour")
    assert balanced["productId"] == "demo-potato"
    assert priced["productId"] == "demo-potato-small"
    assert green["productId"] == "demo-flour-alt"
    assert any(item["code"] == "PRICE_UNKNOWN" for item in plan("Vegetable pies", preference="price")["explanations"])


def test_constraints_select_curated_alternatives_or_withhold_lines():
    gluten_free = plan("Vegetable pies", dietaryRequirements=["gluten_free"])
    assert ingredient(gluten_free, "flour")["productId"] == "demo-flour-gf"
    assert any(item["code"] == "RECIPE_CHANGE" for item in gluten_free["warnings"])
    lactose_free = plan("Vegetable pies", dietaryRequirements=["lactose_free"])
    assert ingredient(lactose_free, "butter")["productId"] == "demo-lf-butter"
    milk_free = plan("Vegetable pies", excludedAllergens=["milk"])
    assert ingredient(milk_free, "butter")["productId"] == "demo-margarine"
    assert ingredient(milk_free, "milk")["productId"] == "demo-oat-drink"
    assert ingredient(milk_free, "egg")["productId"] == "demo-egg"
    explicit = plan("Ignored title", recipeId="vegetable-pie", dietaryRequirements=["vegan"])
    assert explicit["lines"] == []
    assert explicit["complete"] is False
    assert "NO_ELIGIBLE_CANDIDATE" in codes(explicit["questions"])
    soy = plan("Vegan vegetable pies", dietaryRequirements=["vegan"], excludedAllergens=["soybeans"])
    assert soy["lines"] == []
    assert soy["complete"] is False


def test_vegan_recipe_lot_rounding_and_sweet_recipe():
    vegan = plan("Vegan vegetable pies", 10, dietaryRequirements=["vegan"])
    assert vegan["recipeId"] == "vegan-vegetable-pie"
    assert ingredient(vegan, "fat")["quantity"] == 2
    assert all(line["productId"] != "demo-egg" for line in vegan["lines"])
    sweet = plan("Sweet apple pies")
    assert sweet["recipeId"] == "sweet-pie"
    assert ingredient(sweet, "apple")["productId"] == "demo-apple"
    conflict = plan("Sweet and savory pies")
    assert conflict["lines"] == []
    assert "RECIPE_STYLE_REQUIRED" in codes(conflict["questions"])


def test_direct_product_quantities_do_not_invent_conversions():
    milk = plan("10 cases of demo-milk")
    assert milk["recipeId"] is None
    assert milk["lines"] == [{"productId": "demo-milk", "salesUnit": "CASE", "quantity": 10}]
    assert all(candidate["unitNet"] is None and candidate["available"] is None for item in milk["ingredients"] for candidate in item["candidates"])
    flour = plan("5 kg of wheat flour")
    assert ingredient(flour, "demo-flour")["quantity"] == 3
    assert ingredient(flour, "demo-flour")["overage"] == "1"
    margarine = plan("1 tub of demo-margarine")
    assert margarine["lines"] == [{"productId": "demo-margarine", "salesUnit": "TUB", "quantity": 2}]
    assert plan("1.5 cases of demo-milk")["lines"] == []
    assert "UNIT_CONVERSION_UNAVAILABLE" in codes(plan("2 kg of demo-milk")["questions"])
    assert plan("Lasagna for 40 guests")["lines"] == []
    assert "UNSUPPORTED_REQUEST" in codes(plan("Lasagna for 40 guests")["questions"])


def test_confirmation_authority_and_invalid_input_fail_closed():
    unconfirmed = Planner(demo_catalog()).plan("Vegetable pies", 100, {"dietaryRequirements": [], "excludedAllergens": []})
    assert unconfirmed["lines"] == []
    assert "DIETARY_CONFIRMATION_REQUIRED" in codes(unconfirmed["questions"])
    asserted = constraints(autonomousLimitMinor=1, approve=True)
    plain = plan("Vegetable pies")
    asserted_plan = Planner(demo_catalog()).plan("Vegetable pies", 100, asserted)
    assert asserted_plan["lines"] == plain["lines"]
    assert "approve" not in asserted_plan
    assert plan("Vegetable pies", True)["lines"] == []
    assert plan("Vegetable pies", pantry={"flour": -1})["lines"] == []
    assert plan("Vegetable pies", preference="cheapest")["lines"] == []
    mixed = plan("Vegetable pies and 2 cases of demo-milk")
    assert mixed["lines"] == []
    assert "MIXED_REQUEST" in codes(mixed["questions"])


def test_metrics_are_informational_and_unpriced():
    result = plan("Vegetable pies", pantry={"flour": "1"})
    assert result["comparison"]["carbonKgEstimate"] is not None
    assert 0 < result["comparison"]["carbonCoverage"] < 1
    assert result["comparison"]["reliability"] == 0.94
    assert any(item["code"] == "INFORMATIONAL_METRICS" for item in result["explanations"])
    assert all(candidate["unitGross"] is None for item in result["ingredients"] for candidate in item["candidates"])
    reliabilities = []
    for item in result["ingredients"]:
        if not item["quantity"]:
            continue
        candidate = next(entry for entry in item["candidates"] if entry["productId"] == item["productId"])
        reliabilities.append(candidate["reliability"])
    assert result["comparison"]["reliability"] == min(reliabilities)


def test_select_reuses_candidates_without_catalog_or_mutation():
    owner = Planner(demo_catalog())
    original = owner.plan("Vegetable pies", 100, constraints(), {"flour": "1"})
    before = original["lines"][:]
    owner.catalog = None
    updated = owner.select(original, ["demo-flour"])
    assert original["lines"] == before
    assert ingredient(updated, "flour")["productId"] == "demo-flour-alt"
    assert ingredient(updated, "flour")["quantity"] == 2
    assert updated["complete"] is True
    blocked = owner.select(original, ["demo-flour", "demo-flour-alt", "demo-flour-gf"])
    assert blocked["lines"] == []
    assert blocked["complete"] is False
    with pytest.raises(ValueError):
        owner.select({}, [])


def test_demo_source_matches_gateway_evaluation_and_scenarios():
    result = plan("Vegetable pies", 20)
    evaluation = evaluate(result["lines"], DemoSource(lambda: NOW))
    assert evaluation["outcome"] == "allowed"
    assert evaluation["totals"]["grossMinor"] > 0
    shortage = evaluate([{"productId": "demo-flour", "salesUnit": "BAG", "quantity": 2}], DemoSource(lambda: NOW, "shortage"))
    assert "INSUFFICIENT_STOCK" in codes(shortage["reasons"])
    late = evaluate([{"productId": "demo-flour", "salesUnit": "BAG", "quantity": 1}], DemoSource(lambda: NOW, "late"))
    assert "DELIVERY_DATE_MISMATCH" in codes(late["reasons"])
    unaffected = evaluate([{"productId": "demo-milk", "salesUnit": "CASE", "quantity": 1}], DemoSource(lambda: NOW, "late"))
    assert unaffected["outcome"] == "allowed"
    missing = DemoSource(lambda: NOW).fetch("123", "2026-11-16", ["missing-product"])
    assert missing["price"]["products"][0]["error"] is True
    assert missing["availability"]["products"][0]["scheduleLines"] == []
    DemoSource(lambda: NOW).close()
    with pytest.raises(ValueError):
        DemoSource(lambda: NOW, "live")
    with pytest.raises(ValueError):
        DemoSource(lambda: datetime(2026, 11, 14, 8)).fetch("123", "2026-11-16", ["demo-milk"])


def test_technical_fixture_source_is_unchanged():
    data = FixtureSource(lambda: NOW).fetch("123", "2026-11-16", ["demo-flour", "demo-milk"])
    assert data["price"]["products"][0]["catalogPrice"]["value"] == Decimal("1.96")
    assert data["availability"]["products"][0]["scheduleLines"][0]["availableAmount"] == Decimal("10000")
    assert data["availability"]["products"][1]["scheduleLines"][0]["salesUnit"] == "CASE"


def test_missing_catalog_products_and_static_overlays_are_not_invented(tmp_path):
    sparse = Catalog([{
        "id": "demo-flour", "salesUnit": "BAG", "allowedLotSize": 1, "deleted": False,
        "synkkaData": {"names": [{"language": "en", "value": "Demo flour bag"}]},
        "planner": {"packAmount": "2", "packUnit": "kg", "reliability": "0.98", "carbonKgPerKg": "0.8", "source": "test"},
    }], "sparse", "live")
    incomplete = plan("Vegetable pies", catalog=sparse)
    assert incomplete["lines"] == []
    assert incomplete["complete"] is False
    (tmp_path / "carbon-footprint.csv").write_text("productId,AVG kg CO2-eq/kg\n460000,2.315\n", encoding="utf-8")
    (tmp_path / "delivery-reliability.csv").write_text("productId,deliveryReliability\n460000,0.5\n", encoding="utf-8")
    overlay = Catalog([{
        "id": "460000", "salesUnit": "BAG", "allowedLotSize": 1, "deleted": False,
        "synkkaData": {"names": [{"language": "en", "value": "Portal sample"}]},
        "planner": {"packAmount": "1", "packUnit": "kg"},
    }], "overlay", "live")
    quoted = Planner(overlay, tmp_path).plan("2 kg of 460000", 1, constraints())
    candidate = quoted["ingredients"][0]["candidates"][0]
    assert quoted["lines"] == [{"productId": "460000", "salesUnit": "BAG", "quantity": 2}]
    assert candidate["unitNet"] is None and candidate["available"] is None
    assert candidate["reliability"] == 0.5
    assert candidate["carbonKgPerKg"] == 2.315
    assert "carbon-footprint.csv" in candidate["metadataSource"]


def test_gateway_accepts_constrained_demo_baskets():
    gluten_free = plan("Vegetable pies", 12, dietaryRequirements=["gluten_free", "lactose_free"])
    evaluation = evaluate(gluten_free["lines"], DemoSource(lambda: NOW), ["gluten_free", "lactose_free"])
    assert evaluation["outcome"] == "allowed"
    vegan = plan("Vegan vegetable pies", 12, dietaryRequirements=["vegan"])
    assert evaluate(vegan["lines"], DemoSource(lambda: NOW), ["vegan"])["outcome"] == "allowed"
