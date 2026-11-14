# Valio Aimo Purchasing Workspace: Prototype Specification

Status: scoped prototype implemented, including gateway, purchasing UI, curated
planner, and optional xAI tool-calling integration. Real provider inference still
requires an XAI_API_KEY and was not exercised without one. See [README](../README.md)
for tested feature coverage, supported scenarios, and runtime limitations.
Date: 2026-11-14. Basis: [mentor conclusions](../README.md#mentor-interview-conclusions-and-working-assumptions)
and [company, product, and customer research](brand-research.md).

Gateway behavior is refined by the [owner-controlled gateway contract](gateway-contract.md)
and [OpenAPI schemas](gateway.openapi.json). Krish owns that boundary; frontend
and buyer-agent work must consume it without independently changing policy or
authorization. The owner authorized implementation of the gateway baseline;
future contract and authority changes still require owner review.

## Product Decision

Build a general-purpose foodservice purchasing workspace with one deeply
implemented event-catering workflow. The chef-facing buyer agent is the visible
product; the trusted ordering interface is its enforceable foundation.

The first screen is useful work, not a landing page. A chef can describe a need,
inspect a proposed basket, resolve an exception, and complete a mock order.
Do not create a wedding-specific brand, a generic chat-only wrapper, or a full
multi-supplier marketplace.

The working end-to-end demo is the largest individual judging category (30%),
but matching buyer intent and enforcing autonomy controls each count for 20%.
Visual fidelity supports credibility; it does not replace correct ordering.

## Research-to-Design Decisions

| Evidence | Decision |
| --- | --- |
| Minun Aimo already describes recipes, scaling, pack rounding, and A.I.mo | Present a proposed agentic purchasing extension; do not pitch these existing features alone as the innovation |
| Caffitella values quality and exact fulfillment | Explain substitutions against recipe function and preferences, not just price |
| Wilderness Hotels emphasizes delivery reliability | Show required delivery date, supply check time, and deadline failures prominently |
| Institutional customer story describes contracted assortments | Carry customer context through every lookup; mark any contract policy in our demo as synthetic |
| Public webshop guide exposes sales units and both tax views | Distinguish ingredient amount, purchase pack, unit price, line total, and VAT |
| Teal/lime identity, condensed type, square actions | Use the recognizable brand language inside a restrained ordering workspace |

These are design conclusions drawn from public sources, not customer-validated
requirements or an official Valio Aimo roadmap.

## Demo Contract

Use a fictional account named **Demo Catering Kitchen**. The baseline request
is pies for 100 wedding guests, with a specific delivery deadline. A curated,
reviewed recipe provides the initial culinary knowledge; the chosen recipe and
yield must be visible. A sweet/savory preference or kitchen default must be
provided, not silently guessed from the word "pies".

The fixture specifies dietary requirements, pantry stock and its freshness,
budget and tax basis, allowed substitutions, and an autonomous-spend limit.
These are illustrative settings, not policies supplied by Valio Aimo. Missing
critical inputs trigger one concise clarification step. Unknown allergens are
not treated as absent, and lactose-free must not be interpreted as milk-free.

Support a direct product request through the same downstream purchasing flow,
such as the brief's lactose-free milk example. That demonstrates reuse without
requiring a second open-ended recipe planner. Outside curated planning coverage,
ask for a recipe or explain that a draft needs review; do not simulate success.

## Screen and Interaction Specification

### 1. Purchasing Workspace

Use a compact Aimo-inspired header, account/site context, a clearly visible
prototype indicator, and navigation for Requests, Approvals, and Orders. The
current request is the main content, with an input labeled "What do you need?"
and explicit deadline, guest count, and budget fields when relevant.

Keep the initial request and its interpreted requirements visible. Show real
execution states such as planning, matching products, checking availability,
and awaiting a decision. Do not animate invented progress or expose private
model reasoning; summarize tool-backed decisions instead.

### 2. Plan and Proposed Basket

Use a main basket area and a narrower summary/decision area on desktop. Plan,
Basket, and Activity are views of the same request, not separate disconnected
chat sessions. On narrow screens, stack the summary above the basket and use
labeled product rows; critical totals and actions must remain reachable.

The plan shows recipe source/version, servings, yield, dietary constraints,
ingredient calculations, and pantry deductions. The basket shows product image
when permitted, name/code, sales pack, required amount, ordered amount, overage,
price basis, line total, delivery result, and any unresolved condition.

Totals expose VAT treatment and cost per serving. Allow edits to servings,
deadline, and supported preferences, then recompute. Show the data timestamp and
do not describe an availability lookup as reserved stock. Optional reliability
and sustainability details stay secondary to price, quantity, and feasibility.

### 3. Decision and Approval

Present only the decision requiring attention: what changed, why it matters,
the recommended valid option, its price/delivery effect, and any alternatives.
The user can choose an option, revise the request, or cancel. Do not make them
approve each ingredient individually when a policy permits the whole basket.

Separate "Approve purchase" from "Place mock order" unless a clearly labeled
combined action deliberately performs both. Show the authorized approver role.
The agent cannot approve its own exception. A changed basket invalidates the
previous approval, and an unsafe/unverified allergen match remains blocked.

### 4. Order and Activity

Display a persisted mock order ID, the exact approved basket, totals, requested
delivery date, actor, and timestamp. Use "Mock order placed", never a claim of
supplier acceptance or guaranteed delivery. Preserve the request and a readable
event history. Reloading must not lose state or create another order.

## Visual Specification

| Token or rule | Specification | Provenance |
| --- | --- | --- |
| Brand primary | `#005670` | Observed public-site/webshop teal |
| Action accent | `#C0E021`, with teal text | Observed public-site CTA |
| Body ink | `#23282D` | Observed homepage text |
| Main surfaces | White; proposed neutral `#F5F7F7` for muted areas | White observed; neutral is our choice |
| Secondary brand tint | `#EEE8F5`, used sparingly | Observed webshop header |
| Fonts | Approved National/National2Compressed headings and Matter body | Observed; redistribution rights unverified |
| Fallback fonts | Barlow Condensed headings and DM Sans body | Our proposal, with license files retained |
| Corners | Square primary actions; 0-4px fields and framed elements | Actions observed; other sizes proposed |
| Type sizes | 28-32px page title, 18-22px section headings, 14-16px data/body | Our operational adaptation, not copied hero sizes |
| Spacing | 4/8/12/16/24/32px scale | Our proposed layout system |
| Imagery | Actual dish/product images with stable aspect ratios | Subject-specific and permitted assets only |

Keep white/neutral surfaces dominant, teal structural, and lime selective.
Avoid making the workspace entirely teal, lavender, or dark blue. Do not use
large editorial hero photography, floating section cards, nested cards, or
decorative gradients in the working screen. Use full-width separators and
aligned data rather than decoration to organize information.

Use icons with accessible names and tooltips for edit, search, remove, and
history; a familiar library such as Lucide is suitable. Use labeled numeric
inputs/steppers for quantities, date inputs for deadlines, checkboxes for binary
preferences, and menus for option sets. Button text is for actual commands.
No visible feature-tour copy or fake keyboard-shortcut hints.

Define fixed tracks/minimums for product thumbnails, quantity controls, and
totals so changing labels does not move surrounding content. Wrap long product
names without covering neighboring data. Do not size fonts in viewport units
or use negative letter spacing. Test at 390px mobile and 1440px desktop widths.
Verify contrast, keyboard focus, non-color status labels, and reduced motion.

Use English for the initial judging flow, preserve original product names, and
localize Finnish dates/currency consistently. A Finnish-language shell is a
later option; do not ship a language switch until both locales work.

## Agent and Trusted Interface

Keep separate modules for request interpretation/recipe planning, deterministic
quantity and unit calculations, catalog matching, policy evaluation, and mock
order commitment. One application is sufficient; separate microservices and
multiple autonomous agents are not required.

The agent produces structured purchasing intent: account, items, amounts/units,
recipe/version where applicable, dietary restrictions, deadline, budget/currency
and tax basis, and preferences. Authority comes from server-side policy, not
from an assertion in the agent's request. Product descriptions and recipe text
are untrusted data, never instructions that can change policy or reveal keys.

Use JSON Schema to validate boundary data and document our interface with
OpenAPI. Keep it callable by a different buyer agent. MCP can be a later adapter,
not a requirement for the initial end-to-end demo.

Proposed states: `draft`, `needs_clarification`, `planning`, `checking`,
`blocked`, `awaiting_approval`, `ready_to_order`, `ordering`, `ordered_mock`,
`failed`, and `cancelled`. State changes are server-enforced. Only a valid,
fresh, policy-authorized basket can become an order.

These are application workflow states. The gateway contract separately defines
request, basket, evaluation, and terminal mock-order semantics; do not map every
agent planning state onto an order record.

Bind approval to the basket version, customer, totals/tax basis, delivery date,
policy version, approver, and expiry. Revalidate before commit; a changed price,
quantity, substitution, deadline, or policy requires reevaluation and renewed
approval when appropriate. Use an idempotency key and atomic persistence to
prevent duplicate mock orders. Persist events and request state across reloads.

## Data and Mock Boundaries

| Capability | Initial source and behavior |
| --- | --- |
| Product search | Local challenge catalog; retain product IDs and supplied units |
| Recipes and pantry | Explicit curated demo fixtures; not customer data or an inventory integration |
| Prices | On-demand `/api/price` after shortlisting; retain currency, tax, and applicable validity information |
| Availability | On-demand `/api/availability`; check sales blocks, cutoff, available quantity/unit, and dated schedule lines |
| Customer policy | Server-side synthetic fixtures, separate from the model |
| Approvals and orders | Our persisted local implementation; order commitment is a labeled mock |
| Audit | Our event log with inputs, selections, reasons, API timestamps, policy outcomes, and actor attribution |

Authenticate challenge calls only on the backend. Do not send the shared API key
to the frontend. Production sites are research references, not integration
targets. Never connect the prototype to a real webshop account.

Live queries include customer ID, requested date, and only shortlisted product
IDs. Do not bulk-refresh live prices or availability for the full catalog.
Use bounded retries/backoff for transient errors; stale or failed checks cannot
silently become a success. Missing unit conversions or allergen evidence block
the affected commitment. A deadline must reflect preparation time as well as
the event itself. Category carbon estimates are not product measurements, and
historical reliability is not a delivery guarantee.

For deterministic exception demonstrations, use a separately labeled fixture
mode that injects a stock shortage or policy failure. Never describe a fixture
response as a live organizer API result. Maintain a distinct live demo path.

## Build Order and Acceptance Gates

1. Implement a direct-product request through catalog lookup, live checks,
   policy evaluation, and persisted mock ordering. Verify the trusted path first.
2. Add the curated wedding recipe planner and deterministic scaling/pack logic.
3. Build the branded request, basket, decision, and order views around that path.
4. Add one stock exception and one delegated-spend exception, with explicit
   fixture controls for repeatable demonstration.
5. Test the alternate guest count, approval invalidation, duplicate submission,
   missing safety evidence, API errors, and responsive interface before polish.

| Acceptance check | Expected evidence |
| --- | --- |
| Baseline 100 guests | Supported recipe produces traceable quantities and a feasible, priced basket |
| Change to 150 guests | Real recalculation and pack rounding, not a fixed scripted result |
| Below delegated spend limit | Valid basket can commit without an unnecessary approval request |
| Above delegated spend limit | Commit is refused until an authorized human approves the exact basket |
| Missing allergen or unit evidence | Affected purchase is blocked or clarified, not guessed |
| Insufficient stock / missed cutoff | Valid alternative, revised date, or explicit blocked result |
| Basket changed after approval | Prior approval cannot authorize the new version |
| Retry or double-click order | Same idempotent result, no duplicate commitment |
| API failure or rate limit | Honest retry/blocked state; no fabricated availability |
| Direct milk request | Uses the same policy and ordering path without recipe planning |
| Desktop/mobile review | Real screenshots and interaction checks; no overflow or hidden decisions |

Demo sequence: enter the event request, inspect the plan and basket, show one
meaningful exception and human decision, place a mock order, and inspect its
audit trail. Measure completion and manual interventions during testing; do not
invent time savings, customer endorsements, or successful production orders.

## Confirm Before Implementation

- Which capability should we emphasize beyond the existing A.I.mo/recipe flow?
- Can organizers provide approved brand assets and an authenticated webshop
  walkthrough or screenshots? Public login is not the full ordering interface.
- Is any order API available beyond the published contract, or is a local mock
  the expected endpoint for the challenge?
- Which exact recipe, yield, dietary profile, and deadline define the demo?
- Which model/provider and deployment environment are available to the team?

These questions refine the build; the public research does not answer them.