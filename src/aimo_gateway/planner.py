"""Deterministic demo planner. It proposes quantities only and has no approval, price, or commit authority."""

import copy
import csv
import re
from datetime import datetime, time as daytime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_CEILING, ROUND_HALF_UP
from fractions import Fraction
from pathlib import Path
from zoneinfo import ZoneInfo

from .catalog import ALLERGENS, CLAIMS, Catalog
from .common import stamp


AGENT_MODE = "deterministic"
PLANNER_VERSION = "deterministic-v1"
RECIPE_SOURCE = "Curated synthetic demo recipe v1"
PACK_SOURCE = "synthetic-demo-pack-v1"
LIVE_RECIPE_PRODUCTS = {
    "flour": ("460791", "460856"), "butter": ("462421",), "milk": ("463335", "464398"),
    "egg": ("468269", "468520"), "onion": ("460303", "460287"), "carrot": ("460073", "460912"),
    "potato": ("460643",), "pea": ("461238", "460461"), "apple": ("460853",), "sugar": ("460325", "468569"),
}
HELSINKI = ZoneInfo("Europe/Helsinki")
MAX_QUANTITY = 10000
PREFERENCES = ("balanced", "price", "reliability", "sustainability")
REQUEST_QUESTION_CODES = {
    "RECIPE_STYLE_REQUIRED", "UNSUPPORTED_REQUEST", "MIXED_REQUEST", "DIETARY_CONFIRMATION_REQUIRED",
    "INVALID_CONSTRAINT", "INVALID_SERVINGS", "INVALID_PANTRY", "INVALID_PREFERENCE", "QUANTITY_REQUIRED",
    "AMBIGUOUS_QUANTITY", "UNIT_CONVERSION_UNAVAILABLE", "UNSUPPORTED_RECIPE_CONSTRAINT", "PRODUCT_NOT_IN_CATALOG",
    "BRIEF_SERVINGS_IGNORED",
}
SELECTION_CODES = {
    "NO_ELIGIBLE_CANDIDATE", "INCOMPLETE_PLAN", "PRODUCT_EXCLUDED", "SUBSTITUTE_SELECTED", "PACK_ROUNDING",
    "LARGE_PACK_OVERAGE", "PRICE_UNKNOWN", "RECIPE_CHANGE", "QUANTITY_LIMIT",
}

# id, sales unit, lot, name, pack amount, pack unit, reliability, carbon kg/kg or None, net EUR,
# contained allergen keys, supported claims, contradicted claims.
_ROWS = [
    ("demo-milk", "CASE", 1, "Demo lactose-free milk case", "12", "l", "0.99", None, "18.00",
     {"milk"}, {"lactose_free", "vegetarian", "gluten_free"}, {"vegan"}),
    ("demo-flour", "BAG", 1, "Demo flour bag", "2", "kg", "0.98", "0.8", "4.50",
     {"gluten_cereals"}, {"vegan", "vegetarian", "lactose_free"}, {"gluten_free"}),
    ("demo-flour-alt", "BAG", 1, "Demo wheat flour bag 2 kg", "2", "kg", "0.91", "0.75", "4.00",
     {"gluten_cereals"}, {"vegan", "vegetarian", "lactose_free"}, {"gluten_free"}),
    ("demo-flour-gf", "BAG", 1, "Demo gluten-free flour bag 1 kg", "1", "kg", "0.94", "0.9", "6.50",
     set(), {"vegan", "vegetarian", "lactose_free", "gluten_free"}, set()),
    ("demo-butter", "TUB", 1, "Demo butter tub 1 kg", "1", "kg", "0.97", "8", "9.50",
     {"milk"}, {"vegetarian", "gluten_free"}, {"vegan", "lactose_free"}),
    ("demo-lf-butter", "TUB", 1, "Demo lactose-free butter tub 0.5 kg", "0.5", "kg", "0.95", "8.2", "11.00",
     {"milk"}, {"vegetarian", "gluten_free", "lactose_free"}, {"vegan"}),
    ("demo-margarine", "TUB", 2, "Demo vegetable margarine tub 0.5 kg", "0.5", "kg", "0.92", "1.1", "5.00",
     {"soybeans"}, {"vegan", "vegetarian", "gluten_free", "lactose_free"}, set()),
    ("demo-oat-drink", "CARTON", 1, "Demo oat drink carton 1 l", "1", "l", "0.93", None, "2.50",
     set(), {"vegan", "vegetarian", "gluten_free", "lactose_free"}, set()),
    ("demo-egg", "TRAY", 1, "Demo egg tray 30 pieces", "30", "pc", "0.96", None, "6.50",
     {"eggs"}, {"vegetarian", "gluten_free", "lactose_free"}, {"vegan"}),
    ("demo-onion", "BAG", 1, "Demo onion bag 2 kg", "2", "kg", "0.97", "0.4", "3.50",
     set(), {"vegan", "vegetarian", "gluten_free", "lactose_free"}, set()),
    ("demo-carrot", "BAG", 1, "Demo carrot bag 2 kg", "2", "kg", "0.965", "0.35", "3.00",
     set(), {"vegan", "vegetarian", "gluten_free", "lactose_free"}, set()),
    ("demo-potato", "SACK", 1, "Demo potato sack 10 kg", "10", "kg", "0.96", "0.3", "8.00",
     set(), {"vegan", "vegetarian", "gluten_free", "lactose_free"}, set()),
    ("demo-potato-small", "BAG", 1, "Demo potato bag 2 kg", "2", "kg", "0.90", "0.45", "2.50",
     set(), {"vegan", "vegetarian", "gluten_free", "lactose_free"}, set()),
    ("demo-pea", "BAG", 1, "Demo green pea bag 2.5 kg", "2.5", "kg", "0.94", "0.6", "4.00",
     set(), {"vegan", "vegetarian", "gluten_free", "lactose_free"}, set()),
    ("demo-apple", "CASE", 1, "Demo apple case 2 kg", "2", "kg", "0.95", "0.5", "5.50",
     set(), {"vegan", "vegetarian", "gluten_free", "lactose_free"}, set()),
    ("demo-sugar", "BAG", 1, "Demo sugar bag 1 kg", "1", "kg", "0.99", "0.7", "3.00",
     set(), {"vegan", "vegetarian", "gluten_free", "lactose_free"}, set()),
]
_CHANGES_RECIPE = {("flour", "demo-flour-gf"), ("butter", "demo-margarine"), ("milk", "demo-oat-drink")}
_SALES_WORDS = {
    "CASE": "case", "BAG": "bag", "TUB": "tub", "SACK": "sack", "CARTON": "carton", "TRAY": "tray",
}
_UNIT_WORDS = {
    "case": "case", "cases": "case", "bag": "bag", "bags": "bag", "tub": "tub", "tubs": "tub",
    "sack": "sack", "sacks": "sack", "carton": "carton", "cartons": "carton", "tray": "tray", "trays": "tray",
    "kg": "kg", "kgs": "kg", "kilogram": "kg", "kilograms": "kg", "l": "l", "litre": "l", "litres": "l",
    "liter": "l", "liters": "l", "pc": "pc", "pcs": "pc", "piece": "pc", "pieces": "pc",
}
_PHRASES = (
    ("gluten-free flour", "demo-flour-gf"), ("lactose-free milk", "demo-milk"), ("lactose free milk", "demo-milk"),
    ("oat drink", "demo-oat-drink"), ("wheat flour", "demo-flour"), ("green pea", "demo-pea"),
)
_SAVORY = {"vegetable", "savory", "savoury"}
_SWEET = {"sweet", "apple", "dessert", "berry"}
_PIE = {"pie", "pies"}


