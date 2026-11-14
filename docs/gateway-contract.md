# Trusted Purchasing Gateway Contract

Version: 0.1.0 prototype baseline. Date: 2026-11-14.
Owner: Krish. Implementation was authorized and is available in
[src/aimo_gateway](../src/aimo_gateway/). See the [run instructions](../README.md).
This is a synthetic local-order prototype, not a production security guarantee.

## 1. Ownership and Scope

The gateway is the authority boundary, not a model or a recipe planner. It
exposes catalog facts, evaluates a proposed basket, enforces buying authority,
records human decisions, and commits a persisted mock order. The buyer agent
proposes; the gateway authorizes. Another agent must be able to use the same API.

Krish approves changes to this contract, policy semantics, identity handling,
and order transitions. Frontend and buyer-agent implementers consume the
contract; they must not invent alternate approval or commitment paths.

This contract refines the gateway portions of the prototype specification.
Planning/clarification states belong to the buyer workflow, not gateway orders.
It does not prove that a recipe is nutritionally appropriate, sufficient for
100 people, or safe to prepare. Curated recipe validation and kitchen practice
remain separate. Gateway safety claims cover declared purchasing constraints
and evidence, not guaranteed culinary or clinical outcomes.

The wire contract is [OpenAPI 3.1](gateway.openapi.json). Requests
reject unknown fields. There is no client-supplied price, customer identity,
policy override, approval flag, fixture-mode switch, or executable tool name.

## 2. Actors and Trust Boundaries

| Principal | Allowed responsibility | Never accepted from it |
| --- | --- | --- |
| Human buyer | Create an immutable purchasing request, propose baskets, commit within granted authority, cancel an uncommitted request | Arbitrary tenant identity or policy changes |
| Human approver | Approve/reject an exact evaluated basket within their server-side approval ceiling | Waiving hard safety, request-budget, or customer-budget rules |
| Buyer agent | Search, propose/edit baskets, evaluate, read decisions, commit if authorized | Creating human consent or approving itself |
| Gateway | Resolve grants, enforce policy, call upstream, persist transitions | Instructions embedded in product descriptions or model output |
| Challenge APIs | Supply synthetic prices and availability | Buyer authorization, reservations, or supplier order acceptance |

Agent authentication uses opaque bearer credentials mapped server-side to
principal, customer, scopes, expiry, revocation state, and allowed request IDs.
Human authentication uses a separate server-side session, not the agent bearer
credential. Human-only endpoints reject bearer-only callers even if a token
contains an `approve` claim. No actor/customer field in JSON changes identity.
Reject requests presenting both credential types rather than silently choosing
one. Approvers require explicit request/customer access as well as action scope.

The demo bootstraps predefined humans, agents, customers, and grants through
gateway-owned configuration. Login/token issuance is out of this commerce API;
do not infer production SSO or delegate issuance to the frontend. A deployable
demo must still authenticate users and must not expose an unauthenticated role
selector. Agent grants are explicitly assigned to human-created request IDs.

Human cookie: `gateway_session`, HttpOnly, SameSite=Strict, Secure over HTTPS.
Every cookie-authenticated mutation also verifies an exact allowed Origin and a
session-bound `X-CSRF-Token`. CORS is same-origin by default; never wildcard with
credentials. Loopback-only local HTTP may omit Secure. Shared/public demos use
HTTPS. Token/session revocation and expiry are checked on each call and again
inside the final commit authorization check.

Tenant and request authorization applies to every object read/write, events,
idempotency records, and catalog entitlement. Foreign or inaccessible object IDs
return 404. Missing/invalid credentials return 401; missing action scope on an
otherwise accessible object returns 403. Customer-specific adapter caches must
include customer, requested date, product IDs, and live/fixture environment.

## 3. Human Request and Policy

Only a human with `requests:create` creates the purchasing request. It records
the brief, delivery site/date, gross goods budget in EUR cents, confirmed
dietary constraints, and optionally servings. The site must belong to the
authenticated customer. Dietary confirmation is explicit even when the answer
is that no exclusions are required. The server captures the human actor.

