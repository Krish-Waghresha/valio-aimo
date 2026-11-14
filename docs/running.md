# Run and verify

## Offline workspace

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).
Fixture mode uses synthetic local products, prices and availability; no external
API key, downloaded catalog or model provider is needed.

```sh
uv sync --frozen --extra dev
uv run aimo-gateway init --mode fixture
uv run aimo-gateway policy --mode fixture --autonomous-limit 50000
uv run aimo-gateway serve --workspace --mode fixture
```

Open http://127.0.0.1:8000. Initialization writes separate `chef`, `manager` and
`buyer-agent` credentials to ignored `data/gateway/fixture/credentials.json`.
Use the chef token in one browser profile and the manager token in another.
Never share the complete credential file with an agent.

Create a request, inspect its proposed basket and comparison, resolve any
exception, and approve when required. The gateway rechecks before recording a
local mock order. Activity and JSON export show the decision trail.

The EUR 500 autonomous limit above is a demo policy, not a fixed application rule.
Owner CLI limits are **EUR cents, including VAT on goods**. The default per-order
and manager-approval ceilings are EUR 1,000; the default shared daily limit is
EUR 2,000. Raising an autonomous limit does not raise those other ceilings.

Initialization refuses to overwrite existing credentials or audit history.
Demo credentials expire after eight hours; human sessions last at most one hour.
For another rehearsal, pass a new `--database` path to `init`, `policy` and
`serve`, rather than deleting an existing database.

For the standalone HTTP demonstration, use a separate fixture server with the
default EUR 10 autonomous policy, without the override above. Pass its new
`--database` path and `--origin` consistently to `init`, `serve` and `demo`:

```sh
uv run aimo-gateway demo --mode fixture
```

That harness expects an approval-required basket and simulates separate human
principals; it is not proof that a real person reviewed an order.

## Live challenge APIs

Live mode requires separately obtained challenge access. The downloaded catalog
and supplier datasets are **not redistributed** in this repository.
Set `VALIO_PORTAL_PASSWORD` and `VALIO_API_KEY` in the server environment, then:

```sh
uv run python scripts/portal_setup.py
uv run aimo-gateway init --mode live --origin http://127.0.0.1:8001
uv run aimo-gateway policy --mode live --autonomous-limit 50000 --order-limit 500000 --daily-limit 1000000 --manager-approval-limit 500000
uv run aimo-gateway serve --workspace --mode live --port 8001 --origin http://127.0.0.1:8001
```

The setup script caches resources in ignored `data/valio/`, validates API access
and performs read-only price/availability lookups. It does not load `.env`.
The gateway shortlists the catalog before querying prices and availability;
these are separate organizer endpoints, not one upstream call.

Live prices, stock, deadlines and demo outcomes can change. Sustainability
overlays are supplied labels and category-average estimates, not independently
verified product footprints. Both fixture and live orders remain local mocks:
the challenge APIs provide no supplier-order, payment or reservation endpoint.
The illustrated live policy is EUR 500 autonomous, EUR 5,000 per order and
manager approval, and EUR 10,000 daily; it is not a production recommendation.

## Agent and owner access

Commerce schemas are in [OpenAPI 3.1](gateway.openapi.json), with interactive
documentation at http://127.0.0.1:8000/docs. See the
[gateway contract](gateway-contract.md) and [workspace API](workspace-api.md).
Compatible external clients need owner-issued credentials and request grants.
The workspace broker manages its configured buyer agent and manager grants.

The owner CLI can grant or revoke access and change purchasing policy. Those
administrative capabilities are not exposed to the browser or purchasing model:

```sh
uv run aimo-gateway grant --mode fixture --principal buyer-agent --request REQUEST_UUID
uv run aimo-gateway grant --mode fixture --principal manager --request REQUEST_UUID
uv run aimo-gateway revoke --mode fixture --principal buyer-agent
```

The verified default is deterministic planning for supported product requests
and curated recipes. Setting `XAI_API_KEY` enables the optional bounded xAI
interpreter; `XAI_MODEL` selects its model. Live model inference has not been
runtime-verified. Provider failures are explicit, and the model cannot grant
authority or waive gateway checks. Avoid personal or confidential information
in free-text requests sent to an external provider.

## Checks

```sh
uv run pytest -q
uv run ruff check src tests scripts video
uv run python scripts/check_gateway_contract.py
npx --yes @redocly/cli@2.78.0 lint docs/gateway.openapi.json --config docs/redocly.yaml
```

The default test command skips browser cases. To run the offline desktop/mobile
journeys and approval regressions, install Chromium and start a separate fixture workspace:

```sh
uv run playwright install chromium
uv run aimo-gateway init --mode fixture --database data/gateway/workspace-fixture/gateway.sqlite --origin http://127.0.0.1:8002
uv run aimo-gateway policy --mode fixture --database data/gateway/workspace-fixture/gateway.sqlite --autonomous-limit 5000
uv run aimo-gateway serve --workspace --mode fixture --database data/gateway/workspace-fixture/gateway.sqlite --port 8002 --origin http://127.0.0.1:8002
```

In another terminal:

```sh
AIMO_E2E_URL=http://127.0.0.1:8002 \
AIMO_E2E_CREDENTIALS=data/gateway/workspace-fixture/credentials.json \
uv run pytest tests/test_browser.py -q
```

These cover approval/rejection, stock and delivery exceptions, autonomous
purchasing, pantry calculations and blocked exclusions. Three additional
journeys need `AIMO_E2E_LIVE_URL` and live challenge resources; they are not part
of offline CI. Screenshots and exports stay under ignored `test-results/`.

## Presentation

[View the six-slide finals pitch](presentation/slides.pdf) without running the app.
It fits **three minutes including a one-minute demo**, with ten seconds spare.
The [HTML deck](presentation/index.html) works offline: arrows or space advance,
`F` enters fullscreen, `?notes` shows the timed talk track, and `?all` shows every
slide. Print with background graphics enabled for a six-page, 16:9 PDF;
speaker notes stay out of the export.
Leave the final thank-you slide up for questions; it includes both presenters’
portraits, LinkedIn QR codes and clickable profile links.

The demo slide links to the published video at 0:46. For rehearsal, stop at about
1:39 and return to the deck; do not play the whole film inside the three-minute slot.
Pre-open the video before presenting. Its link needs internet, but the deck and
included stock-out still work offline as a fallback. The still is a cropped frame
from the existing film, not a fresh price or availability check.
The [video source](../video/) documents recording and rendering requirements.

## Boundaries

The server binds to loopback. Do not expose this prototype directly to the
internet: production use needs TLS, identity management, deployment controls
and operational hardening. SQLite here is a single-host implementation.

Approval is bound to one evaluated basket; edits, policy changes and stale quotes
invalidate it. Evaluations expire within two minutes or at the delivery cutoff,
whichever comes first. Missing allergen evidence does not establish safety;
lactose-free does not mean milk-free. Unknown lot sizes, variable-weight items,
deposits and unconfirmed terminal stock remain blocked.

There are no production supplier commitments, shipping/payment totals, stock
reservations, signed credentials or MCP interface. Those are future integration
work, not features of this submission.

No project license has been granted. Existing font, icon and image notices remain
with their assets. Historical research and draft production notes are preserved
on `archive/junction-2026-research`; removing them from the main tree does not
remove them from Git history or establish redistribution rights.