def _cents(value):
    return int((value * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _price(net):
    net = Decimal(net)
    rate = Decimal("14")
    tax = (net * rate / Decimal("100")).quantize(Decimal("0.01"))
    gross = net + tax
    if _cents(net + tax) != _cents(gross) or abs(_cents(net * rate / Decimal("100")) - _cents(tax)) > 1:
        raise RuntimeError("Demo price failed the gateway tax identity")
    return {"net": net, "tax": tax, "gross": gross, "rate": rate}


def _classifications(contains, supported, contradicted):
    contained, free = [], []
    fixture = {}
    for key, code in ALLERGENS.items():
        entry = {"synkkaId": code, "id": code, "unit": "CONTAINS" if key in contains else "FREE_FROM"}
        (contained if key in contains else free).append(entry)
        fixture["excludes:" + key] = "contradicted" if key in contains else "supported"
    groups = []
    if contained:
        groups.append({"name": "allergen", "type": "ENUM", "values": contained})
    if free:
        groups.append({"name": "nonAllergen", "type": "ENUM", "values": free})
    claims = []
    for claim in sorted(supported | contradicted):
        claim_id, unit = CLAIMS[claim]
        claims.append({"id": claim_id, "unit": unit if claim in supported else "CONTAINS"})
        fixture[claim] = "supported" if claim in supported else "contradicted"
    if claims:
        groups.append({"name": "nutritionalClaim", "type": "ENUM", "values": claims})
    return groups, fixture


def _build_rows():
    products, commerce = [], {}
    for row in _ROWS:
        pid, sales, lot, name, pack, pack_unit, reliability, carbon, net, contains, supported, contradicted = row
        groups, fixture = _classifications(contains, supported, contradicted)
        products.append({
            "id": pid, "salesUnit": sales, "allowedLotSize": lot, "deleted": False,
            "synkkaData": {"names": [{"language": "en", "value": name}], "classifications": groups},
            "fixtureEvidence": fixture,
            "planner": {
                "packAmount": pack, "packUnit": pack_unit, "reliability": reliability, "carbonKgPerKg": carbon,
                "source": PACK_SOURCE,
            },
        })
        commerce[pid] = {**_price(net), "salesUnit": sales, "stock": Decimal("1000")}
    return products, commerce


_PRODUCTS, _COMMERCE = _build_rows()


def demo_catalog():
    """Fixture catalog: retained demo-milk/demo-flour plus synthetic pie products."""
    return Catalog(copy.deepcopy(_PRODUCTS), "demo-planner-catalog-1", "fixture")


def _aware(value):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("clock must return a timezone-aware datetime")
    return value


class DemoSource:
    """Fixture-compatible commerce source for demo_catalog ids. Not a live supplier result."""

    mode = "fixture"
    SHORTAGE_PRODUCT = "demo-flour"
    SHORTAGE_AMOUNT = Decimal("1")
    LATE_PRODUCT = "demo-flour"

    def __init__(self, clock, scenario="normal"):
        if scenario not in ("normal", "shortage", "late"):
            raise ValueError("Unsupported demo scenario")
        self.clock = clock
        self.scenario = scenario

    def close(self):
        return None

    def fetch(self, customer, delivery_date, products):
        clock = _aware(self.clock())
        midnight = datetime.combine(datetime.fromisoformat(delivery_date).date(), daytime(), HELSINKI)
        validity = {"currency": "EUR", "validFrom": "2020-01-01T00:00:00+0200", "validTo": "2099-12-31T23:59:59+0200"}
        price = {"customerId": customer, "currency": "EUR", "pricingDate": midnight.isoformat(), "products": []}
        availability = {"timeNow": stamp(clock), "requestedDate": midnight.isoformat(), "products": []}
        late = (midnight.date() + timedelta(days=1)).isoformat()
        for product_id in products:
            known = _COMMERCE.get(product_id)
            if not known:
                price["products"].append({
                    "productId": product_id, "quantity": Decimal("1.0"), "netPriceFound": False, "error": True,
                    "catalogPrice": None, "priceWithTax": None, "tax": None,
                })
                availability["products"].append({
                    "productId": product_id, "closingTime": (midnight - timedelta(hours=7)).isoformat(),
                    "salesBlock": False, "logisticModel": "Stock", "scheduleLines": [],
                })
                continue
            amount = known["stock"]
            available = delivery_date
            if self.scenario == "shortage" and product_id == self.SHORTAGE_PRODUCT:
                amount = self.SHORTAGE_AMOUNT
            if self.scenario == "late" and product_id == self.LATE_PRODUCT:
                available = late
            price["products"].append({
                "productId": product_id, "quantity": Decimal("1.0"), "netPriceFound": True, "error": False,
                "catalogPrice": {**validity, "value": known["net"], "valueWithTax": known["gross"]},
                "priceWithTax": {**validity, "value": known["gross"]},
                "tax": {"taxRate": known["rate"], "taxValue": known["tax"]},
            })
            availability["products"].append({
                "productId": product_id, "closingTime": (midnight - timedelta(hours=7)).isoformat(),
                "salesBlock": False, "logisticModel": "Stock", "scheduleLines": [{
                    "salesBlock": False, "availableAmount": amount, "availableDate": available,
                    "salesUnit": known["salesUnit"],
                }],
            })
        return {"price": price, "availability": availability}


def _amount_text(value):
    value = Decimal(value)
    if not value.is_finite():
        raise ValueError("Non-finite amount")
    return format(value.normalize(), "f")


def _json_number(value):
    if value is None:
        return None
    text = _amount_text(value)
    return int(text) if "." not in text else float(text)


def _parse_amount(value):
    if isinstance(value, bool) or isinstance(value, float) or value is None:
        raise ValueError("Inexact amount")
    amount = Decimal(value)
    if not amount.is_finite() or amount < 0 or amount > Decimal("1000000000000"):
        raise ValueError("Unsupported amount")
    if amount.normalize().as_tuple().exponent < -6:
        raise ValueError("Unsupported precision")
    return amount


def _live_pack(raw, unit):
    sales, base = raw.get("salesUnit"), raw.get("baseUnit")
    direct = {"KG": "kg", "L": "l"}
    if direct.get(sales) == unit:
        return Decimal("1")
    if sales != base:
        return None
    conversions = [entry for entry in raw.get("synkkaData", {}).get("unitConversions", [])
                   if entry.get("synkkaPackagingType") == "BASE_UNIT_OR_EACH"]
    if len(conversions) != 1:
        return None
    conversion = conversions[0]
    measure = conversion.get("netWeight", {}) if unit == "kg" else conversion.get("volume", {})
    factors = {"kg": {"KGM": Decimal("1"), "GRM": Decimal("0.001")},
               "l": {"LTR": Decimal("1"), "MLT": Decimal("0.001")},
               "pc": {"H87": Decimal("1"), "PCE": Decimal("1")}}
    factor = factors.get(unit, {}).get(measure.get("unit"))
    if factor is None:
        return None
    try:
        amount = Decimal(str(measure["value"])) * factor
        return amount if amount.is_finite() and amount > 0 else None
    except (ValueError, KeyError, InvalidOperation):
        return None


def _labels(raw):
    found = []
    for group in raw.get("synkkaData", {}).get("classifications", []):
        if group.get("name") == "packagingMarkedLabel":
            found.extend(entry.get("id") for entry in group.get("values", []) if entry.get("id"))
        if group.get("name") == "nutritionalClaim":
            valid = set(CLAIMS.values())
            found.extend(entry["id"] for entry in group.get("values", []) if (entry.get("id"), entry.get("unit")) in valid)
    return sorted(set(found))


def _note(code, message, scope, **extra):
    item = {"code": code, "message": message, "scope": scope}
    item.update(extra)
    return item


def _packs(needed, pack, lot):
    if needed == 0:
        return 0, Decimal("0")
    if pack <= 0 or lot <= 0:
        return None
    count = (needed / pack).to_integral_value(rounding=ROUND_CEILING)
    lot = Decimal(Fraction(lot).numerator)
    if count % lot:
        count = (count / lot).to_integral_value(rounding=ROUND_CEILING) * lot
    if count < 1 or count > MAX_QUANTITY:
        return None
    return int(count), count * pack - needed


def _choice_key(candidate, preference, needed):
    packed = _packs(needed, Decimal(candidate["packAmount"]), Decimal(candidate["lotSize"]))
    overage = packed[1] if packed else Decimal("Infinity")
    quantity = packed[0] if packed else MAX_QUANTITY + 1
    reliability = None if candidate.get("reliability") is None else Decimal(str(candidate["reliability"]))
    carbon = None if candidate.get("carbonKgPerKg") is None else Decimal(str(candidate["carbonKgPerKg"]))
    missing_reliability = reliability is None
    missing_carbon = carbon is None
    reliability = reliability or Decimal("0")
    carbon = carbon if carbon is not None else Decimal("Infinity")
    product_id = candidate["productId"]
    cost = Decimal(str(candidate["unitGross"])) * quantity if candidate.get("unitGross") is not None else Decimal("Infinity")
    if preference == "price":
        return (cost, overage, quantity, product_id)
    if preference == "reliability":
        return (missing_reliability, -reliability, overage, product_id)
    if preference == "sustainability":
        return (missing_carbon, carbon, missing_reliability, -reliability, overage, product_id)
    return (missing_reliability, -reliability, cost, missing_carbon, carbon, overage, product_id)


def _choose(candidates, excluded, preference, needed):
    pool = [item for item in candidates if item["productId"] not in excluded and item.get("packAmount") is not None]
    faithful = [item for item in pool if not item.get("changesRecipe")]
    pool = faithful or pool
    usable = [item for item in pool if _packs(needed, Decimal(item["packAmount"]), Decimal(item["lotSize"]))]
    if not usable:
        return None
    return sorted(usable, key=lambda item: _choice_key(item, preference, needed))[0]


_RECIPES = {
    "vegetable-pie": {
        "title": "Vegetable wedding pies", "style": "savory", "baseServings": 10, "suggestedServings": 100,
        "ingredients": [
            ("flour", "Wheat flour", "kg", "0.5", ["demo-flour", "demo-flour-alt", "demo-flour-gf"]),
            ("butter", "Butter", "kg", "0.25", ["demo-butter", "demo-lf-butter", "demo-margarine"]),
            ("milk", "Lactose-free milk", "l", "0.2", ["demo-milk", "demo-oat-drink"]),
            ("egg", "Egg", "pc", "4", ["demo-egg"]),
            ("onion", "Onion", "kg", "0.4", ["demo-onion"]),
            ("carrot", "Carrot", "kg", "0.3", ["demo-carrot"]),
            ("potato", "Potato", "kg", "0.8", ["demo-potato", "demo-potato-small"]),
            ("pea", "Green pea", "kg", "0.3", ["demo-pea"]),
        ],
    },
    "sweet-pie": {
        "title": "Sweet apple pies", "style": "sweet", "baseServings": 10, "suggestedServings": 100,
        "ingredients": [
            ("flour", "Wheat flour", "kg", "0.45", ["demo-flour", "demo-flour-alt", "demo-flour-gf"]),
            ("butter", "Butter", "kg", "0.2", ["demo-butter", "demo-lf-butter", "demo-margarine"]),
            ("apple", "Apple", "kg", "1.2", ["demo-apple"]),
            ("sugar", "Sugar", "kg", "0.15", ["demo-sugar"]),
            ("egg", "Egg", "pc", "2", ["demo-egg"]),
        ],
    },
    "vegan-vegetable-pie": {
        "title": "Vegan vegetable pies", "style": "savory", "baseServings": 10, "suggestedServings": 100,
        "ingredients": [
            ("flour", "Wheat flour", "kg", "0.5", ["demo-flour", "demo-flour-alt", "demo-flour-gf"]),
            ("fat", "Vegetable fat", "kg", "0.25", ["demo-margarine"]),
            ("milk", "Oat drink", "l", "0.2", ["demo-oat-drink"]),
            ("onion", "Onion", "kg", "0.4", ["demo-onion"]),
            ("carrot", "Carrot", "kg", "0.3", ["demo-carrot"]),
            ("potato", "Potato", "kg", "0.8", ["demo-potato", "demo-potato-small"]),
            ("pea", "Green pea", "kg", "0.3", ["demo-pea"]),
        ],
    },
}


def _overlay(data_dir):
    reliability, carbon, warnings = {}, {}, []
    if data_dir is None:
        return reliability, carbon, warnings
    root = Path(data_dir)
    if not root.is_dir():
        warnings.append(_note("DATA_DIR_UNAVAILABLE", "Planner data directory was not readable.", "request"))
        return reliability, carbon, warnings
    reliability, warning = _read_metric(root / "delivery-reliability.csv", "deliveryReliability")
    if warning:
        warnings.append(warning)
    carbon, warning = _read_metric(root / "carbon-footprint.csv", None)
    if warning:
        warnings.append(warning)
    return reliability, carbon, warnings


def _read_metric(path, preferred):
    if not path.is_file():
        return {}, None
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.reader(handle))
    except OSError:
        return {}, _note("DATA_DIR_UNAVAILABLE", f"Could not read {path.name}.", "request")
    if not rows or "productId" not in rows[0]:
        return {}, _note("DATA_DIR_UNAVAILABLE", f"{path.name} has no productId column.", "request")
    header = rows[0]
    value_index = header.index(preferred) if preferred in header else 1 if len(header) > 1 else None
    if value_index is None:
        return {}, _note("DATA_DIR_UNAVAILABLE", f"{path.name} has no metric column.", "request")
    parsed = {}
    for row in rows[1:]:
        if len(row) <= value_index or not row[0].strip():
            continue
        try:
            amount = Decimal(row[value_index].strip())
        except (InvalidOperation, ValueError):
            continue
        if amount.is_finite() and amount >= 0:
            parsed[row[0].strip()] = amount
    return parsed, None


def _tokens(brief):
    return set(re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", brief.casefold()))


def _mentioned(text, token):
    return re.search(rf"(?<![a-z0-9-]){re.escape(token)}(?![a-z0-9-])", text) is not None


class Planner:
    agent_mode = AGENT_MODE

    def __init__(self, catalog, data_dir=None):
        self.catalog = catalog
        self.reliability, self.carbon, self.data_warnings = _overlay(data_dir)

    def recipes(self):
        return [{
            "id": recipe_id, "title": recipe["title"], "servings": recipe["suggestedServings"],
            "baseServings": recipe["baseServings"], "imageUrl": None, "style": recipe["style"],
            "recipeSource": RECIPE_SOURCE, "agentMode": AGENT_MODE,
        } for recipe_id, recipe in _RECIPES.items()]

    def plan(self, brief, servings, constraints, pantry=None, preference="balanced"):
        questions, warnings = [], list(self.data_warnings)
        if not isinstance(brief, str) or not brief.strip() or len(brief) > 4000:
            questions.append(_note("UNSUPPORTED_REQUEST", "Describe a curated pie or an explicit product quantity.", "request"))
            return self._empty(brief if isinstance(brief, str) else "", servings, preference, questions, warnings)
        servings, problem = _servings(servings)
        if problem:
            questions.append(problem)
            return self._empty(brief, None, preference, questions, warnings)
        constraints, problem = _constraints(constraints)
        if problem:
            questions.append(problem)
            return self._empty(brief, servings, preference, questions, warnings)
        if preference not in PREFERENCES:
            questions.append(_note("INVALID_PREFERENCE", "Preference must be balanced, price, reliability, or sustainability.", "request"))
            return self._empty(brief, servings, preference if isinstance(preference, str) else None, questions, warnings)
        pantry, pantry_warnings, problem = _pantry(pantry)
        warnings.extend(pantry_warnings)
        if problem:
            questions.append(problem)
            return self._empty(brief, servings, preference, questions, warnings)
        if constraints.get("dietaryConfirmed") is not True:
            questions.append(_note(
                "DIETARY_CONFIRMATION_REQUIRED",
                "Dietary requirements must be explicitly confirmed before a purchase proposal.", "request"))
        mentioned = _guest_counts(brief)
        if mentioned and servings not in mentioned:
            warnings.append(_note(
                "BRIEF_SERVINGS_IGNORED",
                "Guest count in the brief differs from the servings argument; servings is used.", "request"))
        recipe_id, recipe_questions = _recipe_choice(brief, constraints)
        questions.extend(recipe_questions)
        if self.catalog.mode == "live" and not recipe_id and re.search(r"\bmilk\b", brief, re.I) and not re.search(r"\bpie(?:s)?\b", brief, re.I):
            return self._live_milk(brief, servings, constraints, pantry, preference, warnings)
        direct_ids = _direct_ids(brief, self.catalog)
        if recipe_id and direct_ids:
            questions.append(_note("MIXED_REQUEST", "Submit the recipe and the extra product quantity as separate requests.", "request"))
        if any(item["code"] in REQUEST_QUESTION_CODES and item["code"] != "BRIEF_SERVINGS_IGNORED" for item in questions):
            return self._empty(brief, servings, preference, questions, warnings, recipe_id)
        if recipe_id:
            if recipe_id == "vegan-vegetable-pie":
                warnings.append(_note(
                    "RECIPE_VARIANT",
                    "The curated vegan vegetable pie is used instead of the egg and dairy recipe. It is not a safety certification.",
                    "request"))
            known = {item[0] for item in _RECIPES[recipe_id]["ingredients"]}
            warnings.extend(_unused_pantry(pantry, known))
            return self._finish(self._recipe_header(recipe_id, servings, preference), self._recipe_ingredients(
                _RECIPES[recipe_id], servings, pantry, constraints), preference, questions, warnings)
        if direct_ids:
            return self._direct(brief, servings, preference, constraints, pantry, direct_ids, questions, warnings)
        questions.append(_note(
            "UNSUPPORTED_REQUEST",
            "This planner covers curated pies and explicit demo or catalog quantities only. It cannot invent a recipe.",
            "request"))
        return self._empty(brief, servings, preference, questions, warnings)

    def select(self, plan, excluded_product_ids):
        if not isinstance(plan, dict) or not isinstance(plan.get("ingredients"), list):
            raise ValueError("Plan selection requires an existing plan")
        excluded = set(excluded_product_ids or [])
        preference = plan.get("preference") if plan.get("preference") in PREFERENCES else "balanced"
        questions = [item for item in plan.get("questions", []) if item.get("code") not in SELECTION_CODES]
        warnings = [item for item in plan.get("warnings", []) if item.get("code") not in SELECTION_CODES]
        for product_id in sorted(excluded):
            if any(product_id == candidate.get("productId") for ingredient in plan["ingredients"] for candidate in ingredient.get("candidates", [])):
                warnings.append(_note("PRODUCT_EXCLUDED", f"{product_id} was excluded by the integration and was not reselected.", "selection", productId=product_id))
        header = {
            "title": plan.get("title"), "recipeId": plan.get("recipeId"), "servings": plan.get("servings"),
            "recipeSource": plan.get("recipeSource"), "imageUrl": plan.get("imageUrl"), "preference": preference,
        }
        ingredients = []
        for source in plan["ingredients"]:
            item = copy.deepcopy(source)
            item["candidates"] = list(source.get("candidates") or [])
            ingredients.append(item)
        return self._finish(header, ingredients, preference, questions, warnings, excluded)

    def _recipe_header(self, recipe_id, servings, preference):
        recipe = _RECIPES[recipe_id]
        return {
            "title": recipe["title"], "recipeId": recipe_id, "servings": servings, "recipeSource": RECIPE_SOURCE,
            "imageUrl": None, "preference": preference,
        }

    def _recipe_ingredients(self, recipe, servings, pantry, constraints):
        ingredients = []
        for key, label, unit, per_base, product_ids in recipe["ingredients"]:
            if self.catalog.mode == "live" and key == "egg":
                unit, per_base, label = "kg", str(Decimal(per_base) * Decimal("0.05")), "Whole egg (50 g per recipe egg)"
            required = Decimal(per_base) * Decimal(servings) / Decimal(recipe["baseServings"])
            available = pantry.get(key, Decimal("0"))
            needed = required - available if required > available else Decimal("0")
            if self.catalog.mode == "live":
                product_ids = self._live_candidates(key, unit, constraints)
            candidates = [self._candidate(key, product_id, unit, constraints) for product_id in product_ids]
            candidates = [item for item in candidates if item]
            ingredients.append({
                "key": key, "label": label, "unit": unit, "required": _amount_text(required),
                "pantry": _amount_text(available), "needed": _amount_text(needed), "candidates": candidates,
                "primaryProductId": product_ids[0] if product_ids else None,
            })
        return ingredients

    def _candidate(self, ingredient_key, product_id, unit, constraints):
        raw = self.catalog.products.get(product_id)
        if not raw or raw.get("deleted") or self.catalog.product(product_id) is None:
            return None
        meta = raw.get("planner") or {}
        pack_unit = meta.get("packUnit")
        pack = meta.get("packAmount")
        if pack_unit != unit or pack is None:
            return None
        if not _evidence_ok(self.catalog, product_id, constraints):
            return None
        reliability, reliability_source = self._metric(product_id, meta, "reliability", self.reliability)
        carbon, carbon_source = self._metric(product_id, meta, "carbonKgPerKg", self.carbon)
        sources = [meta.get("source") or PACK_SOURCE]
        if reliability_source:
            sources.append(reliability_source)
        if carbon_source:
            sources.append(carbon_source)
        return {
            "productId": product_id, "name": self.catalog.product(product_id)["name"], "salesUnit": raw["salesUnit"],
            "packAmount": _amount_text(pack), "packUnit": pack_unit, "lotSize": _amount_text(raw["allowedLotSize"]),
            "imageUrl": None, "labels": _labels(raw), "reliability": _json_number(reliability),
            "carbonKgPerKg": _json_number(carbon) if pack_unit == "kg" else None,
            "unitNet": None, "unitGross": None, "available": None,
            "changesRecipe": (ingredient_key, product_id) in _CHANGES_RECIPE,
            "metadataSource": sorted(set(sources)),
        }

    def _metric(self, product_id, meta, field, overlay):
        if field in meta:
            return (None if meta[field] is None else Decimal(str(meta[field]))), None
        if product_id in overlay:
            filename = "delivery-reliability.csv" if field == "reliability" else "carbon-footprint.csv"
            return overlay[product_id], filename
        return None, None

    def _live_candidates(self, key, unit, constraints=None):
        options = []
        for product_id in LIVE_RECIPE_PRODUCTS.get(key, ()):
            raw = self.catalog.products.get(product_id)
            product = self.catalog.product(product_id)
            if not raw or not product:
                continue
            pack = _live_pack(raw, unit)
            if pack is None or raw.get("deposits") or raw.get("synkkaData", {}).get("variableUnit") is True:
                continue
            if constraints and not _evidence_ok(self.catalog, product_id, constraints):
                continue
            raw["planner"] = {"packAmount": _amount_text(pack), "packUnit": unit, "source": "reviewed-recipe-map-v1:catalog:units+synkkaData.unitConversions"}
            options.append((pack, product_id))
        return [product_id for _, product_id in sorted(options)[:4]]

    def _live_milk(self, brief, servings, constraints, pantry, preference, warnings):
        match = re.search(r"\b(\d+(?:\.\d+)?)\s*(?:litres?|liters?|l)\b", brief, re.I)
        if not match:
            return self._empty(brief, servings, preference, [_note("QUANTITY_REQUIRED", "Specify the milk quantity in litres.", "request")], warnings)
        constraints = copy.deepcopy(constraints)
        if re.search(r"lactose[- ]free", brief, re.I) and "lactose_free" not in constraints["dietaryRequirements"]:
            constraints["dietaryRequirements"].append("lactose_free")
        amount = Decimal(match.group(1))
        held = pantry.get("milk", Decimal("0"))
        candidates = [self._candidate("milk", product_id, "l", constraints) for product_id in self._live_candidates("milk", "l", constraints)]
        candidates = [item for item in candidates if item]
        ingredient = {"key": "milk", "label": "Milk", "unit": "l", "required": _amount_text(amount), "pantry": _amount_text(held),
                      "needed": _amount_text(max(Decimal("0"), amount - held)), "candidates": candidates,
                      "primaryProductId": candidates[0]["productId"] if candidates else None}
        return self._finish({"title": "Milk replenishment", "recipeId": None, "servings": servings,
                             "recipeSource": "Explicit milk quantity; catalog-backed packs", "imageUrl": None, "preference": preference},
                            [ingredient], preference, [], warnings)

    def _direct(self, brief, servings, preference, constraints, pantry, product_ids, questions, warnings):
        if len(product_ids) != 1:
            questions.append(_note("AMBIGUOUS_QUANTITY", "Name one catalog product and one quantity.", "request"))
            return self._empty(brief, servings, preference, questions, warnings)
        product_id = product_ids[0]
        raw = self.catalog.products.get(product_id)
        if not raw or self.catalog.product(product_id) is None:
            questions.append(_note("PRODUCT_NOT_IN_CATALOG", f"{product_id} is not in the supplied catalog.", "request"))
            return self._empty(brief, servings, preference, questions, warnings)
        parsed, problem = _direct_quantity(brief, product_id, raw, servings)
        if problem:
            questions.append(problem)
            return self._empty(brief, servings, preference, questions, warnings)
        held = pantry.get(product_id, Decimal("0"))
        parsed["pantry"] = held
        parsed["needed"] = parsed["required"] - held if parsed["required"] > held else Decimal("0")
        warnings.extend(_unused_pantry(pantry, [product_id]))
        header = {
            "title": "Direct product request", "recipeId": None, "servings": servings,
            "recipeSource": "No curated recipe; explicit catalog quantity", "imageUrl": None, "preference": preference,
        }
        if not _evidence_ok(self.catalog, product_id, constraints):
            blank = _blank_ingredient(product_id, self.catalog.product(product_id)["name"], parsed["unit"], parsed["needed"], held)
            return self._finish(header, [blank], preference, questions, warnings)
        candidate = self._direct_candidate(product_id, raw, parsed)
        if candidate is None:
            questions.append(_note(
                "UNIT_CONVERSION_UNAVAILABLE",
                "No curated pack conversion supports that unit. Sales-unit quantities can be ordered without a conversion.",
                "request"))
            return self._empty(brief, servings, preference, questions, warnings)
        ingredient = {
            "key": product_id, "label": candidate["name"], "unit": parsed["unit"],
            "required": _amount_text(parsed["required"]), "pantry": _amount_text(parsed["pantry"]),
            "needed": _amount_text(parsed["needed"]), "candidates": [candidate], "primaryProductId": product_id,
        }
        return self._finish({
            "title": "Direct product request", "recipeId": None, "servings": servings,
            "recipeSource": "No curated recipe; explicit catalog quantity", "imageUrl": None, "preference": preference,
        }, [ingredient], preference, questions, warnings)

    def _direct_candidate(self, product_id, raw, parsed):
        meta = raw.get("planner") or {}
        if parsed["mode"] == "sales":
            pack, pack_unit, carbon = "1", parsed["unit"], None
        else:
            if meta.get("packUnit") != parsed["unit"] or meta.get("packAmount") is None:
                return None
            pack, pack_unit = _amount_text(meta["packAmount"]), parsed["unit"]
            carbon = meta.get("carbonKgPerKg")
        sources = [meta.get("source") or "catalog"]
        reliability = meta.get("reliability")
        if reliability is None and product_id in self.reliability:
            reliability = self.reliability[product_id]
            sources.append("delivery-reliability.csv")
        if carbon is None and product_id in self.carbon and pack_unit == "kg":
            carbon = self.carbon[product_id]
            sources.append("carbon-footprint.csv")
        return {
            "productId": product_id, "name": self.catalog.product(product_id)["name"], "salesUnit": raw["salesUnit"],
            "packAmount": pack, "packUnit": pack_unit, "lotSize": _amount_text(raw.get("allowedLotSize") or 0),
            "imageUrl": None, "labels": _labels(raw), "reliability": _json_number(reliability),
            "carbonKgPerKg": _json_number(carbon) if pack_unit == "kg" and carbon is not None else None,
            "unitNet": None, "unitGross": None, "available": None, "changesRecipe": False,
            "metadataSource": sources,
        }

    def _finish(self, header, ingredients, preference, questions, warnings, excluded=()):
        excluded = set(excluded)
        explanations = [
            _note("DETERMINISTIC", "Deterministic planner v1; no model call.", "request"),
            _note("AUTHORITY", "The planner does not approve, price, check stock, or commit. Gateway evaluation remains authoritative.", "request"),
            _note("INFORMATIONAL_METRICS", "Reliability is a historical ratio, not a delivery promise. Carbon is a category average, not a product measurement.", "request"),
        ]
        if preference == "price":
            explanations.append(_note(
                "PRICE_UNKNOWN",
                "Price preference cannot see customer prices. Faithful candidates were ranked by pack overage only.",
                "selection"))
        resolved = []
        blocked = False
        for ingredient in ingredients:
            needed = Decimal(ingredient["needed"])
            chosen = _choose(ingredient.get("candidates") or [], excluded, preference, needed)
            if needed == 0:
                ingredient.update(productId=None, quantity=0, packAmount=None, overage="0")
                resolved.append(ingredient)
                continue
            if not chosen:
                blocked = True
                ingredient.update(productId=None, quantity=None, packAmount=None, overage=None)
                questions.append(_note(
                    "NO_ELIGIBLE_CANDIDATE",
                    f"No remaining curated candidate for {ingredient['label']} has a verified pack conversion.",
                    "selection", ingredient=ingredient["key"]))
                resolved.append(ingredient)
                continue
            packed = _packs(needed, Decimal(chosen["packAmount"]), Decimal(chosen["lotSize"]))
            if not packed:
                blocked = True
                ingredient.update(productId=None, quantity=None, packAmount=chosen["packAmount"], overage=None)
                questions.append(_note("QUANTITY_LIMIT", f"{ingredient['label']} does not fit the supported sales-unit range.", "selection", ingredient=ingredient["key"]))
                resolved.append(ingredient)
                continue
            quantity, overage = packed
            ingredient.update(productId=chosen["productId"], quantity=quantity, packAmount=chosen["packAmount"], overage=_amount_text(overage))
            explanations.append(_note(
                "PACK_ROUNDING",
                f"{ingredient['label']}: {ingredient['needed']} {ingredient['unit']} needs {quantity} x {chosen['packAmount']} {chosen['packUnit']} {chosen['salesUnit']}.",
                "selection", ingredient=ingredient["key"], productId=chosen["productId"]))
            if overage > needed or (needed > 0 and overage / needed > Decimal("0.5")):
                warnings.append(_note(
                    "LARGE_PACK_OVERAGE",
                    f"{ingredient['label']} pack rounding orders {_amount_text(overage)} {ingredient['unit']} above the needed amount.",
                    "selection", ingredient=ingredient["key"], productId=chosen["productId"]))
            primary = ingredient.get("primaryProductId")
            if primary and chosen["productId"] != primary:
                explanations.append(_note(
                    "SUBSTITUTE_SELECTED",
                    f"Selected {chosen['productId']} instead of {primary}. This is a curated demo mapping, not a quality or safety guarantee.",
                    "selection", ingredient=ingredient["key"], productId=chosen["productId"]))
            if chosen.get("changesRecipe"):
                warnings.append(_note(
                    "RECIPE_CHANGE",
                    f"{chosen['name']} changes the curated ingredient character and was used only because the primary candidate was ineligible or excluded.",
                    "selection", ingredient=ingredient["key"], productId=chosen["productId"]))
            resolved.append(ingredient)
        if blocked:
            questions.append(_note("INCOMPLETE_PLAN", "The purchase lines were withheld because at least one required ingredient is unresolved.", "selection"))
        request_block = any(item["code"] in REQUEST_QUESTION_CODES and item["code"] != "BRIEF_SERVINGS_IGNORED" for item in questions)
        lines = [] if blocked or request_block else _lines(resolved)
        if lines is None:
            questions.append(_note("QUANTITY_LIMIT", "Combined sales quantity exceeds the gateway maximum.", "selection"))
            lines = []
        plan = {
            **header, "agentMode": AGENT_MODE, "plannerVersion": PLANNER_VERSION, "questions": questions,
            "warnings": warnings, "explanations": explanations, "ingredients": [_public_ingredient(item) for item in resolved],
            "lines": lines, "comparison": _comparison(resolved if lines else []), "complete": not questions,
        }
        return plan

    def _empty(self, brief, servings, preference, questions, warnings, recipe_id=None):
        title = brief.strip() if isinstance(brief, str) and brief.strip() else "Unsupported request"
        return self._finish({
            "title": title[:120], "recipeId": recipe_id, "servings": servings, "recipeSource": RECIPE_SOURCE,
            "imageUrl": None, "preference": preference if preference in PREFERENCES else None,
        }, [], preference if preference in PREFERENCES else "balanced", questions, warnings)


def _public_ingredient(ingredient):
    return {
        "key": ingredient["key"], "label": ingredient["label"], "unit": ingredient["unit"],
        "required": ingredient["required"], "pantry": ingredient["pantry"], "needed": ingredient["needed"],
        "productId": ingredient.get("productId"), "quantity": ingredient.get("quantity"),
        "packAmount": ingredient.get("packAmount"), "overage": ingredient.get("overage"),
        "primaryProductId": ingredient.get("primaryProductId"), "candidates": ingredient.get("candidates") or [],
    }


def _blank_ingredient(key, label, unit, needed, pantry=Decimal("0")):
    return {
        "key": key, "label": label, "unit": unit, "required": _amount_text(needed + pantry), "pantry": _amount_text(pantry),
        "needed": _amount_text(needed), "candidates": [], "primaryProductId": None,
    }


def _lines(ingredients):
    merged, order = {}, []
    for ingredient in ingredients:
        quantity = ingredient.get("quantity")
        if not quantity:
            continue
        candidate = next(item for item in ingredient["candidates"] if item["productId"] == ingredient["productId"])
        key = (candidate["productId"], candidate["salesUnit"])
        if key not in merged:
            order.append(key)
            merged[key] = 0
        merged[key] += quantity
    if any(quantity > MAX_QUANTITY for quantity in merged.values()):
        return None
    return [{"productId": product_id, "salesUnit": sales_unit, "quantity": quantity} for (product_id, sales_unit), quantity in ((key, merged[key]) for key in order)]


def _comparison(ingredients):
    selected = []
    for ingredient in ingredients:
        if not ingredient.get("quantity"):
            continue
        candidate = next((item for item in ingredient["candidates"] if item["productId"] == ingredient["productId"]), None)
        if candidate:
            selected.append((ingredient, candidate))
    if not selected:
        return {"reliability": None, "carbonKgEstimate": None, "carbonCoverage": 0}
    reliabilities = [Decimal(str(candidate["reliability"])) for _, candidate in selected if candidate.get("reliability") is not None]
    reliability = min(reliabilities) if len(reliabilities) == len(selected) else None
    covered, estimate = 0, Decimal("0")
    for ingredient, candidate in selected:
        if ingredient["unit"] == "kg" and candidate.get("carbonKgPerKg") is not None:
            covered += 1
            estimate += Decimal(str(candidate["carbonKgPerKg"])) * Decimal(candidate["packAmount"]) * Decimal(ingredient["quantity"])
    return {
        "reliability": _json_number(reliability),
        "carbonKgEstimate": _json_number(estimate) if covered else None,
        "carbonCoverage": _json_number(Decimal(covered) / Decimal(len(selected))) if covered else 0,
    }


def _servings(value):
    if isinstance(value, bool) or isinstance(value, float) or isinstance(value, str) or not isinstance(value, int):
        return None, _note("INVALID_SERVINGS", "Servings must be a positive integer.", "request")
    if value < 1 or value > 10000:
        return None, _note("INVALID_SERVINGS", "Servings must be from 1 to 10000.", "request")
    return value, None


def _constraints(value):
    if not isinstance(value, dict):
        return None, _note("INVALID_CONSTRAINT", "Constraints must be an object.", "request")
    requirements, allergens = value.get("dietaryRequirements", []), value.get("excludedAllergens", [])
    if not isinstance(requirements, list) or not isinstance(allergens, list):
        return None, _note("INVALID_CONSTRAINT", "Dietary requirements and excluded allergens must be arrays.", "request")
    if any(not isinstance(item, str) for item in requirements + allergens):
        return None, _note("INVALID_CONSTRAINT", "Constraint values must be strings.", "request")
    if any(item not in CLAIMS for item in requirements) or any(item not in ALLERGENS for item in allergens):
        return None, _note("INVALID_CONSTRAINT", "A dietary requirement or allergen is outside the gateway vocabulary.", "request")
    if len(set(requirements)) != len(requirements) or len(set(allergens)) != len(allergens):
        return None, _note("INVALID_CONSTRAINT", "Constraint values must be unique.", "request")
    recipe_id = value.get("recipeId")
    if recipe_id is not None and recipe_id not in _RECIPES:
        return None, _note("INVALID_CONSTRAINT", "recipeId is not a curated recipe.", "request")
    return value, None


def _pantry(value):
    if value is None:
        return {}, [], None
    if not isinstance(value, dict):
        return {}, [], _note("INVALID_PANTRY", "Pantry must be an object of ingredient amounts.", "request")
    parsed, warnings = {}, []
    for key, amount in value.items():
        if not isinstance(key, str):
            return {}, warnings, _note("INVALID_PANTRY", "Pantry keys must be strings.", "request")
        try:
            parsed[key] = _parse_amount(amount)
        except (ValueError, ArithmeticError):
            return {}, warnings, _note("INVALID_PANTRY", f"Pantry amount for {key} must be a nonnegative exact number.", "request")
    return parsed, warnings, None


def _guest_counts(brief):
    return [int(item) for item in re.findall(r"(\d+)\s*(?:guests|servings|people|portions)\b", brief, flags=re.I)]


def _recipe_choice(brief, constraints):
    text = brief.casefold()
    tokens = _tokens(brief)
    explicit = []
    if constraints.get("recipeId"):
        explicit.append(constraints["recipeId"])
    explicit.extend(recipe_id for recipe_id in _RECIPES if recipe_id in tokens or _mentioned(text, recipe_id))
    explicit = list(dict.fromkeys(explicit))
    if len(explicit) > 1:
        return None, [_note("UNSUPPORTED_RECIPE_CONSTRAINT", "The brief names more than one curated recipe.", "request")]
    if len(explicit) == 1:
        return explicit[0], []
    savory, sweet, pie = bool(tokens & _SAVORY), bool(tokens & _SWEET), bool(tokens & _PIE)
    vegan = "vegan" in constraints.get("dietaryRequirements", []) or "vegan" in tokens
    if pie and savory and sweet:
        return None, [_note("RECIPE_STYLE_REQUIRED", "Say whether the pies should be savory vegetable or sweet. Both styles were mentioned.", "request", options=["vegetable-pie", "sweet-pie"])]
    if pie and sweet:
        if vegan:
            return None, [_note("UNSUPPORTED_RECIPE_CONSTRAINT", "No curated vegan sweet pie is available. Provide a reviewed recipe rather than dropping ingredients.", "request")]
        return "sweet-pie", []
    if pie and savory:
        return ("vegan-vegetable-pie" if vegan else "vegetable-pie"), []
    if pie or "wedding" in tokens:
        return None, [_note(
            "RECIPE_STYLE_REQUIRED",
            "Say whether the pies should be savory vegetable or sweet. The word pies does not select a recipe.",
            "request", options=["vegetable-pie", "sweet-pie"])]
    return None, []


def _direct_ids(brief, catalog):
    text = brief.casefold()
    found = []
    for product_id in catalog.products:
        if _mentioned(text, product_id.casefold()):
            found.append(product_id)
    for phrase, product_id in _PHRASES:
        if _mentioned(text, phrase) and product_id not in found:
            found.append(product_id)
    return found


def _evidence_ok(catalog, product_id, constraints):
    evidence = catalog.evidence(product_id, {
        "dietaryRequirements": list(constraints.get("dietaryRequirements") or []),
        "excludedAllergens": list(constraints.get("excludedAllergens") or []),
    })
    return all(item["state"] == "supported" for item in evidence)


def _direct_quantity(brief, product_id, raw, servings):
    text = f" {re.sub(r'\\s+', ' ', brief.casefold())} "
    names = [product_id.casefold()] + [phrase for phrase, target in _PHRASES if target == product_id]
    matches = []
    for name in names:
        pattern = rf"(\d+(?:\.\d+)?)\s*([a-z]+)?\s*(?:of\s+)?{re.escape(name)}(\s+per\s+(?:serving|guest|person))?"
        matches.extend(re.finditer(pattern, text))
    if not matches:
        return None, _note("QUANTITY_REQUIRED", f"Give a quantity and unit for {product_id}.", "request")
    if len(matches) > 1:
        return None, _note("AMBIGUOUS_QUANTITY", f"More than one quantity was given for {product_id}.", "request")
    match = matches[0]
    try:
        quantity = _parse_amount(match.group(1))
    except ValueError:
        return None, _note("QUANTITY_REQUIRED", "The product quantity must be an exact nonnegative number.", "request")
    if match.group(3):
        quantity *= Decimal(servings)
    supplied_unit = (match.group(2) or "").casefold()
    unit = _UNIT_WORDS.get(supplied_unit)
    if supplied_unit == str(raw.get("salesUnit", "")).casefold():
        unit = supplied_unit
    if not unit:
        return None, _note("UNIT_CONVERSION_UNAVAILABLE", "Give a sales unit or a curated physical unit; the planner will not infer one.", "request")
    sales_word = _SALES_WORDS.get(raw.get("salesUnit"), str(raw.get("salesUnit", "")).casefold())
    meta = raw.get("planner") or {}
    pantry = Decimal("0")
    if unit == sales_word:
        if quantity != quantity.to_integral_value():
            return None, _note("UNIT_CONVERSION_UNAVAILABLE", "Fractional sales units are not ordered in v1.", "request")
        required = quantity
        return {"mode": "sales", "unit": raw["salesUnit"], "required": required, "pantry": pantry, "needed": required}, None
    if unit == meta.get("packUnit"):
        return {"mode": "physical", "unit": unit, "required": quantity, "pantry": pantry, "needed": quantity}, None
    return None, _note("UNIT_CONVERSION_UNAVAILABLE", f"No curated conversion from {unit} to {raw.get('salesUnit')}.", "request")


def _unused_pantry(pantry, keys):
    unused = sorted(set(pantry) - set(keys))
    if not unused:
        return []
    return [_note("PANTRY_UNUSED", "Unused pantry keys: " + ", ".join(unused) + ".", "request")]
