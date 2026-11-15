# Valio Aimo Purchasing Workspace

[Watch the latest demo](https://youtu.be/CB_NcgdgK5k).

The working demo includes an Aimo-styled purchasing workspace, curated recipe
and direct-product planning, candidate comparison, pantry/portion/pack calculations,
exception recovery, authenticated human approvals, and persistent mock orders.
The owner-controlled gateway enforces authority and live-data checks underneath.

## Start the Complete Demo

The currently running workspaces are:

- Fixture workspace: http://127.0.0.1:8002/
- Live challenge-data workspace: http://127.0.0.1:8003/

For a fresh workspace, initialize once, then serve:

```sh
uv sync --extra dev
uv run aimo-gateway init --mode fixture --database data/gateway/workspace-fixture/gateway.sqlite --origin http://127.0.0.1:8002
uv run aimo-gateway policy --mode fixture --database data/gateway/workspace-fixture/gateway.sqlite --autonomous-limit 5000
uv run aimo-gateway serve --workspace --mode fixture --database data/gateway/workspace-fixture/gateway.sqlite --port 8002 --origin http://127.0.0.1:8002
```

Sign in using the appropriate owner-issued `chef` or `manager` token from the
ignored credential file beside that database. Do not use production passwords.
Use a separate browser profile/private window for the manager. The chef can
submit requests but cannot approve their own exception; manager approval and
explicit mock commitment are separate actions. Session refresh does not revive
revoked sessions. Failed jobs cancel their underlying uncommitted requests.

The application broker automatically assigns only the configured buyer-agent
and manager to each human-created request. It does not expose agent keys,
arbitrary grant mutation, or policy changes to the browser or model.

For the live workspace (after downloading the challenge resources):

```sh
uv run aimo-gateway init --mode live --database data/gateway/workspace-live/gateway.sqlite --origin http://127.0.0.1:8003
uv run aimo-gateway serve --workspace --mode live --database data/gateway/workspace-live/gateway.sqlite --port 8003 --origin http://127.0.0.1:8003 --credentials-from-brief
```

Existing initialization is never overwritten. Use a new database directory for
a clean rehearsal when credentials expire, preserving old audit history.

### Model Access

No runtime provider key was configured during development. Without `XAI_API_KEY`,
the UI explicitly says **Deterministic planner**. This mode performs actual
recipe/quantity calculations and gateway actions but is not live LLM inference.

Set `XAI_API_KEY` in the server environment and restart to enable the bounded xAI
tool-calling interpreter. `XAI_MODEL` optionally overrides the default `grok-4`.
Do not put keys in chat, frontend code, or Git. No `.env` loader is installed.
Provider failures are explicit, not silently replaced with deterministic results.
Only brief/servings and permitted recipe metadata are sent to xAI; structured
dietary/exclusion fields stay local, though users must avoid personal information
in the free-text brief. External-provider retention terms still apply.

Live Grok inference remains unverified until a valid provider key is configured.
Mock-transport tests verify tool arguments, intent binding, errors, and refusal
of model-supplied authority. Grok coding subagents are not runtime model access.

### Feature Coverage

| Requirement | Implemented demo behavior |
| --- | --- |
| Structured lookup and comparison | Catalog IDs, gateway quotes, physical packs, gross purchase cost, stock/date checks |
| Inquiry to fixed-price order | Human request, plan, evaluated basket, final recheck, persisted mock order |
| Permissions and human approval | Separate sessions/agent credentials; request-scoped delegation; manager decision; no self-approval |
| Recipe and portion planning | Three curated pie variants; 100/150 serving recalculation; pantry deductions; pack/lot rounding |
| Direct purchasing | Explicit catalog quantities and milk quantities through the same gateway |
| Delivery/reliability comparison | Dated availability, cutoff, historical ratios, preference ranking, late-date fixture recovery |
| Sustainability | Supplied labels, reliability/CO2 CSV overlays, category-average estimates and explicit coverage |
| Substitution and exceptions | Compared candidates; stock/late alternatives; recipe-changing or unsafe alternatives require clarification |
| Traceability | Plan explanations, selection evidence, gateway audit, actor attribution, JSON export |
| Usable interface | Requests, Plan/Basket/Comparison/Activity, Approvals, Orders, refresh, recheck, cancellation, revision and reload |

The live recipe uses a reviewed shortlist of actual staple IDs in
`LIVE_RECIPE_PRODUCTS`, not broad text matching. Pack mass/volume comes from
structured catalog metadata. For live pie recipes, whole egg is measured by mass
using the curated 50 g shell-free egg assumption, clearly labeled in the plan.
Technical sales unit ST is never assumed to mean one individual egg. Fixture
ingredients, metrics and recipes are synthetic; live supplier facts stay distinct.
Arbitrary recipes and unreviewed culinary substitutions are not claimed supported.

### Browser Verification

```sh
AIMO_E2E_URL=http://127.0.0.1:8002 AIMO_E2E_LIVE_URL=http://127.0.0.1:8003 uv run pytest tests/test_browser.py -q
```

Seven Playwright journeys passed: fixture wedding with stock substitution and
manager approval/order/export/reload; 150 servings and rejection; mobile direct
autonomous purchase; pantry plus late-date recovery; blocked egg exclusion; live
single-product purchase; reviewed live 100-person wedding approval and mock order.
Desktop/mobile screenshots and export artifacts are under ignored
`test-results/browser/`. Tests read local credentials without printing them.
Browser tests are skipped by the default unit-test command unless their URLs are
provided. Upstream data can legitimately block future live runs; this is not a
guarantee of stock or delivery. Earlier failed exploratory requests were cancelled,
including a draft whose overly broad ingredient matching was corrected.

Grok 4.7 subagents implemented the planner and UI slices. A separate Grok review
identified session/lifecycle/attribution issues that were repaired and covered by
tests. The original gateway contract and security boundary remain owner-controlled.

## Run the Gateway

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/). Dependencies are locked
in `uv.lock`. Initialize each mode once; `init` refuses to overwrite an existing
database or credential file.

