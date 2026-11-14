"""Turn one natural-language purchasing request into structured, editable order fields.

The interpreter never decides authority, prices or stock. It only proposes field values
and records where each value came from, so the UI can ask about the uncertain ones:

- said:     stated explicitly in the request
- inferred: derived by a stated rule (e.g. "by Monday" -> next Monday)
- default:  not mentioned; a kitchen default is used and shown for confirmation
- missing:  required and unknown; the human must answer
"""

import re
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

WEEKDAYS = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6,
    "maanantai": 0, "tiistai": 1, "keskiviikko": 2, "torstai": 3, "perjantai": 4, "lauantai": 5, "sunnuntai": 6,
    "mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6,
}
UNITS = {
    "l": "l", "litre": "l", "litres": "l", "liter": "l", "liters": "l", "ltr": "l", "litraa": "l",
    "kg": "kg", "kgs": "kg", "kilo": "kg", "kilos": "kg", "kilogram": "kg", "kilograms": "kg", "kiloa": "kg",
    "pcs": "pc", "pc": "pc", "pieces": "pc", "piece": "pc",
}
GUEST_WORDS = r"(?:guests?|people|persons?|servings?|portions?|pax|covers|diners|hengelle|henkeä|annosta)"
DIET_PATTERNS = (
    ("lactose_free", r"lactose[- ]?free|laktoositon"),
    ("gluten_free", r"gluten[- ]?free|gluteeniton"),
    ("vegan", r"\bvegan\b|vegaaninen"),
    ("vegetarian", r"vegetarian|kasvis"),
)
ALLERGEN_PATTERNS = (
    ("nuts", r"\bnut(?:s)?\b(?! ?free)|nut allerg|pähkinä"),
    ("peanuts", r"peanut|maapähkinä"),
    ("eggs", r"\begg allerg|no eggs?|egg[- ]free|without eggs?|munaton"),
    ("milk", r"milk allerg|milk[- ]free|dairy[- ]free|maidoton"),
    ("fish", r"fish allerg"),
    ("sesame", r"sesame"),
    ("soybeans", r"\bsoy"),
    ("gluten_cereals", r"coeliac|celiac|keliakia"),
)
PREFERENCE_PATTERNS = (
    ("price", r"cheap|lowest price|best price|budget option|edullisin|halvin"),
    ("reliability", r"reliab|must arrive|on time|varma"),
    ("sustainability", r"sustainab|organic|luomu|eco|low[- ]carbon|climate|domestic|finnish|kotimai"),
)
PIE_WORDS = r"\bpies?\b|piirakk|quiche"
SAVORY_WORDS = r"savou?ry|vegetable|veggie|suolai|kasvispiirak"
SWEET_WORDS = r"\bsweet\b|apple|berry|dessert|makea|omena"


def _number(text):
    cleaned = text.replace(" ", "").replace(" ", "")
    if re.fullmatch(r"\d{1,3}(?:,\d{3})+", cleaned):
        cleaned = cleaned.replace(",", "")
    cleaned = cleaned.replace(",", ".")
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def _field(value, source, evidence=None):
    return {"value": value, "source": source, "evidence": evidence}


def _delivery(text, today):
    lowered = text.casefold()
    match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", lowered)
    if match:
        try:
            return _field(date.fromisoformat(match.group(1)).isoformat(), "said", match.group(0))
        except ValueError:
            pass
    match = re.search(r"\b(\d{1,2})[./](\d{1,2})(?:[./](\d{2,4}))?\b", lowered)
    if match:
        day, month = int(match.group(1)), int(match.group(2))
        year = int(match.group(3)) if match.group(3) else today.year
        year = year + 2000 if year < 100 else year
        try:
            value = date(year, month, day)
            if not match.group(3) and value < today:
                value = date(year + 1, month, day)
            return _field(value.isoformat(), "said", match.group(0))
        except ValueError:
            pass
    if re.search(r"\btomorrow\b|\bhuomenna\b", lowered):
        return _field((today + timedelta(days=1)).isoformat(), "inferred", "tomorrow")
    if re.search(r"day after tomorrow|ylihuomenna", lowered):
        return _field((today + timedelta(days=2)).isoformat(), "inferred", "day after tomorrow")
    for word, weekday in WEEKDAYS.items():
        found = re.search(rf"\b{word}\b", lowered)
        if found:
            ahead = (weekday - today.weekday()) % 7 or 7
            return _field((today + timedelta(days=ahead)).isoformat(), "inferred", found.group(0))
    return _field(None, "missing")


def _servings(text):
    match = re.search(rf"(\d[\d,.]*)\s+(?:[a-zA-ZåäöÅÄÖ-]+\s+){{0,2}}?{GUEST_WORDS}", text, re.I)
    if match:
        value = _number(match.group(1))
        if value is not None and value == value.to_integral_value() and value > 0:
            return _field(int(value), "said", match.group(0).strip())
    match = re.search(r"for\s+(\d[\d,]*)\b(?!\s*(?:l|kg|litres?|liters?|eur|€))", text, re.I)
    if match:
        value = _number(match.group(1))
        if value is not None and value == value.to_integral_value() and value > 0:
            return _field(int(value), "inferred", match.group(0).strip())
    return _field(None, "missing")