The request is immutable. To change its budget, delivery date/site, or safety
constraints, cancel it and create another through the human endpoint. The agent
may not weaken constraints by rephrasing the brief or submitting another basket.
One request can yield at most one mock order, across all baskets and agents.

Server-side policy has a version, autonomous gross-goods ceiling, hard per-order
ceiling, shared daily gross-goods ceiling, eligible product/site rules, and human
approver ceilings. All monetary limits use EUR cents, VAT included, on goods
only. Delivery fees/payment costs are unavailable and not claimed to be covered.
Production use requires those charges to be incorporated before authorization.

Hard failure takes precedence over approval. Hard failures include request
budget, hard order/daily limits, account eligibility, unsafe/unknown required
dietary evidence, missing price/unit mapping, and infeasible delivery. Human
approval is needed only for a valid basket exceeding the autonomous ceiling.
An approver cannot raise limits through a decision endpoint. Change policy via
the owner-controlled configuration and re-evaluate affected baskets.

Daily spending is shared by the customer across humans, agents, and requests,
using the Europe/Helsinki calendar day of commitment. The ledger, order, request
consumption, and success event commit atomically. Concurrent transactions must
not both spend the same remaining allowance. Approval does not reserve budget.

## 4. Operations

Base path `/v1`. JSON bodies; RFC 3339 UTC response timestamps; ISO calendar
dates interpreted in Europe/Helsinki for delivery. Stable UUID resource IDs.

| Method and path | Principal/scope | Successful result |
| --- | --- | --- |
| GET `/products?query=...&limit=20` | Human or agent, `catalog:read` | Bounded structured catalog search, no full-catalog live lookups |
| POST `/requests` | Human, `requests:create` | 201 immutable human-authorized request |
| GET `/requests/{requestId}` | Human or assigned agent, `requests:read` | Request context and active/cancelled/ordered state |
| POST `/requests/{requestId}/cancel` | Human, `requests:cancel` | Cancelled request, or conflict if committed |
| POST `/requests/{requestId}/baskets` | Human or assigned agent, `baskets:write` | 201 draft basket, version 1 |
| GET `/baskets/{basketId}` | Human or assigned agent, `baskets:read` | Basket, content version and current state |
| PUT `/baskets/{basketId}` | Human or assigned agent, `baskets:write` | Full replacement with a new content version |
| POST `/baskets/{basketId}/evaluations` | Human or assigned agent, `baskets:evaluate` | 201 immutable evaluation |
| GET `/evaluations/{evaluationId}` | Human or assigned agent, `baskets:read` | Original evaluation evidence and expiry |
| POST `/evaluations/{evaluationId}/decisions` | Human approver, `approvals:decide` | 201 immutable approve/reject decision |
| POST `/orders` | Human or assigned agent, `orders:commit` | 201 persisted mock order from an evaluation ID |
| GET `/orders/{orderId}` | Human or assigned agent, `orders:read` | Exact committed snapshot |
| GET `/requests/{requestId}/events` | Human or assigned agent, `audit:read` | Ordered events with cursor pagination |

All mutations require `Idempotency-Key`. Basket replacement and evaluation also
require `X-Expected-Basket-Version: <contentVersion>`. Missing precondition is
428; wrong version is 412. `X-Basket-Version` is returned on basket responses.
Content version changes only when
lines change, not on approval or status refresh. Duplicate product IDs are
rejected even if their other fields differ. Maximum 50 unique lines and 10,000
integer sales units per line in v1; fractional/variable-weight ordering is out
of scope. `salesUnit` must match the catalog, not an agent-invented conversion.
Catalog lot multiples are enforced. Missing lot evidence blocks, and deposit-
bearing or variable-weight products are ineligible until their full quantity
and charge semantics are supported; the gateway never silently omits deposits.
Canonical lines are sorted by product ID; reordering identical lines is a no-op
and cannot clear a rejection. Basket responses use Cache-Control: no-store;
the explicit version is a mutation precondition, not an HTTP representation
validator. No ETag or conditional GET is advertised for changing readiness.

The approval endpoint accepts only decision and optional comment. It derives
the basket, amount, customer, and approver from the stored evaluation/session.
It cannot accept a different total or supplied signature as a substitute.
An evaluation has at most one human decision. Rejection cannot be reversed;
the basket must be revised and evaluated again to request another decision.