```sh
uv sync --extra dev
uv run aimo-gateway init --mode fixture
uv run aimo-gateway serve --mode fixture
```

API documentation: http://127.0.0.1:8000/docs

In a second terminal, exercise the full HTTP flow:

```sh
uv run aimo-gateway demo --mode fixture
```

The owner-run demo harness signs in separate synthetic chef and manager clients,
grants the buyer agent access to the human-created request, proposes a basket,
checks that commit is refused before approval, records a simulated human-principal
approval, commits a local mock order, and verifies replay/audit behavior. It is
not an LLM agent or evidence that a real human participant reviewed the order.

For live challenge data, first run the portal setup below, then:

```sh
uv run aimo-gateway init --mode live
uv run aimo-gateway serve --mode live --port 8001 --origin http://127.0.0.1:8001 --credentials-from-brief
```

```sh
uv run aimo-gateway demo --mode live --origin http://127.0.0.1:8001
```

Alternatively set `VALIO_API_KEY` in the server environment and omit the brief
flag. No key is required for fixture mode. Live mode uses the downloaded catalog
and actual organizer pricing/availability APIs. Orders in both modes remain
local mocks; there is no production webshop, payment, or supplier commitment.
Live data can legitimately block a demo when stock, pricing, or dates change.

Both flows were verified on 2026-11-14: ten fixture milk cases and ten sales units
of catalog product 460000 each produced an approval-required EUR 22.20 goods
basket, one mock order, an identical replay, and seven audit events. These are
observations from that run, not promised prices or stock for future runs.

## Owner Controls

Runtime state and owner-only `credentials.json` files are under ignored
`data/gateway/fixture/` and `data/gateway/live/`. Files contain separate chef,
manager, and buyer-agent credentials; never pass the whole file to an agent or
commit it. The database stores credential hashes. Demo principal credentials
expire after eight hours; human sessions last at most one hour. Reinitialize a
fresh database in a new directory when an expired demo must be restarted; do not
delete an existing audit database or silently extend authority.

Human login is `POST /auth/login` with `{ "loginToken": "..." }` and the exact
configured `Origin`. It sets an HttpOnly, SameSite=Strict cookie and returns a
session-bound CSRF token. Every human mutation includes `X-CSRF-Token` and Origin.
The agent uses only its bearer token. Login/bootstrap is outside the commerce
OpenAPI; the commerce schemas are served unchanged at `/openapi.json`.

Grant request access explicitly through the local owner CLI:

```sh
uv run aimo-gateway grant --mode fixture --principal buyer-agent --request REQUEST_UUID
uv run aimo-gateway grant --mode fixture --principal manager --request REQUEST_UUID
uv run aimo-gateway revoke --mode fixture --principal buyer-agent
uv run aimo-gateway policy --mode fixture --autonomous-limit 1000 --order-limit 100000 --daily-limit 200000
```

Limits are EUR cents including VAT on goods only. Policy changes invalidate old
evaluations. The example defaults are EUR 10 autonomous, EUR 1,000 per order,
and EUR 2,000 shared daily. The owner CLI is a trusted administrative capability,
not an endpoint available to the buyer agent. It has direct database access.
The `--database` option supports separate runs; live and fixture state cannot mix.

