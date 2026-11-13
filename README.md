# Valio Aimo Challenge Access

Resource portal: https://junction26.valioaimo.fi/

The portal uses an event-password browser session. The APIs separately require
an `X-API-Key` header. Credentials are in the supplied local challenge brief;
do not put them in frontend code, screenshots, logs, or commits.

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