## 5. Evaluation, Units, Prices, and Evidence

Evaluate only the submitted shortlist using the authenticated customer's mapped
upstream ID and the request delivery date. Match responses by product ID, not
array position. Missing, duplicate, unexpected or malformed product records
fail closed. Validate customerId, currency, and pricingDate on PriceResponse.
AvailabilityResponse has no customer/currency echo: validate its requestedDate
and preserve customer provenance from our outbound request, never invent echoed
fields. Upstream treating all customers alike does not relax tenant isolation.

Use only the server-side challenge `X-API-Key` on the allowlisted challenge host
and endpoints. Never forward a gateway bearer credential or human cookie.
Catalog download links are redirects, not product JSON: bootstrap the cached
catalog from the final file, with HTTPS/host allowlisting and bounded redirects.
No credentials follow an unapproved redirect; no downloads occur per search.

Parse upstream timestamps with explicit offsets, including `+0200`/`+0300` as
well as colon forms, then normalize gateway output to UTC. Preserve supplied
offsets; never reinterpret an offset timestamp as local time. If an upstream
timestamp has no offset, use Europe/Helsinki only when that local time exists
and is unambiguous; ambiguous/nonexistent DST times or malformed values are
502 UPSTREAM_INVALID. Compare pricingDate and requestedDate by their Helsinki
calendar date, not string equality with the request. A schedule availableDate
may be a plain ISO date or a timestamp converted to its Helsinki date.

Compare cutoff against both parsed upstream timeNow and gateway time; it must
be in the future relative to both. An absolute clock discrepancy over 60 seconds
returns 503 UPSTREAM_CLOCK_UNTRUSTED. This is a conservative demo threshold,
not an upstream guarantee. Fixture mode uses its isolated, consistent test clock.

Check catalog orderability, sales units, dietary evidence and quantity bounds.
Missing an allergen declaration is not evidence of absence. A required exclusion
fails on contains, may-contain, or unknown evidence. Dietary claims must be
normalized from actual supplied evidence or an explicitly labeled, reviewed
fixture; never inferred from the product name. Lactose-free is not milk-free.
Unsupported constraint interpretation fails rather than becoming an empty rule.

Decode upstream JSON numeric tokens directly into a decimal type, with no
IEEE754 intermediate; use a maintained decimal-preserving parser and arithmetic
library. Upstream `catalogPrice.value` supplies net price per sales unit and
`priceWithTax.value` supplies gross price. Quantity must equal decimal 1 or 1.0.
`error == true` or absent/null optional price/tax objects gives PRICE_UNAVAILABLE,
not a 502. When present, malformed required members give 502 UPSTREAM_INVALID.

Require EUR on PriceResponse and both order-price objects, and require each
object's validFrom <= normalized pricingDate <= validTo. Check the two nested
validity windows independently. Require exact decimal equality of
catalogPrice.valueWithTax and priceWithTax.value. Define cents(x) as half-up
rounding of 100*x: cents(net + taxValue) must equal cents(gross), and the difference
between cents(net * taxRate / 100) and cents(taxValue) must be at most one cent
to accommodate supplied per-unit rounding. Tax rate is a percent between 0 and
100, not a fraction. Inconsistent price/tax data returns 502 UPSTREAM_INVALID.
These are adapter checks, not a claim about a fixed Finnish VAT rate.

`netPriceFound` is provenance, not permission. Neither listPrice nor
comparisonPrice is ever charged, including when netPriceFound is false.

Preserve decimal unit prices as strings. Each line amount is quantity times
unit price, rounded half-up to EUR cents. Sum rounded line net/gross amounts;
line tax is gross minus net. All policy checks use the summed gross integer
amount. Show sales unit, quantity, unit prices, VAT, and line totals explicitly.
No negotiable quote, payment, stock reservation, or price lock is implied.

Availability normalization distinguishes a valid refusal from a malformed body:

| Upstream condition | Gateway behavior |
| --- | --- |
| Empty scheduleLines | Block DELIVERY_UNAVAILABLE; missing optional cutoff/model is expected here |
| More than one schedule line | 502 UPSTREAM_INVALID: unsupported by this v1 adapter; not claimed invalid under the upstream array schema |
| Product or schedule salesBlock true | Block SALES_BLOCK |
| Missing/null cutoff or availableDate for a nonempty schedule | Block DELIVERY_UNCONFIRMED |
| Unparseable non-null date/time | 502 UPSTREAM_INVALID |
| Offered (earliest) date is later than the authorized date | Block DELIVERY_DATE_MISMATCH; require a new human request to change the date. An earlier earliest-date is deliverable on the authorized date (organizers: availableDate is the earliest delivery; the mock API returns it regardless of requestedDate) |
| Exact model Stock, finite nonnegative amount and matching technical unit | Require decimal amount >= integer order quantity; 0/shortfall blocks INSUFFICIENT_STOCK |
| Exact model Terminal, including the 999999 sentinel | Block QUANTITY_UNCONFIRMED; omit availableQuantity |
| Missing, null or other logisticModel; sentinel on a non-Terminal record | Block QUANTITY_UNCONFIRMED; normalized model Unknown where necessary |
| Missing/malformed required members, negative amount, or impossible numeric value | 502 UPSTREAM_INVALID |

Match schedule salesUnit to both catalog and proposed unit; do not compare a
unit string to a quantity or infer units from comparisonPrice. Missing verified
unit mapping blocks UNIT_UNCONFIRMED. Stock may be fractional even though v1
orders use integer sales units. Cutoff checks apply only after a deliverable
dated schedule is established. Unknown quantities are never represented as zero
or 999999 in confirmed gateway evidence.

Exact-date matching is our conservative policy: an upstream earliest-available
date alone does not establish authorization or route feasibility for a different
receipt day. No within-day arrival guarantee is available. Preparation lead time
is a buyer planning constraint and must not be invented by the adapter.

An evaluation is an immutable snapshot with basket version, policy/catalog
versions, normalized lines, reason codes, totals, source mode, checkedAt and
expiresAt. Freshness lasts at most 120 seconds and never beyond the earliest
cutoff. This is a demo policy, not an organizer SLA. Its outcome is `allowed`,
`approval_required`, or `blocked`. A blocked evaluation may lack a complete
total; never represent missing prices as zero. The gateway returns 503 for
upstream outages; this is our mapping, not a documented upstream response schema.
It does not publish an evaluation or change the active pointer on that failure.

Persist an allowlisted immutable adapter-evidence record linked by evidenceId:
outbound customer/date/product IDs, fetch times, original and normalized
timeNow/cutoff/pricing dates, both nested price validity windows, exact decimal
net/gross/duplicated-gross/taxRate/taxValue, stock flags/quantities/units, and
catalog field references. No HTTP credentials or raw validation-error bodies.
The public evaluation exposes normalized facts plus evidenceId; owner/debug
access to the underlying record is separately authorized, not a public URL.

Upstream 422 or structurally invalid 200 maps to 502 UPSTREAM_INVALID. Upstream
401/403, timeouts, 5xx and rate-limit responses map to 503 UPSTREAM_UNAVAILABLE
without publishing an evaluation. Do not copy upstream detail[].input or raw
error bodies. The gateway's own throttling uses 429. Use bounded retry/backoff
for retryable failures, not authentication/validation failures; no fixture fallback.

Only the active evaluation may be approved or committed. Creating a new one
supersedes the previous evaluation and any approval, even with identical lines.
Late upstream responses must not publish over a changed basket: transactionally
compare basket version, request state and captured policy/catalog versions.
Concurrent evaluations of one basket are serialized with a bounded 30-second
wait; saturation returns REQUEST_IN_PROGRESS and can be retried. Order creation is unique
per request. A rejected unchanged basket cannot be re-evaluated to erase the
human rejection; its contents must actually change first.

## 6. State and Approval Binding

Basket state: `draft`, `blocked`, `awaiting_approval`, `ready`, `rejected`,
`expired`, `cancelled`, or `ordered_mock`. The latest evaluation and decision
determine readiness; expiry is checked against server time on every action.
Request cancellation overrides all uncommitted baskets. An order is terminal.

