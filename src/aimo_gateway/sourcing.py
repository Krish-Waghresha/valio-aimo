"""Agentic sourcing for direct product requests ("1,000 litres lactose-free milk by Monday").

Steps, all deterministic and explainable:
1. shortlist(): catalog-only search for a product family, converted to the requested unit.
2. The workspace checks the shortlist ONCE with live price/availability (never the full catalog).
3. decide(): drops ineligible candidates with a reason, ranks the rest, allocates the quantity
   (splitting across producers when stock is partial) and raises exception cards only when a
   human decision is needed. Everything the agent decided alone is recorded as an agent action.

Decision rules follow common practice (Instacart/Pepper partial fills, SAP-style tolerances):
- same spec, enough stock                      -> agent decides, logged
- partial stock, equivalent product available  -> one-tap card (split recommended)
- usual product replaced by another brand      -> one-tap card
- low historical delivery reliability (< 0.9)  -> agent avoids it when an equivalent is within +15 % price
- cutoff passed / no availability / diet fails -> agent drops it, logged; never ordered
- nothing eligible                             -> blocked, human asked to revise
"""

import csv
import re
from decimal import ROUND_CEILING, Decimal
from pathlib import Path

FAMILIES = {
    "milk": {
        "match": r"maito|milk|maitojuoma|milk drink",
        "exclude": r"kerma|cream|jauhe|powder|kaakao|cocoa|suklaa|chocolate|juusto|cheese|jogurt|yog|rahka|quark|vanukas|pudding|kahvi|coffee|puuro|porridge|kefir|piimä|buttermilk|vispi|ruoka|cooking|smoothie|kaura|oat|soija|soy|mantel|almond|riisi|rice|kookos|coconut|herne|pea|protein|proteiini|jäätelö|ice|leipä|bread|keksi|biscuit|vohveli|kastike|sauce|marja|berry|mansikka|vanilja|vanilla|banaani|banana|latte|cappuccino|barista|cafè|cafe|kondensoitu|condensed|maitorahka|fermented|piimä|portion|annos|viili|margar|rama\b|candies|candy|karkki|cleaner|puhdist|system|milk[- ]free|maidoton|flora|kasvirasva|levite",
        "unit": "l", "words": ("milk", "maito"),
    },
    "cream": {"match": r"kerma|cream", "exclude": r"jäätelö|ice|juusto|cheese|rahka|kastike|sauce|keitto|soup|hapan|sour|ranskan|creme fraiche|smetana|suklaa|chocolate|leivos|kakku|cake|täyte|filling|kahvi|coffee", "unit": "l", "words": ("cream", "kerma")},
    "butter": {"match": r"\bvoi\b|\bbutter\b|kirnuvoi", "exclude": r"filling|brioche|briossi|jäätelö|ice cream|juusto|cheese|curd|almond|manteli|cashew|nut\b|pähkinä|coconut|kookos|chicken|kana|bean|papu|vegetable|kasvis|filled|täytetty|flavour|maku|portion|annos|squash|kurpitsa|steak|napkin|lautasliina|bun|pulla|patty|pihvi|voileipä|sandwich|margariini|margarine|levite|spread|maapähkinä|peanut|kakku|keksi|cookie|croissant|taikina|dough|kastike|sauce|seos|blend|kasvi|plant|cocoa|kaakao|shea", "unit": "kg", "words": ("butter", "voi")},
    "wheat flour": {"match": r"vehnäjauho|wheat flour|vehnäjauhot", "exclude": r"seos|mix|täysjyvä|whole|graham|kaura|ruis|rye|buckwheat|tattari|strewing|durum|dark|tumma", "unit": "kg", "words": ("flour", "jauho")},
    "yogurt": {"match": r"jogurt|yoghurt|yogurt", "exclude": r"juoma|drink|kreikkalainen|greek|marja|berry|mansikka|vanilja|vanilla|mustikka|persikka|peach|mango|kirsikka|cherry|pätkis|kastike|kaura|oat|soija|soy|kookos|coconut|banana|banaani|fruit|hedelmä|set type", "unit": "kg", "words": ("yogurt", "yoghurt", "jogurtti")},
    "eggs": {"match": r"kananmuna|munamassa|egg", "exclude": r"pasta|nuudel|noodle|majoneesi|mayo|munakoiso|aubergine|eggplant|leipä|bread|kastike|sauce|salaatti|salad|piirakka|pie|rulla|roll|munkki", "unit": "kg", "words": ("egg", "eggs", "muna")},
}

