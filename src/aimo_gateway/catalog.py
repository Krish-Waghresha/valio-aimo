import hashlib
import json
from decimal import Decimal
from pathlib import Path


CLAIMS = {
    "lactose_free": ("FREE_FROM_LACTOSE", "FREE_FROM"),
    "gluten_free": ("FREE_FROM_GLUTEN", "FREE_FROM"),
    "vegetarian": ("VEGETARIAN", "DIET"),
    "vegan": ("VEGAN", "DIET"),
}

ALLERGENS = {
    "gluten_cereals": "AW", "crustaceans": "AC", "eggs": "AE", "fish": "AF", "peanuts": "AP",
    "soybeans": "AY", "milk": "AM", "nuts": "AN", "celery": "BC", "mustard": "BM",
    "sesame": "AS", "sulphites": "AU", "lupin": "NL", "molluscs": "UM",
}
SUBTYPES = {
    "AW": {"GB", "GK", "GO", "GS", "NR", "UW", "TR"},
    "AN": {"SA", "SC", "SH", "SM", "SP", "SR", "ST", "SW"},
    "AM": {"GOM"},
}


def allergen_evidence(groups, code, product_id):
    relevant = {code} | SUBTYPES.get(code, set())
    known = set(ALLERGENS.values()) | set().union(*SUBTYPES.values()) | {"ML"}
    matches, sources = [], []
    ambiguous = False
    for group_index, group in enumerate(groups):
        if group.get("name") not in ("allergen", "nonAllergen"):
            continue
        for value_index, entry in enumerate(group.get("values", [])):
            entry_code = entry.get("synkkaId") or entry.get("id")
            if entry_code in relevant:
                matches.append((entry_code, entry.get("unit")))
                sources.append(f"catalog:{product_id}:synkkaData.classifications[{group_index}].values[{value_index}]")
            if entry_code not in known and entry.get("unit") != "FREE_FROM":
                ambiguous = True
    if any(unit in ("CONTAINS", "MAY_CONTAIN") for _, unit in matches):
        return "contradicted", sources
    if matches and any(found == code for found, _ in matches) and all(unit == "FREE_FROM" for _, unit in matches) and not ambiguous:
        return "supported", sources
    return "unknown", sources


class Catalog:
    def __init__(self, products, version, mode):
        self.products = {product["id"]: product for product in products}
        if len(self.products) != len(products):
            raise ValueError("Duplicate catalog product IDs")
        self.version = version
        self.mode = mode

    @classmethod
    def load(cls, path):
        content = Path(path).read_bytes()
        return cls(json.loads(content, parse_float=Decimal), hashlib.sha256(content).hexdigest(), "live")

    @classmethod
    def fixture(cls):
        return cls([{
            "id": "demo-milk", "salesUnit": "CASE", "allowedLotSize": 1, "deleted": False,
            "synkkaData": {"names": [{"language": "en", "value": "Demo lactose-free milk case"}], "classifications": [
                {"name": "nutritionalClaim", "values": [{"id": "FREE_FROM_LACTOSE", "unit": "FREE_FROM"}]},
            ]},
            "fixtureEvidence": {"excludes:milk": "contradicted", "excludes:peanuts": "supported"},
        }, {
            "id": "demo-flour", "salesUnit": "BAG", "allowedLotSize": 1, "deleted": False,
            "synkkaData": {"names": [{"language": "en", "value": "Demo flour bag"}]},
            "fixtureEvidence": {"excludes:gluten_cereals": "contradicted"},
        }], "fixture-catalog-1", "fixture")

    def product(self, product_id):
        raw = self.products.get(product_id)
        if not raw or raw.get("deleted"):
            return None
        names = raw.get("synkkaData", {}).get("names", [])
        name = next((entry["value"] for entry in names if entry.get("language") == "en"), None)
        name = name or next((entry["value"] for entry in names if entry.get("language") == "fi"), product_id)
        return {"productId": product_id, "name": name, "salesUnit": raw["salesUnit"], "constraintEvidence": []}

    def evidence(self, product_id, constraints):
        raw = self.products[product_id]
        groups = raw.get("synkkaData", {}).get("classifications", [])
        result = []
        needed = list(constraints["dietaryRequirements"]) + ["excludes:" + item for item in constraints["excludedAllergens"]]
        for constraint in needed:
            state, sources = "unknown", []
            if constraint.startswith("excludes:"):
                code = ALLERGENS.get(constraint.removeprefix("excludes:"))
                if code:
                    state, sources = allergen_evidence(groups, code, product_id)
            if constraint in CLAIMS:
                claim, unit = CLAIMS[constraint]
                found = [entry for group in groups if group.get("name") == "nutritionalClaim"
                         for entry in group.get("values", []) if entry.get("id") == claim]
                if found:
                    state = "supported" if all(entry.get("unit") == unit for entry in found) else "contradicted"
                    sources = [f"catalog:{product_id}:synkkaData.classifications.nutritionalClaim:{claim}"]
            if self.mode == "fixture" and constraint in raw.get("fixtureEvidence", {}):
                state = raw["fixtureEvidence"][constraint]
                sources = [f"fixture:{product_id}:{constraint}"]
            result.append({"constraint": constraint, "state": state, "sourceRefs": sources})
        return result

    def search(self, query, limit, eligible):
        result = []
        for product_id in self.products:
            if eligible is not None and product_id not in eligible:
                continue
            product = self.product(product_id)
            if product and query.casefold() in (product_id + " " + product["name"]).casefold():
                product["constraintEvidence"] = self.evidence(product_id, {"dietaryRequirements": list(CLAIMS), "excludedAllergens": []})
                result.append(product)
            if len(result) == limit:
                break
        return {"catalogVersion": self.version, "products": result}