def _budget(text):
    patterns = (
        r"(?:under|below|max(?:imum)?|budget(?: of| is)?|up to|at most|alle|enintään)\s*€?\s*(\d[\d\s,.]*)\s*(?:€|eur(?:os?)?|euroa)?",
        r"€\s*(\d[\d\s,.]*)",
        r"(\d[\d\s,.]*)\s*(?:€|eur(?:os?)?\b|euroa)",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            value = _number(match.group(1).strip().rstrip(".,"))
            if value is not None and value > 0:
                return _field(str(value.quantize(Decimal("0.01"))), "said", match.group(0).strip())
    return _field(None, "default")


def _items(text):
    items = []
    pattern = r"(\d[\d\s,.]*?)\s*(" + "|".join(sorted(map(re.escape, UNITS), key=len, reverse=True)) + r")\b\.?\s*(?:of\s+)?([a-zA-ZåäöÅÄÖ][\w\s%-]*?)(?=\s+(?:by|for|on|before|until|under|max|and|,|with|delivered)\b|[,.;]|$)"
    for match in re.finditer(pattern, text, re.I):
        quantity = _number(match.group(1).strip().rstrip(".,"))
        if quantity is None or quantity <= 0:
            continue
        product = re.sub(r"\s+", " ", match.group(3)).strip(" -")
        if not product:
            continue
        items.append({"query": product, "quantity": format(quantity.normalize(), "f"),
                      "unit": UNITS[match.group(2).casefold()], "evidence": match.group(0).strip()})
    return items


def interpret(text, today, policy=None):
    """Return a structured draft with per-field provenance and only the necessary questions."""
    text = (text or "").strip()
    lowered = text.casefold()
    fields = {}
    questions = []

    items = _items(text)
    is_pie = re.search(PIE_WORDS, lowered) is not None
    kind = "recipe" if is_pie and not items else "product" if items else "unknown"
    fields["kind"] = _field(kind, "inferred" if kind != "unknown" else "missing")

    style = None
    if kind == "recipe":
        if re.search(SAVORY_WORDS, lowered):
            style = _field("savory", "said", re.search(SAVORY_WORDS, lowered).group(0))
        elif re.search(SWEET_WORDS, lowered):
            style = _field("sweet", "said", re.search(SWEET_WORDS, lowered).group(0))
        else:
            style = _field(None, "missing")
            questions.append({"field": "style", "question": "Sweet or savory pies?", "options": ["savory", "sweet"]})
    else:
        style = _field("not-a-pie", "inferred")
    fields["style"] = style

    servings = _servings(text)
    if kind == "product":
        servings = _field(1, "default") if servings["value"] is None else servings
    elif kind == "recipe" and servings["value"] is None:
        questions.append({"field": "servings", "question": "How many guests?", "options": []})
    fields["servings"] = servings

    delivery = _delivery(text, today)
    if delivery["value"] is None:
        delivery = _field((today + timedelta(days=2)).isoformat(), "default")
        delivery["note"] = "Earliest usual delivery"
    elif delivery["value"] < today.isoformat():
        delivery = {**delivery, "source": "missing"}
        questions.append({"field": "deliveryDate", "question": "That date has passed. When should it arrive?", "options": []})
    fields["deliveryDate"] = delivery

    budget = _budget(text)
    if budget["value"] is None and policy and policy.get("orderLimitMinor"):
        budget = _field(str((Decimal(policy["orderLimitMinor"]) / 100).quantize(Decimal("0.01"))), "default")
        budget["note"] = "Your per-order limit"
    fields["budget"] = budget

    diet = [key for key, pattern in DIET_PATTERNS if re.search(pattern, lowered)]
    fields["dietaryRequirements"] = _field(diet, "said" if diet else "default")
    allergens = [key for key, pattern in ALLERGEN_PATTERNS if re.search(pattern, lowered)]
    if "nuts" in allergens and "peanuts" not in allergens and re.search(r"nut allerg", lowered):
        allergens.append("peanuts")
    fields["excludedAllergens"] = _field(allergens, "said" if allergens else "default")
    preference = next((key for key, pattern in PREFERENCE_PATTERNS if re.search(pattern, lowered)), None)
    fields["preference"] = _field(preference or "balanced", "said" if preference else "default")
    fields["items"] = _field(items, "said" if items else ("missing" if kind == "product" else "default"))

    if kind == "unknown":
        questions.append({"field": "brief", "question": "What should I order, and how much? For example \"1,000 litres lactose-free milk by Monday\".", "options": []})

    brief = _clean_brief(text, kind, items)
    return {"text": text, "kind": kind, "brief": brief, "fields": fields, "questions": questions,
            "ready": not questions, "interpreter": "rules-v1"}


def _clean_brief(text, kind, items):
    if kind == "product" and items:
        return "; ".join(f"{_display(item['quantity'])} {'L' if item['unit'] == 'l' else item['unit']} {item['query']}" for item in items)
    return text


def _display(quantity):
    value = Decimal(quantity)
    return f"{value:,.0f}" if value == value.to_integral_value() else f"{value:,.2f}".rstrip("0").rstrip(".")