The default server binds to loopback. Do not expose this prototype directly to
the internet. Shared use needs TLS termination, deployment/network controls,
production identity management, and operational hardening. The `--origin` setting
is an exact origin, not a CORS wildcard. SQLite is suitable for this single-host
prototype, not a claim of distributed transaction safety.

## Verification and Limits

```sh
uv run pytest -q
uv run ruff check src tests
uv run python scripts/check_gateway_contract.py
npx --yes @redocly/cli@2.78.0 lint docs/gateway.openapi.json --config docs/redocly.yaml
```

The default suite currently has 101 passing tests, covering authenticated HTTP
flows, tenant/grant isolation, CSRF, unknown-field rejection, approval invalidation,
restarts, duplicate submissions, competing budgets and baskets, in-flight edits,
cancellation/revocation, decimal arithmetic, planner/workspace behavior, and upstream failures.
Seven browser tests are skipped by default and passed when run against the two
workspace servers with their E2E URL variables. The separate
wire checker covers 29 schema cases and 13 operation contracts. The test client
emits a third-party Starlette/httpx deprecation warning; OpenAPI lint retains the
intentional missing-license warning. Neither means production security is certified.

Known v1 restrictions: exact delivery dates, integer sales-unit quantities,
verified lot multiples, no variable-weight/deposit-bearing items, and no orders
against unconfirmed Terminal stock. Missing lot data stays blocked; the catalog
does not document a default step. Missing safety evidence is never treated as safe.
Shipping/payment charges and production stock reservations are not available.

