from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from .common import Problem, identity, stamp
from .upstream import calendar_date, decimal_text, number, preserve, timestamp


def cents(value):
    result = int((value * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    if result < 0 or result > 1_000_000_000_000:
        raise Problem(502, "UPSTREAM_INVALID", "Amount exceeds the supported range")
    return result


def reason(code, product_id=None, message=None):
    result = {"code": code, "message": message or code.replace("_", " ").capitalize()}
    if product_id:
        result["productId"] = product_id
    return result


def indexed(records, products):
    if not isinstance(records, list) or any(not isinstance(item, dict) for item in records):
        raise Problem(502, "UPSTREAM_INVALID")
    result = {item["productId"]: item for item in records}
    if len(result) != len(records) or set(result) != set(products):
        raise Problem(502, "UPSTREAM_INVALID", "Upstream product set mismatch")
    return result


def pricing(raw, quantity, pricing_date):
    if not isinstance(raw["error"], bool) or not isinstance(raw["netPriceFound"], bool):
        raise Problem(502, "UPSTREAM_INVALID")
    if number(raw["quantity"]) != 1:
        raise Problem(502, "UPSTREAM_INVALID")
    if raw["error"] or any(raw.get(field) is None for field in ("catalogPrice", "priceWithTax", "tax")):
        return None
    net, gross, tax = raw["catalogPrice"], raw["priceWithTax"], raw["tax"]
    for price in (net, gross):
        if price["currency"] != "EUR" or not timestamp(price["validFrom"]) <= pricing_date <= timestamp(price["validTo"]):
            raise Problem(502, "UPSTREAM_INVALID", "Invalid price currency or validity window")
    unit_net, unit_gross = number(net["value"]), number(gross["value"])
    tax_rate, tax_value = number(tax["taxRate"]), number(tax["taxValue"])
    if tax_rate > 100 or unit_gross < unit_net or number(net["valueWithTax"]) != unit_gross:
        raise Problem(502, "UPSTREAM_INVALID", "Inconsistent gross price")
    if cents(unit_net + tax_value) != cents(unit_gross) or abs(cents(unit_net * tax_rate / 100) - cents(tax_value)) > 1:
        raise Problem(502, "UPSTREAM_INVALID", "Inconsistent tax data")
    net_total, gross_total = cents(unit_net * quantity), cents(unit_gross * quantity)
    return {"unitNet": decimal_text(unit_net), "unitGross": decimal_text(unit_gross),
            "taxRate": decimal_text(tax_rate), "netMinor": net_total, "grossMinor": gross_total,
            "taxMinor": gross_total - net_total, "netPriceFound": raw["netPriceFound"]}


def availability(raw, line, delivery_date, clock, upstream_now):
    if not isinstance(raw["salesBlock"], bool) or not isinstance(raw["scheduleLines"], list):
        raise Problem(502, "UPSTREAM_INVALID")
    model = raw.get("logisticModel")
    if model is not None and not isinstance(model, str):
        raise Problem(502, "UPSTREAM_INVALID")
    result = {"logisticModel": model if model in ("Stock", "Terminal") else "Unknown",
              "quantityConfirmed": False, "salesUnit": line["salesUnit"], "salesBlock": raw["salesBlock"]}
    codes = ["SALES_BLOCK"] if raw["salesBlock"] else []
    schedules = raw["scheduleLines"]
    if not schedules:
        return result, codes + ["DELIVERY_UNAVAILABLE"]
    if len(schedules) != 1:
        raise Problem(502, "UPSTREAM_INVALID", "Multiple schedule lines unsupported")
    schedule = schedules[0]
    if not isinstance(schedule["salesBlock"], bool) or not isinstance(schedule["salesUnit"], str):
        raise Problem(502, "UPSTREAM_INVALID")
    result["salesBlock"] = result["salesBlock"] or schedule["salesBlock"]
    if schedule["salesBlock"]:
        codes.append("SALES_BLOCK")
    amount = number(schedule["availableAmount"])
    if model != "Stock" or amount == 999999:
        codes.append("QUANTITY_UNCONFIRMED")
    else:
        result.update(quantityConfirmed=True, availableQuantity=decimal_text(amount))
        if amount < line["quantity"]:
            codes.append("INSUFFICIENT_STOCK")
    if schedule["salesUnit"] != line["salesUnit"]:
        codes.append("UNIT_UNCONFIRMED")
    if schedule.get("availableDate") is None or raw.get("closingTime") is None:
        codes.append("DELIVERY_UNCONFIRMED")
    else:
        result["availableDate"] = calendar_date(schedule["availableDate"])
        closing = timestamp(raw["closingTime"])
        result["closingTime"] = stamp(closing)
        if result["availableDate"] != delivery_date:
            codes.append("DELIVERY_DATE_MISMATCH")
        if closing <= max(clock, upstream_now):
            codes.append("CUTOFF_PASSED")
    return result, sorted(set(codes))


def retained_source(data):
    if not data:
        return {}
    def pick(value, keys):
        return {key: value[key] for key in keys if key in value}
    price = pick(data["price"], ("customerId", "currency", "pricingDate"))
    price["products"] = []
    for raw in data["price"]["products"]:
        record = pick(raw, ("productId", "quantity", "error", "netPriceFound"))
        for field in ("catalogPrice", "priceWithTax", "tax"):
            if raw.get(field) is not None:
                record[field] = pick(raw[field], ("value", "valueWithTax", "currency", "validFrom", "validTo", "taxRate", "taxValue"))
        price["products"].append(record)
    stock = pick(data["availability"], ("timeNow", "requestedDate"))
    stock["products"] = []
    for raw in data["availability"]["products"]:
        record = pick(raw, ("productId", "closingTime", "logisticModel", "salesBlock"))
        record["scheduleLines"] = [pick(line, ("salesBlock", "availableAmount", "availableDate", "salesUnit")) for line in raw["scheduleLines"]]
        stock["products"].append(record)
    return preserve({"price": price, "availability": stock})


class Evaluator:
    def __init__(self, catalog, source, clock):
        self.catalog, self.source, self.clock = catalog, source, clock

    def evaluate(self, request, basket, policy, spent):
        try:
            return self._evaluate(request, basket, policy, spent)
        except (KeyError, TypeError, ValueError, ArithmeticError, AttributeError):
            raise Problem(502, "UPSTREAM_INVALID", "Malformed or unsupported commerce data") from None

    def _evaluate(self, request, basket, policy, spent):
        started = self.clock()
        intent = request["intent"]
        lines, shortlist = [], []
        for proposed in basket["lines"]:
            product_id = proposed["productId"]
            product = self.catalog.product(product_id)
            eligible = policy.get("eligibleProducts")
            line = {**(product or {"name": "Unavailable product", "constraintEvidence": []}), **proposed, "reasons": []}
            lines.append(line)
            if not product or (eligible is not None and product_id not in eligible):
                line["name"] = "Unavailable product"
                line["reasons"].append(reason("PRODUCT_NOT_ELIGIBLE", product_id))
                continue
            raw = self.catalog.products[product_id]
            if raw.get("deposits") or raw.get("synkkaData", {}).get("variableUnit") is True:
                line["reasons"].append(reason("PRODUCT_NOT_ELIGIBLE", product_id, "Deposits/variable weight are unsupported in v1"))
            lot = number(raw.get("allowedLotSize", 0))
            if product["salesUnit"] != proposed["salesUnit"] or not lot or Decimal(proposed["quantity"]) % lot:
                line["reasons"].append(reason("UNIT_UNCONFIRMED", product_id))
            line["constraintEvidence"] = self.catalog.evidence(product_id, intent["constraints"])
            for evidence in line["constraintEvidence"]:
                if evidence["state"] != "supported":
                    code = "DIETARY_CONFLICT" if evidence["state"] == "contradicted" else "DIETARY_UNCONFIRMED"
                    line["reasons"].append(reason(code, product_id, "Constraint not satisfied: " + evidence["constraint"]))
            shortlist.append(product_id)
        raw_data = self.source.fetch(policy["upstreamCustomer"], intent["requestedDeliveryDate"], shortlist) if shortlist else {}
        if shortlist:
            prices, stocks = raw_data["price"], raw_data["availability"]
            if prices["customerId"] != policy["upstreamCustomer"] or prices["currency"] != "EUR":
                raise Problem(502, "UPSTREAM_INVALID", "Upstream customer/currency mismatch")
            if any(calendar_date(value) != intent["requestedDeliveryDate"] for value in (prices["pricingDate"], stocks["requestedDate"])):
                raise Problem(502, "UPSTREAM_INVALID", "Upstream date mismatch")
            upstream_now = timestamp(stocks["timeNow"])
            if abs((self.clock() - upstream_now).total_seconds()) > 60:
                raise Problem(503, "UPSTREAM_CLOCK_UNTRUSTED")
            price_map, stock_map = indexed(prices["products"], shortlist), indexed(stocks["products"], shortlist)
            for line in lines:
                product_id = line["productId"]
                if product_id not in price_map:
                    continue
                price = pricing(price_map[product_id], line["quantity"], timestamp(prices["pricingDate"]))
                if price is None:
                    line["reasons"].append(reason("PRICE_UNAVAILABLE", product_id))
                else:
                    line["pricing"] = price
                line["availability"], codes = availability(stock_map[product_id], line, intent["requestedDeliveryDate"], self.clock(), upstream_now)
                line["reasons"].extend(reason(code, product_id) for code in codes)
        reasons = [item for line in lines for item in line["reasons"]]
        evaluation = {"id": identity(), "basketId": basket["id"], "basketVersion": basket["version"],
                      "requestId": request["id"], "customerId": request["customerId"], "policyVersion": policy["version"],
                      "catalogVersion": self.catalog.version, "mode": self.catalog.mode, "checkedAt": stamp(started),
                      "expiresAt": stamp(started + timedelta(seconds=120)), "evidenceId": identity(), "lines": lines, "reasons": reasons}
        if all("pricing" in line for line in lines):
            totals = {field: sum(line["pricing"][field] for line in lines) for field in ("netMinor", "grossMinor", "taxMinor")}
            if max(totals.values()) > 1_000_000_000_000:
                raise Problem(502, "UPSTREAM_INVALID", "Unsupported basket amount")
            evaluation["totals"] = {**totals, "currency": "EUR", "basis": "goods_only"}
            for failed, code in (
                (totals["grossMinor"] > intent["maxGrossMinor"], "REQUEST_BUDGET_EXCEEDED"),
                (totals["grossMinor"] > policy["orderLimitMinor"], "ORDER_LIMIT_EXCEEDED"),
                (totals["grossMinor"] + spent > policy["dailyLimitMinor"], "DAILY_LIMIT_EXCEEDED"),
                (intent["deliverySiteId"] not in policy["sites"], "PRODUCT_NOT_ELIGIBLE"),
            ):
                if failed:
                    reasons.append(reason(code))
        evaluation["outcome"] = "blocked" if reasons else "allowed"
        if not reasons and evaluation["totals"]["grossMinor"] > policy["autonomousLimitMinor"]:
            evaluation["outcome"] = "approval_required"
            reasons.append(reason("APPROVAL_THRESHOLD_EXCEEDED"))
        cutoffs = [timestamp(line["availability"]["closingTime"]) for line in lines if line.get("availability", {}).get("closingTime")]
        evaluation["expiresAt"] = stamp(min([started + timedelta(seconds=120), *cutoffs]))
        evidence = {"id": evaluation["evidenceId"], "customer": policy["upstreamCustomer"],
                    "requestedDate": intent["requestedDeliveryDate"], "products": shortlist,
                    "fetchedAt": stamp(self.clock()), "source": retained_source(raw_data), "normalized": evaluation}
        return evaluation, evidence