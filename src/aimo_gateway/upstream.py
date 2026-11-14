import json
import logging
import time
from datetime import datetime, time as daytime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

import httpx
from dateutil import tz

from .common import Problem, stamp


HELSINKI = ZoneInfo("Europe/Helsinki")


def timestamp(value):
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            local = parsed.replace(tzinfo=tz.gettz("Europe/Helsinki"))
            if not tz.datetime_exists(local) or tz.datetime_ambiguous(local):
                raise ValueError("Ambiguous local time")
            parsed = local
        return parsed.astimezone(timezone.utc)
    except (ValueError, TypeError, OverflowError):
        raise Problem(502, "UPSTREAM_INVALID", "Invalid or ambiguous upstream timestamp") from None


def calendar_date(value):
    if isinstance(value, str) and len(value) == 10:
        try:
            return datetime.strptime(value, "%Y-%m-%d").date().isoformat()
        except ValueError:
            pass
    return timestamp(value).astimezone(HELSINKI).date().isoformat()


def number(value):
    if isinstance(value, bool) or not isinstance(value, (int, Decimal)):
        raise Problem(502, "UPSTREAM_INVALID", "Expected an exact numeric value")
    value = Decimal(value)
    if not value.is_finite() or value < 0 or value > Decimal("1000000000000"):
        raise Problem(502, "UPSTREAM_INVALID", "Unsupported numeric value")
    if value.normalize().as_tuple().exponent < -6:
        raise Problem(502, "UPSTREAM_INVALID", "Unsupported numeric precision")
    return value


def decimal_text(value):
    return format(number(value).normalize(), "f")


def preserve(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {key: preserve(item) for key, item in value.items()}
    if isinstance(value, list):
        return [preserve(item) for item in value]
    return value


class LiveSource:
    mode = "live"

    def __init__(self, api_key, transport=None):
        if not api_key:
            raise ValueError("VALIO_API_KEY is required for live mode")
        self.client = httpx.Client(
            base_url="https://junction26.valioaimo.fi", timeout=6, follow_redirects=False,
            headers={"X-API-Key": api_key, "User-Agent": "ValioAimoChallengeGateway/0.1"}, transport=transport,
        )

    def close(self):
        self.client.close()

    rate_limit_seconds = 31

    def rate_limit_wait(self, response):
        try:
            return min(max(float(response.headers.get("Retry-After", self.rate_limit_seconds)), 0), 60)
        except ValueError:
            return self.rate_limit_seconds

    def fetch(self, customer, delivery_date, products):
        payload = {"customer": customer, "requestedDate": delivery_date, "products": products}
        result = {}
        for endpoint in ("price", "availability"):
            for attempt in range(2):
                try:
                    response = self.client.post("/api/" + endpoint, json=payload)
                except httpx.RequestError as error:
                    logging.getLogger("aimo_gateway.upstream").warning("Lookup transport failure endpoint=%s class=%s", endpoint, type(error).__name__)
                    if attempt == 0:
                        time.sleep(0.1)
                        continue
                    raise Problem(503, "UPSTREAM_UNAVAILABLE") from None
                if response.status_code == 422:
                    raise Problem(502, "UPSTREAM_INVALID", "Upstream rejected the gateway request")
                if response.status_code == 200:
                    if len(response.content) > 2_000_000:
                        raise Problem(502, "UPSTREAM_INVALID")
                    try:
                        result[endpoint] = json.loads(response.content, parse_float=Decimal, parse_int=Decimal,
                                                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError()))
                    except (ValueError, UnicodeError):
                        raise Problem(502, "UPSTREAM_INVALID") from None
                    break
                logging.getLogger("aimo_gateway.upstream").warning("Lookup HTTP failure endpoint=%s status=%s", endpoint, response.status_code)
                if attempt == 0 and response.status_code == 429:
                    # Organizers: a 429 blocks the key for 30 seconds; honour it once, then report honestly.
                    time.sleep(self.rate_limit_wait(response))
                    continue
                if attempt == 0 and response.status_code >= 500:
                    time.sleep(0.1)
                    continue
                raise Problem(503, "UPSTREAM_UNAVAILABLE")
        return result


class FixtureSource:
    mode = "fixture"

    def __init__(self, clock, transform=None):
        self.clock = clock
        self.transform = transform

    def close(self):
        pass

    def fetch(self, customer, delivery_date, products):
        midnight = datetime.combine(datetime.fromisoformat(delivery_date).date(), daytime(), HELSINKI)
        price = {"customerId": customer, "currency": "EUR", "pricingDate": midnight.isoformat(), "products": []}
        availability = {"timeNow": stamp(self.clock()), "requestedDate": midnight.isoformat(), "products": []}
        validity = {"currency": "EUR", "validFrom": "2020-01-01T00:00:00+0200", "validTo": "2099-12-31T23:59:59+0200"}
        for product_id in products:
            price["products"].append({
                "productId": product_id, "quantity": Decimal("1.0"), "netPriceFound": False, "error": False,
                "catalogPrice": {**validity, "value": Decimal("1.96"), "valueWithTax": Decimal("2.22")},
                "priceWithTax": {**validity, "value": Decimal("2.22")},
                "tax": {"taxRate": Decimal("13.5"), "taxValue": Decimal("0.26")},
            })
            availability["products"].append({
                "productId": product_id, "closingTime": (midnight - timedelta(hours=7)).isoformat(),
                "salesBlock": False, "logisticModel": "Stock", "scheduleLines": [{
                    "salesBlock": False, "availableAmount": Decimal("10000"), "availableDate": delivery_date,
                    "salesUnit": "CASE" if product_id == "demo-milk" else "BAG",
                }],
            })
        result = {"price": price, "availability": availability}
        return self.transform(result) if self.transform else result