Allergen normalization uses supplied Synkka groups and verified
[GS1 allergen codes](https://ref.gs1.org/voc/AllergenTypeCode) and
[containment codes](https://ref.gs1.org/voc/LevelOfContainmentCode).
Explicit free-from declarations can support an exclusion; contains/may-contain,
contradictions, unmapped relevant evidence, and unknown values fail closed.
This is synthetic challenge data, not a guarantee of real-world allergen safety.
Lactose-free does not imply milk-free. Catalog assets/text cannot grant authority.

Resource portal: https://junction26.valioaimo.fi/

The portal uses an event-password browser session. The APIs separately require
an `X-API-Key` header. Credentials are in the supplied local challenge brief;
do not put them in frontend code, screenshots, logs, or commits.

## Research and Prototype Specification

- [Brand, existing products, and customer research](docs/brand-research.md)
- [Public-page screenshot reference gallery](docs/brand-research.md#screenshot-reference-gallery)
- [Prototype scope, screens, controls, and acceptance gates](docs/prototype-spec.md)
- [Owner-controlled gateway contract](docs/gateway-contract.md)
- [Gateway OpenAPI 3.1 schemas](docs/gateway.openapi.json)
- [Independent review record and validation](docs/gateway-review.md)

The research distinguishes public source claims from our design choices. In
particular, Minun Aimo already describes recipes, pack rounding, and an A.I.mo
assistant; the prototype should demonstrate trusted agentic purchasing, not
present those existing capabilities alone as a new invention. The specification
is a build target, not a list of already implemented features.

## Local Setup

Requires Python 3.9+ with Helsinki timezone data. No third-party packages are needed.
From the workspace root:

```sh
python3 scripts/portal_setup.py --credentials-from-brief
```

Alternatively, supply `VALIO_PORTAL_PASSWORD` and `VALIO_API_KEY` through your
local environment and omit `--credentials-from-brief`. The script does not read
`.env` files. Environment values take precedence over values in the brief.

The script signs in, downloads the resources, verifies API authentication, and
requests price and availability for exactly one catalog product. These POST
requests are lookups, not purchases. No order is placed. Session cookies stay
in memory and credentials are not copied into generated files.

Files are cached in `data/valio/`:

- `products.json`: static product catalog (17,546 products observed).
- `product-schema.json`: published product JSON Schema.
- `delivery-reliability.csv`: historical delivered-to-ordered ratios.
- `carbon-footprint.csv`: category-average estimates, not measured product footprints.
- `openapi.json`: current API contract.
- `smoke-test.json`: timestamped read-only lookup results, not a reservation or quote lock.

Use `--refresh` to download datasets again. Use `--requested-date YYYY-MM-DD`
and `--customer ID` to change the smoke-test inputs. The default customer is
synthetic `123`; the default date is two days after today's Helsinki date.
Downloading validates basic JSON/CSV structure, not full JSON Schema conformance.

The credential-bearing original brief, local environment files, browser auth
state, and downloaded data are excluded by `.gitignore`. The original brief is
not included in a clone; obtain challenge access separately or supply credentials
through the environment. Never force-add the original brief or secrets.

## Verified Portal Scope

- `GET /api/ping`
- `POST /api/price`
- `POST /api/availability`
- `GET /api/products/download`
- `GET /api/delivery-reliability/download`
- `GET /api/carbon-footprint/download`

Price and availability requests use `customer`, `requestedDate`, and a list of
1-1,000 product IDs in `products`. Shortlist using the static catalog first.
The organizers explicitly prohibit designing around frequent full-catalog
price/availability fetches, and undisclosed rate limits apply.

The published OpenAPI contract has no order-submission, approval, recipe, or
inventory-reservation endpoint. The portal does not expose a customer webshop
login. Ask the organizers whether additional access exists; otherwise label
order submission as a local mock in the demo.

All data is synthetic and for this challenge only. Product information can be
incomplete; missing allergen information is not proof of allergen safety.

## Mentor Interview: Conclusions and Working Assumptions

This section records the team's account of a conversation with a challenge
mentor and the implementation direction chosen afterward. It is not a verbatim
transcript or an official replacement for the written challenge requirements.

### Initial Interpretation

We initially understood our responsibility as building a trusted gateway for
Valio Aimo, assuming that an external buyer already had a capable purchasing
agent. Understanding the buyer's request and planning ingredients would therefore
belong to that external agent, not to our implementation.

### Reported Mentor Feedback

The mentor described a chef facing an urgent wedding order: make pies for 100
people without having time to work out the exact ingredients. They wanted to see
a working experience in which the AI determines the ingredients, finds suitable
products, keeps a human in the loop only where needed, and lets the chef place
the order.

Our conclusion is that a gateway-only demo would not demonstrate enough of the
desired experience. We should implement the buyer-side agent as well as the
trusted purchasing interface. This emphasizes the brief's existing
"need -> recipe -> order" scenario rather than removing its trust requirements.

### Chosen Product Direction

Present a general-purpose purchasing workspace for professional kitchens, not a
wedding-specific or pie-specific app. Users should be able to express either a
direct product need or a higher-level catering need. Requests, proposed baskets,
approvals, and orders are the general product concepts.

Underneath that broad experience, the first implementation is deliberately
focused on the wedding-pie demo. Use a curated recipe basis and thoroughly
implement ingredient planning, portion scaling, pack-size conversion, catalog
matching, price and availability checks, approvals, and mock order commitment.
These are planned capabilities, not a claim that the current setup implements
them or that arbitrary culinary requests are already supported.

Specialize the recipe knowledge, not the entire execution flow. Guest count,
budget, delivery date, and availability changes must affect the result through
real calculations and checks, not a hardcoded response to one rehearsed prompt.
Outside supported planning coverage, request a recipe or clarification, or
explicitly return a draft that needs review rather than inventing certainty.

### Architecture and Human Control

Both direct product requests and recipe-derived needs should converge on shared
structured purchasing requirements: items, quantities, dietary constraints,
delivery deadline, budget, and delegated authority.

The buyer agent interprets the request, plans, proposes alternatives, and explains
trade-offs. The trusted interface retrieves commerce data, enforces permissions,
validates required approvals, and records order actions. It must remain usable
by another external agent; these responsibilities can be separate modules without
requiring separate services.

Minimal human intervention means avoiding redundant questions, not skipping
safety checks. Ask for missing essential requirements and obtain approval for
decisions outside delegated authority. An approval does not make an unsafe or
unverified allergen substitution safe, and the agent cannot waive gateway rules.

Order submission remains a clearly labeled local mock unless the organizers
provide an additional endpoint. The published APIs currently cover product
resources, prices, and availability, not order commitment.

## Chef Scenario

The mentor's urgent wedding request is a concrete version of the brief's
"need -> recipe -> order" scenario. A useful demo can combine:

1. Chef request: pies for 100 guests, deadline, budget, and dietary constraints.
2. Agent planning: recipe, portion scaling, pantry deductions, and purchasing quantities.
3. Product matching: catalog selection, pack sizes, live prices, and availability.
4. Enforced controls: human approval for unresolved safety requirements, policy
   exceptions, or spend outside delegated authority.
5. Order review/commitment and an auditable record, using a clearly identified
   local order mock unless an organizer-provided order API becomes available.

The chef-facing experience demonstrates the value; a documented trusted ordering
interface supplies the controls underneath. Recipe planning does not replace
the challenge's requirements for open interfaces and enforceable permissions.