| Event | Precondition | Result |
| --- | --- | --- |
| Replace lines | Request active; not committed; matching content version | New version, draft; prior evaluation/approval invalid |
| Evaluate | Active request/current version; not rejected unchanged | Publish evaluation and derive blocked/awaiting_approval/ready |
| Approve | Current unexpired approval_required evaluation; authorized human ceiling covers total | Ready, bound to this evaluation only |
| Reject | Same current approval_required preconditions | Rejected until a real content change |
| Expire | Evaluation expires or referenced policy/catalog changes | Not ready; new evaluation required |
| Cancel request | No order committed; human cancellation authorized | All its uncommitted baskets cancelled |
| Commit | Current allowed or approved evaluation; final checks pass | One ordered_mock result, consume request |

Approval is bound by the immutable evaluation ID to exact customer, request,
site/date, basket version/lines/prices/totals, and policy/catalog versions. It
expires with the evaluation and is invalid if the approving principal no longer
has authority. Server records actor/time and decision; client text is not proof.

Before commitment, fetch fresh upstream prices/availability for the shortlist.
Recompute line totals and policy. Any price change, eligibility change, expired
cutoff, insufficient stock, or now-unknown required fact prevents commitment.
A price change requires a new evaluation even if cheaper or still below budget.
A harmless raw stock-count change with enough quantity does not invalidate an
otherwise identical basket. Approval cannot waive a new hard failure.

Perform upstream calls outside a database transaction, then in one final
serialized transaction recheck current versions, request state, actor and
approver grants, shared daily allowance, expiry and evidence age. Upstream
checks used at commit must be no more than 30 seconds old and before cutoff.
Never keep a transaction open awaiting an LLM or network call. The upstream
cannot atomically reserve inventory; mock confirmation is not supplier acceptance.
Persist final recheck evidence separately as the order's commitEvidenceId;
never mutate the original evaluation's evidence to make it appear fresh.

## 7. Idempotency and Failure Semantics

Key scope is customer + principal + method + normalized path + key. Bind it to
the canonical parsed body and X-Expected-Basket-Version header; no arbitrary
body-field omission.
Retain keys and request fingerprints for at least 24 hours. Successful mutations
and their original response are stored atomically with the operation. Same key
and payload replays that response after current authentication/access checks;
changed payload/precondition returns 409 `IDEMPOTENCY_CONFLICT`.

Concurrent same-key requests return 409 `REQUEST_IN_PROGRESS` with Retry-After;
they do not execute twice. A failed operation has no purchasing side effects
(a refusal/security audit record is permitted) and
may be retried with the same bound payload/key. A lost response after a completed
commit replays success even when the original evaluation has since expired.
With a different key, attempts to reuse a consumed request return 409
`REQUEST_ALREADY_ORDERED`; the database uniqueness rule is permanent, not 24h.

Errors use RFC 9457 `application/problem+json`: type, title, status, code,
detail, instance and traceId. No keys, raw upstream bodies, hidden reasoning,
stack traces, or cross-customer data. Domain evaluation reasons use stable codes.

| HTTP | Codes / interpretation |
| --- | --- |
| 400 / 422 | MALFORMED_REQUEST / INVALID_INPUT; unknown fields, duplicates, invalid dates/units/limits |
| 401 / 403 / 404 | UNAUTHENTICATED / FORBIDDEN / NOT_FOUND |
| 405 | METHOD_NOT_ALLOWED |
| 409 | IDEMPOTENCY_CONFLICT, REQUEST_IN_PROGRESS, REQUEST_ALREADY_ORDERED, REQUEST_CANCELLED, EVALUATION_SUPERSEDED, DECISION_ALREADY_RECORDED, EVALUATION_REQUIRED, APPROVAL_REQUIRED, POLICY_BLOCKED |
| 410 | EVALUATION_EXPIRED |
| 412 / 428 | VERSION_CONFLICT / PRECONDITION_REQUIRED |
| 429 | RATE_LIMITED with Retry-After; no unbounded automatic retries |
| 500 | INTERNAL_ERROR; sanitized gateway fault, not mislabeled as upstream data |
| 502 / 503 | UPSTREAM_INVALID / UPSTREAM_UNAVAILABLE or UPSTREAM_CLOCK_UNTRUSTED; no invented fallback prices |

