import json
import os
import re
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import expect, sync_playwright


pytestmark = pytest.mark.skipif(not os.environ.get("AIMO_E2E_URL"), reason="Set AIMO_E2E_URL for browser tests")


class BrowserDemo:
    def __init__(self, browser):
        self.url = os.environ["AIMO_E2E_URL"]
        self.credentials_path = Path(os.environ.get("AIMO_E2E_CREDENTIALS", "data/gateway/workspace-fixture/credentials.json"))
        self.contexts = []
        self.browser = browser
        self.output = Path("test-results/browser")
        self.output.mkdir(parents=True, exist_ok=True)

    def page(self, actor, width=1440, height=1000):
        context = self.browser.new_context(viewport={"width": width, "height": height}, accept_downloads=True)
        self.contexts.append(context)
        page = context.new_page()
        page.goto(self.url)
        expect(page.get_by_role("heading", name="Sign in", exact=True)).to_be_visible()
        token = json.loads(self.credentials_path.read_text())["credentials"][actor]
        page.get_by_label("Login token", exact=True).fill(token)
        page.get_by_role("button", name="Sign in", exact=True).click()
        expect(page.locator("main h1")).to_be_visible(timeout=15000)
        return page

    def submit(self, page, servings=100, scenario="normal", auto=False, direct=False, pantry=False, exclude_eggs=False):
        page.goto(self.url + "/#requests")
        page.get_by_role("button", name="Use the order form instead", exact=True).click()
        expect(page.get_by_label("What do you need?", exact=True)).to_be_visible()
        if direct:
            page.get_by_label("What do you need?", exact=True).fill("12 litres lactose-free milk")
            page.get_by_label("Style", exact=True).select_option("not-a-pie")
            page.get_by_label("Servings", exact=True).fill("1")
        else:
            page.get_by_role("button", name="Fill savory wedding-pie example", exact=True).click()
            page.get_by_label("Servings", exact=True).fill(str(servings))
        page.get_by_label("Goods budget, VAT included (EUR)", exact=True).fill("500")
        if page.get_by_label("Fixture scenario", exact=True).count():
            page.get_by_label("Fixture scenario", exact=True).select_option(scenario)
        open_more_options(page)
        if pantry:
            page.get_by_role("button", name="Add pantry row", exact=True).click()
            page.get_by_label("Ingredient key", exact=True).fill("flour")
            page.get_by_label("Amount", exact=True).fill("1")
        if exclude_eggs:
            page.locator(".constraint-details summary").click()
            page.get_by_label("Eggs", exact=True).check()
        page.locator("#dietaryConfirmed").check()
        page.locator("#autoCommit").set_checked(auto)
        with page.expect_response(lambda response: response.url.endswith("/workspace/jobs") and response.request.method == "POST") as created:
            page.get_by_role("button", name="Submit request", exact=True).click()
        response = created.value
        assert response.status == 201, "Workspace creation failed"
        job_id = response.json()["id"]
        expect(page).to_have_url(re.compile(re.escape(f"#job/{job_id}/")))
        expect(page.locator(".job-layout")).to_be_visible()
        return job_id

    def layout(self, page, name):
        page.evaluate("document.fonts.ready")
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1"), "Page has horizontal overflow"
        page.screenshot(path=str(self.output / name), full_page=True)
        images = page.locator("img").evaluate_all("images => images.filter(image => image.currentSrc).map(image => ({loaded:image.complete && image.naturalWidth > 0,src:image.currentSrc}))")
        assert all(image["loaded"] for image in images), "A referenced image did not render"


def open_more_options(page):
    details = page.locator("details.more-options")
    if details.get_attribute("open") is None:
        details.locator("> summary").click()


@pytest.fixture
def demo():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        instance = BrowserDemo(browser)
        yield instance
        for context in instance.contexts:
            context.close()
        browser.close()