BLOCKING = {
    "CUTOFF_PASSED": "cutoff passed",
    "DELIVERY_UNAVAILABLE": "not available",
    "SALES_BLOCK": "sales blocked",
    "QUANTITY_UNCONFIRMED": "stock unconfirmed",
    "DELIVERY_DATE_MISMATCH": "wrong delivery day",
    "DELIVERY_UNCONFIRMED": "delivery unconfirmed",
    "DIETARY_CONFLICT": "fails your diet",
    "DIETARY_UNCONFIRMED": "diet info missing",
    "PRICE_UNAVAILABLE": "no price",
    "UNIT_UNCONFIRMED": "unit unclear",
    "PRODUCT_NOT_ELIGIBLE": "not orderable",
}

LABELS = {
    "GOODS_FROM_FINLAND_BLUE_SWAN": "Hyvää Suomesta", "MADE_IN_FINLAND_FLAG_WITH_KEY": "Avainlippu",
    "FINNISH_HEART_SYMBOL": "Sydänmerkki", "EU_ORGANIC_FARMING": "Organic", "SVANEN": "Nordic Swan",
    "EU_ECO_LABEL": "EU Ecolabel", "MARINE_STEWARDSHIP_COUNCIL_LABEL": "MSC", "FAIR_TRADE_MARK": "Fairtrade",
    "RAINFOREST_ALLIANCE": "Rainforest Alliance",
}

# The fictional customer's usual products ("favourites" in the webshop). Synthetic profile data.
USUAL_PRODUCTS = {"milk": "469363", "cream": "469346", "yogurt": "465845"}
MAX_PER_ITEM = 12
RELIABILITY_FLOOR = Decimal("0.9")
RELIABILITY_PRICE_TOLERANCE = Decimal("1.15")


def family_for(query):
    text = query.casefold()
    for name, family in FAMILIES.items():
        if name in text or any(re.search(rf"\b{re.escape(word)}", text) for word in family["words"]):
            return name
    return None


def _names(raw):
    names = raw.get("synkkaData", {}).get("names", [])
    english = next((entry["value"] for entry in names if entry.get("language") == "en"), None)
    finnish = next((entry["value"] for entry in names if entry.get("language") == "fi"), None)
    return english or finnish or raw["id"], " ".join(entry.get("value", "") for entry in names)


def labels(raw):
    found = []
    for group in raw.get("synkkaData", {}).get("classifications", []):
        if group.get("name") == "packagingMarkedLabel":
            for value in group.get("values", []):
                label = LABELS.get(value.get("id"))
                if label and label not in found:
                    found.append(label)
    if raw.get("countryOfOrigin") == "fi" and "Hyvää Suomesta" not in found and "Avainlippu" not in found:
        found.append("Finnish origin")
    return found


def _base_amount(raw, unit):
    for entry in raw.get("synkkaData", {}).get("unitConversions", []):
        if entry.get("synkkaPackagingType") != "BASE_UNIT_OR_EACH":
            continue
        measure = entry.get("volume", {}) if unit == "l" else entry.get("netWeight", {})
        factor = {"LTR": 1, "MLT": Decimal("0.001"), "KGM": 1, "GRM": Decimal("0.001")}.get(measure.get("unit"))
        if factor is not None and measure.get("value") is not None:
            amount = Decimal(str(measure["value"])) * Decimal(str(factor))
            if amount > 0:
                return amount
    return None


def pack_amount(raw, unit):
    """Physical amount (litres or kg) in ONE sales unit, or None when it cannot be verified."""
    sales, base = raw.get("salesUnit"), raw.get("baseUnit")
    if {"KG": "kg", "L": "l", "LTR": "l"}.get(sales) == unit:
        return Decimal("1")
    base_amount = _base_amount(raw, unit)
    if base_amount is None:
        return None
    if sales == base:
        return base_amount
    size = next((Decimal(str(entry["sizeInBaseUnits"])) for entry in raw.get("units", []) if entry.get("unitId") == sales), None)
    return base_amount * size if size else None


