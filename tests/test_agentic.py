from datetime import date
from decimal import Decimal

from aimo_gateway.interpreter import interpret
from aimo_gateway.sourcing import decide, pack_amount

TODAY = date(2026, 11, 14)  # Saturday


def test_flyer_request_is_structured_with_provenance():
    result = interpret("I need 1,000 litres of lactose-free milk by Monday. Find an option based on price and availability.", TODAY, {"orderLimitMinor": 500000})
    fields = result["fields"]
    assert result["kind"] == "product" and result["ready"]
    assert fields["items"]["value"][0] | {"evidence": None} == {"query": "lactose-free milk", "quantity": "1000", "unit": "l", "evidence": None}
    assert fields["deliveryDate"] == {"value": "2026-11-16", "source": "inferred", "evidence": "monday"}
    assert fields["dietaryRequirements"]["value"] == ["lactose_free"] and fields["dietaryRequirements"]["source"] == "said"
    assert fields["budget"]["source"] == "default" and fields["budget"]["value"] == "5000.00"
    assert result["brief"] == "1,000 L lactose-free milk"


def test_event_request_asks_only_what_is_missing():
    result = interpret("pies for the wedding", TODAY)
    assert result["kind"] == "recipe" and not result["ready"]
    assert {item["field"] for item in result["questions"]} == {"style", "servings"}
    full = interpret("Savory pies for 100 wedding guests on Saturday, one guest has a nut allergy, under 400 euros", TODAY)
    assert full["ready"]
    assert full["fields"]["servings"]["value"] == 100
    assert full["fields"]["budget"]["value"] == "400.00"
    assert set(full["fields"]["excludedAllergens"]["value"]) == {"nuts", "peanuts"}
    assert full["fields"]["deliveryDate"]["value"] == "2026-11-21"


def test_past_date_is_questioned_not_used():
    result = interpret("10 kg butter on 1.11.2026", TODAY)
    assert result["fields"]["deliveryDate"]["source"] == "missing"
    assert any(item["field"] == "deliveryDate" for item in result["questions"])


def test_case_pack_amount_uses_units_and_base_volume():
    raw = {"salesUnit": "KI", "baseUnit": "ST", "units": [{"unitId": "KI", "sizeInBaseUnits": 12}],
           "synkkaData": {"unitConversions": [{"synkkaPackagingType": "BASE_UNIT_OR_EACH", "volume": {"value": 1.75, "unit": "LTR"}}]}}
    assert pack_amount(raw, "l") == Decimal("21.00")


def candidate(product_id, name, substitutes=()):
    return {"productId": product_id, "name": name, "salesUnit": "ST", "packAmount": Decimal("1"), "unit": "l",
            "vendor": name.split()[0].upper(), "labels": [], "category": "x", "substitutes": list(substitutes)}


def fact(gross, available=None, reasons=()):
    availability = {"quantityConfirmed": True, "availableQuantity": str(available if available is not None else 9999999999),
                    "closingTime": "2026-11-15T15:00:00Z"}
    return {"pricing": {"unitGross": str(gross), "unitNet": str(gross)}, "availability": availability,
            "reasons": [{"code": code} for code in reasons]}


def test_partial_stock_offers_split_switch_and_partial():
    usual = candidate("469363", "Arla milk 1 L")
    official = candidate("464306", "Valio Arki Eila milk 1 l", substitutes=["469363"])
    late = candidate("469287", "Valio Eila 1,75 l")
    facts = {"469363": fact("2.81", 384), "464306": fact("1.15"), "469287": fact("1.00", reasons=["CUTOFF_PASSED"])}
    item = {"query": "lactose-free milk", "quantity": "1000", "unit": "l"}
    lines, exceptions, actions, _ = decide(item, "milk", [usual, official, late], facts, {}, "balanced", "2026-11-16")
    assert lines == []
    options = exceptions[0]["options"]
    assert [option["id"] for option in options] == ["switch", "split", "partial"]
    assert options[0]["primary"] and options[0]["lines"] == [{"productId": "464306", "salesUnit": "ST", "quantity": 1000}]
    assert options[1]["lines"] == [{"productId": "469363", "salesUnit": "ST", "quantity": 384},
                                   {"productId": "464306", "salesUnit": "ST", "quantity": 616}]
    assert "+€" in options[1]["effect"]
    assert "official substitute" in exceptions[0]["detail"]
    assert any("Skipped" in action["message"] and "cutoff" in action["message"] for action in actions)


def test_unreliable_product_is_avoided_when_a_reliable_one_is_close_in_price():
    cheap = candidate("465845", "Valiojogurtti 1 kg")
    safe = candidate("476824", "Valio A+ yoghurt 1 kg")
    for item in (cheap, safe):
        item["unit"] = "kg"
    facts = {"465845": fact("1.69"), "476824": fact("1.90")}
    reliability = {"465845": Decimal("0.5"), "476824": Decimal("1.0")}
    lines, exceptions, actions, _ = decide({"query": "yogurt", "quantity": "50", "unit": "kg"}, "other", [cheap, safe], facts, reliability, "balanced", "2026-11-16")
    assert not exceptions
    assert lines == [{"productId": "476824", "salesUnit": "ST", "quantity": 50}]
    assert any(action["code"] == "RELIABILITY" for action in actions)


def test_nothing_eligible_blocks_with_reason():
    only = candidate("463010", "Kruunu flour 20 kg")
    lines, exceptions, actions, _ = decide({"query": "wheat flour", "quantity": "40", "unit": "kg"}, "wheat flour", [only],
                                          {"463010": fact("19.42", reasons=["DELIVERY_UNAVAILABLE"])}, {}, "balanced", "2026-11-16")
    assert lines == [] and exceptions[0]["severity"] == "blocked"
    assert "not available" in actions[0]["message"]