def test_wedding_substitution_approval_order_export_and_reload(demo):
    chef = demo.page("chef")
    errors = []
    chef.on("pageerror", lambda error: errors.append(str(error)))
    job_id = demo.submit(chef, scenario="shortage")
    expect(chef.get_by_text("Waiting for approval", exact=True).first).to_be_visible(timeout=30000)
    expect(chef.get_by_role("button", name="Approve & place order", exact=True)).to_have_count(0)
    chef.locator("summary", has_text="Compare alternatives").click()
    expect(chef.get_by_text("Demo wheat flour bag 2 kg", exact=True).first).to_be_visible()
    demo.layout(chef, "01-comparison-desktop.png")
    manager = demo.page("manager")
    manager.goto(demo.url + f"/#job/{job_id}/basket")
    manager.get_by_role("button", name="Approve & place order", exact=True).click()
    manager.get_by_role("button", name="Yes, continue", exact=True).click()
    expect(manager.locator(".decision").get_by_text("Order number")).to_be_visible(timeout=30000)
    demo.layout(manager, "02-order-desktop.png")
    with manager.expect_download() as downloaded:
        manager.get_by_role("button", name="Download order record", exact=True).click()
    downloaded.value.save_as(str(demo.output / "order-record.json"))
    record = json.loads((demo.output / "order-record.json").read_text())
    assert record["job"]["order"]["status"] == "ordered_mock"
    assert len([event for event in record["events"] if event["type"] == "order.created"]) == 1
    assert "demo-flour-alt" in [line["productId"] for line in record["job"]["plan"]["lines"]]
    manager.reload()
    expect(manager.locator(".decision").get_by_text("Order number")).to_be_visible()
    assert not errors


def test_servings_recalculate_and_manager_can_reject(demo):
    chef = demo.page("chef")
    job_id = demo.submit(chef, servings=150)
    expect(chef.get_by_text("Waiting for approval", exact=True).first).to_be_visible(timeout=30000)
    result = chef.request.get(demo.url + f"/workspace/jobs/{job_id}").json()
    flour = next(ingredient for ingredient in result["plan"]["ingredients"] if ingredient["key"] == "flour")
    assert flour["required"] == "7.5" and flour["quantity"] == 4
    manager = demo.page("manager")
    manager.goto(demo.url + f"/#job/{job_id}/plan")
    manager.get_by_role("button", name="Reject", exact=True).click()
    manager.get_by_role("button", name="Yes, continue", exact=True).click()
    expect(manager.get_by_text("Rejected", exact=True).first).to_be_visible()
    expect(manager.get_by_role("button", name="Place order", exact=True)).to_have_count(0)


def test_mobile_direct_purchase_is_autonomous(demo):
    page = demo.page("chef", width=390, height=844)
    demo.layout(page, "03-workspace-mobile.png")
    job_id = demo.submit(page, direct=True, auto=True)
    expect(page.locator(".decision").get_by_text("Order number")).to_be_visible(timeout=30000)
    result = page.request.get(demo.url + f"/workspace/jobs/{job_id}").json()
    assert result["evaluation"]["outcome"] == "allowed"
    assert result["order"]["totals"]["grossMinor"] < 5000
    demo.layout(page, "04-order-mobile.png")