def shortlist(catalog, query, unit, constraints):
    family = family_for(query)
    if not family or FAMILIES[family]["unit"] != unit:
        return family, []
    spec = FAMILIES[family]
    extra = [word for word in re.findall(r"[a-zåäö]+", query.casefold()) if word not in ("lactose", "free", "laktoositon", *spec["words"], "of", "and")]
    found = []
    for product_id, raw in catalog.products.items():
        if raw.get("deleted") or raw.get("deposits") or raw.get("synkkaData", {}).get("variableUnit") is True:
            continue
        name, all_names = _names(raw)
        text = all_names.casefold()
        if not re.search(spec["match"], text) or re.search(spec["exclude"], text):
            continue
        if extra and not all(word in text for word in extra if len(word) > 3):
            continue
        amount = pack_amount(raw, unit)
        if amount is None or amount > 30:
            continue
        evidence = catalog.evidence(product_id, {"dietaryRequirements": list(constraints.get("dietaryRequirements") or []),
                                                 "excludedAllergens": list(constraints.get("excludedAllergens") or [])})
        if any(item["state"] != "supported" for item in evidence):
            continue
        found.append({"productId": product_id, "name": name, "salesUnit": raw["salesUnit"], "packAmount": amount,
                      "unit": unit, "vendor": raw.get("vendorName", ""), "labels": labels(raw), "category": raw.get("category"),
                      "substitutes": [entry["substituteProduct"] for entry in raw.get("substitutions") or []]})
    usual = USUAL_PRODUCTS.get(family)
    found.sort(key=lambda item: (item["productId"] != usual, item["packAmount"] != 1, item["productId"]))
    return family, found[:MAX_PER_ITEM]


def reliability_map(data_dir):
    path = Path(data_dir or "data/valio") / "delivery-reliability.csv"
    result = {}
    if not path.exists():
        return result
    with path.open(encoding="utf-8-sig") as handle:
        reader = csv.reader(handle)
        next(reader, [])
        for row in reader:
            if len(row) >= 2:
                try:
                    result[row[0].strip()] = Decimal(row[-1].strip().replace(",", "."))
                except Exception:
                    continue
    return result


def _units_for(needed, pack):
    return int((Decimal(needed) / pack).to_integral_value(rounding=ROUND_CEILING))


def _money(value):
    return f"€{Decimal(value).quantize(Decimal('0.01')):,.2f}"


def _qty(value):
    value = Decimal(value)
    return f"{value:,.0f}" if value == value.to_integral_value() else f"{value:,.2f}"