An evaluation returning `blocked` is a successful 201 evaluation, not an order
failure hidden in a 200 order response. Structural upstream violations are 502;
valid upstream records indicating no price/stock are blocked evaluations.

## 8. Audit and Live/Fixture Boundaries

Append events for request creation/cancellation, basket revisions, evaluations,
human decisions, commit attempts/outcomes, and successful mock orders. Include
server actor, request/basket/evaluation/order IDs as applicable, UTC timestamp,
monotonic per-request sequence, trace ID, reason codes, and bounded summary.
Never claim a stored log is cryptographically tamper-proof. Mutation success
and its audit event are atomic; read-only denials go to a separate security log.

Pagination uses `afterSequence` and `limit`; `nextAfterSequence` is the last
returned sequence, or the input cursor for an empty page. The caller repeats
until an empty page. Tenant checks precede any cursor lookup.

Live and fixture modes are deployment-controlled and returned on evidence and
orders. Fixture mode cannot be selected in request bodies, headers, or prompts.
Its state, credentials, IDs and idempotency records are isolated from live mode.
Live mode uses the organizer APIs; both modes submit orders only to our local
mock. No order API, payment route, or production login integration is available.

## 9. Required Contract Tests

| ID | Test | Required outcome |
| --- | --- | --- |
| G01 | Agent calls human creation/approval endpoint | Denied; actor cannot self-assert human status |
| G02 | Foreign customer/request IDs on read, write, events or replay | 404; no side effects or existence leak |
| G03 | Cookie mutation lacks valid Origin/CSRF | Denied |
| G04 | Agent sends prices, approval flag, customer override or fixture switch | Strict schema rejection |
| G05 | Caller replaces/evaluates a stale basket version | 412; cannot overwrite newer content |
| G06 | Valid affordable basket within authority | Commit without unnecessary human approval |
| G07 | Above autonomous ceiling, within hard limits | Approval required; unauthorized commit refused |
| G08 | Human approval followed by line/date/policy/price change | Old approval cannot authorize new commitment |
| G09 | Unknown allergen, may-contain exclusion, bad units or missing price | Blocked; approval cannot override |
| G10 | Terminal sentinel 999999, stock shortfall, sales block or late date | Blocked with the specific reason |
| G11 | Cutoff or evaluation expires while committing | No order; re-evaluation required |
| G12 | Two orders race for shared daily allowance | Atomic limit check; no overspend |
| G13 | Same-key retry or lost commit response | Same resource/response; one order and one spend entry |
| G14 | Same key, changed body/expected version | 409 without execution |
| G15 | Different keys/baskets race for the same request | At most one order |
| G16 | Late evaluation races with edit/cancel | Cannot become active for obsolete request/version |
| G17 | Agent retries an unchanged human-rejected basket | Still rejected; no reset by re-evaluation |
| G18 | Agent or approver authority revoked before commit | Denied even if earlier evaluation/approval was valid |
| G19 | Upstream timeout, malformed data or rate limit | Explicit failure; no mock success or silent fixture fallback |
| G20 | Decimal rounding, net/gross and comparison price differ | Correct gross-goods totals; comparison price never charged |
| G21 | Restart after commit and repeat with a new key | Consumed request remains consumed |
| G22 | Cancellation races with commit | One terminal result; never cancelled plus committed |
| G23 | Empty/null availability fields or unavailable optional price objects | Valid business block, not a malformed-response error |
| G24 | Offset +0200, midnight date-time echoes, DST ambiguity or excessive clock skew | Correct normalized comparison or explicit fail-closed error |
| G25 | Availability has no customer/currency fields | Bind outbound customer context; do not demand absent echoed fields |
| G26 | An earlier offered date replaces the requested date | Block mismatch; never silently change receipt date |
| G27 | Inconsistent duplicated gross/tax values or wrong nested validity window | 502; comparison/list price cannot repair it |
| G28 | Same lines reordered or both credential kinds supplied | No reset of rejection; ambiguous authentication denied |

These requirements are exercised by the runtime suite in [tests](../tests/),
including HTTP race/restart cases and adapter unit tests. They are not exhaustive
proofs of all interleavings or production safety. The separate schema checker
validates wire shapes only; run both suites before changing this boundary.