@pytest.mark.parametrize("approval_case", ["approved", "legacy", "autonomous", "unavailable"])
def test_order_summary_uses_recorded_approval_actor(demo, approval_case):
    evaluation_id = "evaluation-current"
    job = {
        "id": "summary-job", "state": "ordered_mock", "brief": "20 kg butter", "mode": "fixture",
        "deliveryDate": "2026-11-20",
        "evaluation": {
            "id": evaluation_id,
            "outcome": "allowed" if approval_case == "autonomous" else "approval_required",
            "reasons": [{"code": "SUBSTITUTION_REQUIRES_APPROVAL" if approval_case == "approved" else "APPROVAL_THRESHOLD_EXCEEDED"}],
        },
        "order": {
            "id": "order-current", "evaluationId": evaluation_id,
            "committedBy": "buyer-agent", "committedAt": "2026-11-14T12:00:00Z", "lines": [],
        },
    }
    if approval_case == "autonomous":
        job["evaluation"]["reasons"] = []
    events = [{"type": "evaluation.decided", "evaluationId": "previous-evaluation", "actorId": "manager", "outcome": "approve"}]
    if approval_case in {"approved", "legacy"}:
        decision = {"type": "evaluation.decided", "evaluationId": evaluation_id, "actorId": "reviewer-42"}
        if approval_case == "approved":
            decision["outcome"] = "approve"
        events.append(decision)
    events.append({"type": "evaluation.decided", "evaluationId": "rejected-evaluation", "actorId": "manager", "outcome": "reject"})
    responses = {
        "/workspace/session": {"principalId": "chef", "scopes": ["audit:read"], "mode": "fixture", "today": "2026-11-14"},
        "/workspace/jobs": [job],
        "/workspace/jobs/summary-job": job,
        "/workspace/jobs/summary-job/events": events,
    }
    app_path = Path(__file__).resolve().parents[1] / "src/aimo_gateway/static/app.js"

    def respond(route):
        path = urlsplit(route.request.url).path
        if path == "/":
            route.fulfill(content_type="text/html", body='<div id="app"></div><div id="live"></div><script src="/static/app.js"></script>')
        elif path == "/static/app.js":
            route.fulfill(path=str(app_path))
        elif path.endswith("/events") and approval_case == "unavailable":
            route.fulfill(status=503, json={"detail": "Approval events unavailable"})
        elif path in responses:
            route.fulfill(json=responses[path])
        else:
            route.fulfill(status=404, body="Not found")

    context = demo.browser.new_context()
    demo.contexts.append(context)
    page = context.new_page()
    page.route("**/*", respond)
    page.goto(demo.url + "/#job/summary-job/basket")
    summary = page.locator(".decision")
    expect(summary.get_by_text("Order number", exact=True)).to_be_visible()
    expect(summary.locator('dt:text-is("Placed by") + dd')).to_have_text("Buyer agent")
    if approval_case in {"approved", "legacy"}:
        expect(summary.locator('dt:text-is("Approved by") + dd')).to_have_text("reviewer-42")
    else:
        expect(summary.locator('dt:text-is("Approved by")')).to_have_count(0)
        expect(summary.locator('dt:text-is("Approval") + dd')).to_have_text("Not needed (within authority)" if approval_case == "autonomous" else "Not available")
    if approval_case == "unavailable":
        expect(page.get_by_role("alert")).to_contain_text("Approval events unavailable")


def test_pantry_and_late_delivery_recovery(demo):
    page = demo.page("chef")
    job_id = demo.submit(page, scenario="late", pantry=True)
    expect(page.get_by_text("Waiting for approval", exact=True).first).to_be_visible(timeout=30000)
    result = page.request.get(demo.url + f"/workspace/jobs/{job_id}").json()
    flour = next(item for item in result["plan"]["ingredients"] if item["key"] == "flour")
    assert flour["required"] == "5" and flour["needed"] == "4"
    assert flour["productId"] == "demo-flour-alt"
    page.locator("summary", has_text="Recipe and quantities").click()
    demo.layout(page, "05-plan-desktop.png")
    page.get_by_role("button", name="Cancel request", exact=True).click()
    page.get_by_role("button", name="Yes, continue", exact=True).click()
    expect(page.get_by_text("Cancelled", exact=True).first).to_be_visible()


def test_missing_safe_egg_substitution_blocks_purchase(demo):
    page = demo.page("chef")
    job_id = demo.submit(page, exclude_eggs=True)
    expect(page.get_by_text("Needs more detail", exact=True).first).to_be_visible(timeout=30000)
    result = page.request.get(demo.url + f"/workspace/jobs/{job_id}").json()
    assert not result["plan"]["lines"] and not result["order"]
    expect(page.get_by_role("button", name="Place order", exact=True)).to_have_count(0)


@pytest.mark.skipif(not os.environ.get("AIMO_E2E_LIVE_URL"), reason="Set AIMO_E2E_LIVE_URL for real challenge data")
def test_live_catalog_purchase_through_browser(demo):
    demo.url = os.environ["AIMO_E2E_LIVE_URL"]
    demo.credentials_path = Path(os.environ.get("AIMO_E2E_LIVE_CREDENTIALS", "data/gateway/workspace-live/credentials.json"))
    page = demo.page("chef")
    page.get_by_role("button", name="Use the order form instead", exact=True).click()
    page.get_by_label("What do you need?", exact=True).fill("1 RAS of 460000")
    page.get_by_label("Style", exact=True).select_option("not-a-pie")
    page.get_by_label("Servings", exact=True).fill("1")
    page.get_by_label("Goods budget, VAT included (EUR)", exact=True).fill("50")
    expect(page.get_by_label("Fixture scenario", exact=True)).to_have_count(0)
    page.locator("#dietaryConfirmed").check()
    open_more_options(page)
    page.locator("#autoCommit").check()
    with page.expect_response(lambda response: response.url.endswith("/workspace/jobs") and response.request.method == "POST") as created:
        page.get_by_role("button", name="Submit request", exact=True).click()
    assert created.value.status == 201
    job_id = created.value.json()["id"]
    expect(page).to_have_url(re.compile(re.escape(f"#job/{job_id}/")))
    expect(page.locator(".job-layout")).to_be_visible()
    expect(page.locator(".decision").get_by_text("Order number")).to_be_visible(timeout=60000)
    result = page.request.get(demo.url + f"/workspace/jobs/{job_id}").json()
    assert result["mode"] == "live" and result["order"]["mode"] == "live"
    assert result["order"]["lines"][0]["productId"] == "460000"
    demo.layout(page, "06-live-order-desktop.png")


