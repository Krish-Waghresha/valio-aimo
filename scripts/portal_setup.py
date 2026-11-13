#!/usr/bin/env python3
"""Download challenge resources and check read-only APIs using Python's stdlib."""

import argparse
import csv
import io
import json
import os
import re
import sys
from datetime import date, datetime, timedelta, timezone
from html.parser import HTMLParser
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin, urlsplit
from urllib.request import HTTPCookieProcessor, Request, build_opener
from zoneinfo import ZoneInfo


BASE_URL = "https://junction26.valioaimo.fi"
ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "valio"
RESOURCES = {
    "valio_aimo_junction26_product_data.json": "products.json",
    "valio_aimo_junction26_product_data_schema.json": "product-schema.json",
    "valio_aimo_junction26_delivery_reliability.csv": "delivery-reliability.csv",
    "valio_aimo_junction26_carbon_footprint.csv": "carbon-footprint.csv",
}


class ResourceLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = {}

    def handle_starttag(self, tag, attrs):
        href = dict(attrs).get("href", "")
        if tag == "a" and href:
            self.links[Path(urlsplit(href).path).name] = urljoin(BASE_URL, href)


def credentials(from_brief):
    password = os.environ.get("VALIO_PORTAL_PASSWORD")
    api_key = os.environ.get("VALIO_API_KEY")
    if from_brief and (not password or not api_key):
        brief = (ROOT / "valio-aimo-challenge.md").read_text(encoding="utf-8")
        password_match = re.search(r"Resource portal password:.*?`([^`]+)`", brief)
        key_match = re.search(r"API key:\s*`([^`]+)`", brief)
        password = password or (password_match.group(1) if password_match else None)
        api_key = api_key or (key_match.group(1) if key_match else None)
    if not password or not api_key:
        raise ValueError(
            "Set VALIO_PORTAL_PASSWORD and VALIO_API_KEY, or use "
            "--credentials-from-brief with the supplied local challenge brief."
        )
    return password, api_key


def summarize_resource(filename, content):
    if filename.endswith(".json"):
        parsed = json.loads(content)
        if filename == "products.json":
            if not isinstance(parsed, list) or not parsed or not parsed[0].get("id"):
                raise ValueError("Expected a nonempty product array with product IDs.")
            return {"products": len(parsed), "sampleProduct": str(parsed[0]["id"])}
        if not isinstance(parsed, dict):
            raise ValueError(f"Expected a JSON object in {filename}.")
        return {"format": "json"}
    reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
    if not reader.fieldnames or len(reader.fieldnames) < 2:
        raise ValueError(f"Expected multiple CSV columns in {filename}.")
    rows = sum(1 for _ in reader)
    if not rows:
        raise ValueError(f"Expected data rows in {filename}.")
    return {"rows": rows, "columns": reader.fieldnames}


def setup(args):
    password, api_key = credentials(args.credentials_from_brief)
    opener = build_opener(HTTPCookieProcessor(CookieJar()))
    opener.addheaders = [("User-Agent", "ValioAimoChallengeSetup/1.0")]

    def request(path, payload=None, authenticated=False, form=False):
        url = urljoin(BASE_URL, path)
        if urlsplit(url).netloc != urlsplit(BASE_URL).netloc:
            raise ValueError("Refusing a resource outside the challenge portal.")
        headers = {}
        body = None
        if authenticated:
            headers["X-API-Key"] = api_key
        if payload is not None:
            body = (urlencode(payload) if form else json.dumps(payload)).encode()
            headers["Content-Type"] = (
                "application/x-www-form-urlencoded" if form else "application/json"
            )
        with opener.open(Request(url, data=body, headers=headers), timeout=60) as response:
            return response.read()

    request("/login", {"password": password, "next": "/"}, form=True)
    links = ResourceLinks()
    links.feed(request("/").decode("utf-8"))
    missing = set(RESOURCES) - links.links.keys()
    if missing:
        raise ValueError("Portal login failed or expected resource links are missing.")
    print("Portal sign-in: OK")

    spec = json.loads(request("/openapi.json"))
    if not all(path in spec.get("paths", {}) for path in ("/api/ping", "/api/price", "/api/availability")):
        raise ValueError("The published API contract has changed; review it before proceeding.")
    ping = json.loads(request("/api/ping", authenticated=True))
    print("API authentication: OK")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "openapi.json").write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")
    resources = {}
    for remote_name, local_name in RESOURCES.items():
        destination = DATA_DIR / local_name
        cached = destination.exists() and not args.refresh
        content = destination.read_bytes() if cached else request(links.links[remote_name])
        summary = summarize_resource(local_name, content)
        if not cached:
            destination.write_bytes(content)
        resources[local_name] = summary
        print(f"{'Cached' if cached else 'Downloaded'}: {local_name}")

    product = resources["products.json"]["sampleProduct"]
    payload = {
        "customer": args.customer,
        "requestedDate": args.requested_date.isoformat(),
        "products": [product],
    }
    results = {"ping": ping}
    for endpoint in ("price", "availability"):
        result = json.loads(request(f"/api/{endpoint}", payload, authenticated=True))
        if not isinstance(result, dict) or not isinstance(result.get("products"), list) or len(result["products"]) != 1:
            raise ValueError(f"Unexpected {endpoint} response; expected one product result.")
        results[endpoint] = result
        print(f"Read-only {endpoint} lookup: OK (product {product})")

    report = {
        "checkedAt": datetime.now(timezone.utc).isoformat(),
        "baseUrl": BASE_URL,
        "request": payload,
        "resources": resources,
        "results": results,
        "publishedPaths": list(spec["paths"]),
    }
    (DATA_DIR / "smoke-test.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Ready: {resources['products.json']['products']} products in {DATA_DIR}")
    print("Only read-only lookups were made. No order was placed.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--credentials-from-brief", action="store_true", help="Read missing credentials from the local supplied challenge brief.")
    parser.add_argument("--refresh", action="store_true", help="Download datasets again instead of using local copies.")
    parser.add_argument("--customer", default="123", help="Synthetic customer ID (default: 123).")
    parser.add_argument("--requested-date", type=date.fromisoformat, default=datetime.now(ZoneInfo("Europe/Helsinki")).date() + timedelta(days=2), help="Delivery date as YYYY-MM-DD (default: Helsinki today + 2 days).")
    args = parser.parse_args()
    try:
        setup(args)
    except HTTPError as error:
        print(f"Setup failed: HTTP {error.code} at {urlsplit(error.url).path}. Check credentials; for 429, retry later.", file=sys.stderr)
        return 1
    except (OSError, URLError, ValueError) as error:
        print(f"Setup failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())