def decide(item, family, candidates, checked, reliability, preference, delivery_date):
    """Return (lines, exceptions, actions, ranked) for one requested item."""
    needed = Decimal(item["quantity"])
    unit = item["unit"]
    unit_label = "L" if unit == "l" else unit
    actions, eligible = [], []
    for candidate in candidates:
        line = checked.get(candidate["productId"])
        reasons = [reason["code"] for reason in (line or {}).get("reasons", []) if reason["code"] != "INSUFFICIENT_STOCK"]
        candidate["reliability"] = reliability.get(candidate["productId"])
        if line is None or not line.get("pricing"):
            reasons = reasons or ["PRICE_UNAVAILABLE"]
        if reasons:
            why = BLOCKING.get(reasons[0], reasons[0].replace("_", " ").lower())
            closing = (line or {}).get("availability", {}).get("closingTime")
            actions.append({"code": "SKIPPED", "productId": candidate["productId"],
                            "message": f"Skipped {short(candidate)} — {why}" + (f" ({local_time(closing)})" if reasons[0] == "CUTOFF_PASSED" and closing else "")})
            continue
        availability = line["availability"]
        stock_units = Decimal(availability["availableQuantity"]) if availability.get("quantityConfirmed") else None
        unlimited = stock_units is not None and stock_units >= 999999
        unit_gross = Decimal(line["pricing"]["unitGross"])
        eligible.append({**candidate, "unitGross": unit_gross, "unitNet": Decimal(line["pricing"]["unitNet"]),
                         "perUnitGross": unit_gross / candidate["packAmount"],
                         "stockAmount": None if (stock_units is None or unlimited) else stock_units * candidate["packAmount"],
                         "stockUnits": None if unlimited else stock_units, "closingTime": availability.get("closingTime")})
    if not eligible:
        return [], [{"id": f"{family}-none", "kind": "no_product", "severity": "blocked",
                     "title": f"No {item['query']} can be delivered on time",
                     "detail": "Every matching product was unavailable, past its cutoff, or failed your dietary requirements.",
                     "options": []}], actions, []

    def rank(candidate):
        reliable = candidate["reliability"] if candidate["reliability"] is not None else Decimal("0.95")
        if preference == "reliability":
            return (-reliable, candidate["perUnitGross"])
        if preference == "sustainability":
            return (-len(candidate["labels"]), candidate["perUnitGross"])
        return (candidate["perUnitGross"], -reliable)

    ranked = sorted(eligible, key=rank)
    usual_id = USUAL_PRODUCTS.get(family)
    usual = next((candidate for candidate in eligible if candidate["productId"] == usual_id), None)
    best = ranked[0]
    if best["reliability"] is not None and best["reliability"] < RELIABILITY_FLOOR:
        safer = next((candidate for candidate in ranked[1:] if (candidate["reliability"] or 0) >= Decimal("0.98")
                      and candidate["perUnitGross"] <= best["perUnitGross"] * RELIABILITY_PRICE_TOLERANCE), None)
        if safer:
            actions.append({"code": "RELIABILITY", "productId": best["productId"],
                            "message": f"Avoided {short(best)} — only {int(best['reliability'] * 100)} % delivered in full → "
                                       f"{short(safer)}, +{_money((safer['perUnitGross'] - best['perUnitGross']) * needed)}"})
            best = safer
    primary = usual or best

    def fill(first, rest_pool):
        allocation, remaining = [], needed
        for candidate in [first] + [c for c in rest_pool if c["productId"] != first["productId"]]:
            if remaining <= 0:
                break
            cap = candidate["stockUnits"]
            units = _units_for(remaining, candidate["packAmount"])
            if cap is not None:
                units = min(units, int(cap))
            if units <= 0:
                continue
            allocation.append({"candidate": candidate, "quantity": units})
            remaining -= candidate["packAmount"] * units
        return allocation, max(remaining, Decimal("0"))

    def describe(allocation):
        lines = [{"productId": entry["candidate"]["productId"], "salesUnit": entry["candidate"]["salesUnit"], "quantity": entry["quantity"]} for entry in allocation]
        total = sum(entry["candidate"]["unitGross"] * entry["quantity"] for entry in allocation)
        return lines, total

    exceptions = []
    primary_short = primary["stockAmount"] is not None and primary["stockAmount"] < needed
    if primary_short:
        others = [candidate for candidate in ranked if candidate["productId"] != primary["productId"]]
        official = [candidate for candidate in others if candidate["productId"] in primary.get("substitutes", [])
                    or primary["productId"] in candidate.get("substitutes", [])]
        pool = official + [candidate for candidate in others if candidate not in official]
        split, split_short = fill(primary, pool)
        split_lines, split_total = describe(split)
        options = []
        alternative = next((candidate for candidate in pool if candidate["stockAmount"] is None or candidate["stockAmount"] >= needed), None)
        if alternative:
            alt_lines, alt_total = describe([{"candidate": alternative, "quantity": _units_for(needed, alternative["packAmount"])}])
            options.append({"id": "switch", "lines": alt_lines, "totalGross": str(alt_total),
                            "label": f"Switch all {_qty(needed)} {unit_label} to {short(alternative)}", "effect": _money(alt_total)})
        if len(split) > 1 and not split_short:
            filler = split[1]["candidate"]
            options.append({"id": "split", "lines": split_lines, "totalGross": str(split_total),
                            "label": f"Keep {_qty(primary['stockAmount'])} {unit_label} {short(primary)} + {_qty(needed - primary['stockAmount'])} {unit_label} {short(filler)}",
                            "effect": _money(split_total) + " · keeps your usual brand"})
        # Recommend the cheapest option that delivers the full quantity; explain the price gap on the others.
        options.sort(key=lambda option: Decimal(option["totalGross"]))
        for index, option in enumerate(options):
            option["primary"] = index == 0
            if index and options:
                option["effect"] += f" · +{_money(Decimal(option['totalGross']) - Decimal(options[0]['totalGross']))}"
        partial_lines, partial_total = describe([{"candidate": primary, "quantity": int(primary["stockUnits"])}]) if primary["stockUnits"] else ([], 0)
        if partial_lines:
            options.append({"id": "partial", "primary": not options, "lines": partial_lines, "totalGross": str(partial_total),
                            "label": f"Only {_qty(primary['stockAmount'])} {unit_label} {short(primary)}",
                            "effect": f"{_money(partial_total)} · {_qty(needed - primary['stockAmount'])} {unit_label} short"})
        best = alternative or (split[1]["candidate"] if len(split) > 1 else None)
        why = ""
        if best:
            facts = ["same lactose-free 1 L spec" if family == "milk" else "same product type"]
            if best["reliability"] is not None:
                facts.append(f"{int(best['reliability'] * 100)} % delivered in full")
            note = "Valio Aimo's official substitute" if best in official else short(best)
            why = f" {note}: {', '.join(facts)}."
        exceptions.append({"id": f"{family}-partial", "kind": "partial_stock", "severity": "decide",
                           "title": f"Only {_qty(primary['stockAmount'])} {unit_label} of your usual {short(primary)} for {day(delivery_date)}",
                           "detail": f"You need {_qty(needed)} {unit_label}.{why}",
                           "options": options})
        return [], exceptions, actions, ranked

    if usual and usual["reliability"] is not None and usual["reliability"] < RELIABILITY_FLOOR:
        safer = next((candidate for candidate in ranked if candidate is not usual and (candidate["reliability"] or 0) >= Decimal("0.98")
                      and (candidate["stockAmount"] is None or candidate["stockAmount"] >= needed)), None)
        if safer:
            usual_lines, usual_total = describe([{"candidate": usual, "quantity": _units_for(needed, usual["packAmount"])}])
            safer_lines, safer_total = describe([{"candidate": safer, "quantity": _units_for(needed, safer["packAmount"])}])
            difference = safer_total - usual_total
            exceptions.append({"id": f"{family}-reliability", "kind": "delivery_risk", "severity": "decide",
                               "title": f"Your usual {short(usual)} was delivered in full only {int(usual['reliability'] * 100)} % of the time",
                               "detail": f"For {day(delivery_date)} the agent suggests {short(safer)}: {int(safer['reliability'] * 100)} % delivered in full, same {unit_label} quantity.",
                               "options": [
                                   {"id": "switch", "primary": True, "lines": safer_lines, "totalGross": str(safer_total),
                                    "label": f"Switch to {short(safer)}", "effect": _money(safer_total) + (f" · +{_money(difference)}" if difference > 0 else f" · saves {_money(-difference)}" if difference < 0 else "")},
                                   {"id": "keep", "primary": False, "lines": usual_lines, "totalGross": str(usual_total),
                                    "label": f"Keep {short(usual)}", "effect": _money(usual_total) + " · delivery risk"}]})
            return [], exceptions, actions, ranked

    allocation, short_amount = fill(primary, ranked)
    lines, total = describe(allocation)
    if short_amount > 0:
        exceptions.append({"id": f"{family}-short", "kind": "partial_stock", "severity": "decide",
                           "title": f"Only {_qty(needed - short_amount)} of {_qty(needed)} {unit_label} available",
                           "detail": "No other eligible product can cover the rest by your delivery date.",
                           "options": [{"id": "partial", "primary": True, "lines": lines, "totalGross": str(total),
                                        "label": f"Order the {_qty(needed - short_amount)} {unit_label} available", "effect": _money(total)}]})
        return [], exceptions, actions, ranked
    chosen = allocation[0]["candidate"]
    reason = "your usual product" if usual and chosen is usual else {"price": "lowest price", "reliability": "most reliable delivery", "sustainability": "best sustainability labels"}.get(preference, "best price with reliable delivery")
    actions.append({"code": "SELECTED", "productId": chosen["productId"],
                    "message": f"Chose {short(chosen)} — {reason}, {_money(chosen['perUnitGross'])}/{unit_label}"})
    rounding = sum(entry["candidate"]["packAmount"] * entry["quantity"] for entry in allocation) - needed
    if rounding > 0:
        actions.append({"code": "PACK_ROUNDING", "productId": chosen["productId"],
                        "message": f"Rounded up {_qty(rounding)} {unit_label} to whole packs"})
    return lines, exceptions, actions, ranked


NOISE = r"hyvä suomalainen|suomesta|lactose[- ]free|laktoositon|\buht\b|\besl\b|[®™]"


def short(candidate):
    name = candidate["name"]
    vendor = candidate.get("vendor") or ""
    brand = "Arla" if "arla" in (name + vendor).casefold() else "Valio" if "valio" in (name + vendor).casefold() else ""
    compact = re.sub(NOISE, " ", name, flags=re.I)
    compact = re.sub(r"milk ?drink", "milk", compact, flags=re.I)
    compact = re.sub(r"\s+", " ", compact).strip(" ,-")
    if brand and not compact.casefold().startswith(brand.casefold()):
        compact = f"{brand} {compact}"
    return compact or name


def local_time(stamp_text):
    from datetime import datetime
    from zoneinfo import ZoneInfo
    value = datetime.fromisoformat(stamp_text.replace("Z", "+00:00")).astimezone(ZoneInfo("Europe/Helsinki"))
    return value.strftime("%a %-d %b %H:%M")


def day(iso):
    from datetime import date as _date
    value = _date.fromisoformat(iso)
    return value.strftime("%a %-d %b")