@pytest.mark.skipif(not os.environ.get("AIMO_E2E_LIVE_URL"), reason="Set AIMO_E2E_LIVE_URL for real challenge data")
def test_reviewed_live_wedding_reaches_approved_mock_order(demo):
    from aimo_gateway.planner import LIVE_RECIPE_PRODUCTS
    demo.url = os.environ["AIMO_E2E_LIVE_URL"]
    demo.credentials_path = Path(os.environ.get("AIMO_E2E_LIVE_CREDENTIALS", "data/gateway/workspace-live/credentials.json"))
    chef = demo.page("chef")
    job_id = demo.submit(chef)
    expect(chef.get_by_text("Waiting for approval", exact=True).first).to_be_visible(timeout=60000)
    result = chef.request.get(demo.url + f"/workspace/jobs/{job_id}").json()
    assert len(result["plan"]["lines"]) == 8
    for ingredient in result["plan"]["ingredients"]:
        assert ingredient["productId"] in LIVE_RECIPE_PRODUCTS[ingredient["key"]]
    egg = next(item for item in result["plan"]["ingredients"] if item["key"] == "egg")
    assert egg["required"] == "2" and egg["unit"] == "kg"
    manager = demo.page("manager")
    manager.goto(demo.url + f"/#job/{job_id}/basket")
    manager.get_by_role("button", name="Approve & place order", exact=True).click()
    manager.get_by_role("button", name="Yes, continue", exact=True).click()
    expect(manager.locator(".decision").get_by_text("Order number")).to_be_visible(timeout=60000)
    job = manager.request.get(demo.url + f"/workspace/jobs/{job_id}").json()
    assert job["order"]["committedBy"] == "manager" and job["order"]["mode"] == "live"
    demo.layout(manager, "07-live-wedding-order.png")

@pytest.mark.skipif(not os.environ.get("AIMO_E2E_LIVE_URL"), reason="Set AIMO_E2E_LIVE_URL for real challenge data")
def test_spoken_style_request_partial_stock_decision_and_approval(demo):
    """The flyer's request typed in plain words; the agent splits across producers after one tap."""
    demo.url = os.environ["AIMO_E2E_LIVE_URL"]
    demo.credentials_path = Path(os.environ.get("AIMO_E2E_LIVE_CREDENTIALS", "data/gateway/workspace-live/credentials.json"))
    chef = demo.page("chef")
    chef.fill("#ask", "I need 1,000 litres of lactose-free milk by Monday")
    chef.get_by_role("button", name="Continue", exact=True).click()
    expect(chef.get_by_text("Here's what I understood")).to_be_visible(timeout=10000)
    chef.locator("#dietaryConfirmed").check()
    chef.get_by_role("button", name="Find products", exact=True).click()
    expect(chef.locator(".xcard")).to_be_visible(timeout=60000)
    expect(chef.locator(".xcard h2")).to_contain_text("Only 384 L")
    chef.locator(".xoption", has_text="Keep 384 L").click()
    expect(chef.get_by_text("Waiting for approval").first).to_be_visible(timeout=60000)
    job_id = re.search(r"#job/([^/]+)", chef.url).group(1)
    job = chef.request.get(demo.url + f"/workspace/jobs/{job_id}").json()
    assert sorted((line["productId"], line["quantity"]) for line in job["evaluation"]["lines"]) == [("464306", 616), ("469363", 384)]
    demo.layout(chef, "08-live-partial-stock.png")
