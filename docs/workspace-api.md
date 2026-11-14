# Purchasing Workspace Integration Contract

Implementation handoff, 2026-11-14. The gateway remains the authority boundary.
This application layer adds the chef workflow without giving agent code human
credentials or access to policy/grant mutation. No production supplier orders.

Implementation status: complete for the supported demo scenarios. Seven browser
journeys verified fixture/live purchasing and human approvals. Runtime xAI calls
require an environment key; deterministic mode is explicitly identified.

## Browser API

Same origin, HttpOnly gateway_session. Login uses existing POST /auth/login with
loginToken plus Origin. Session response includes principalId and csrfToken.
All mutations below require Origin and X-CSRF-Token. Never store credentials
in localStorage or render them into HTML. In-memory or sessionStorage CSRF is
acceptable; gateway bearer tokens never enter browser responses.

- GET /workspace/session: authenticated principalId, scopes, csrfToken,
  mode (fixture/live), agentMode (grok/deterministic), today (Helsinki date),
  recipes (id/title/servings/imageUrl), policy (autonomousLimitMinor/orderLimitMinor).
  Returns 401 if not signed in. Fetching this refreshes the session CSRF token.
- POST /workspace/logout: revokes the current session and clears the cookie.
- GET /workspace/jobs: array of Job objects accessible to this principal.
- POST /workspace/jobs: creates a human purchasing request and starts the worker.
  Body: brief (string), servings (integer), deliveryDate (YYYY-MM-DD),
  maxGrossMinor (EUR cents), dietaryConfirmed (true), dietaryRequirements (array),
  excludedAllergens (array), pantry (object: ingredient key -> nonnegative numeric
  amount in the recipe's unit), preference (balanced/price/reliability/sustainability),
  scenario (normal/shortage/late; fixture only), autoCommit (boolean).
  X-Request-Key UUID prevents duplicate application submissions. Response: Job.
- GET /workspace/jobs/{id}: Job. Poll every 1-2 seconds while processing or
  awaiting an external decision; stop polling when ordered/cancelled/failed.
- POST /workspace/jobs/{id}/decision: decision approve/reject, with an authenticated
  approver session; forwards to the gateway. Response: updated Job.
- POST /workspace/jobs/{id}/commit: explicit mock-order command. Updated Job.
- POST /workspace/jobs/{id}/cancel: human cancellation. Updated Job.
- POST /workspace/jobs/{id}/recheck: human-authorized new evaluation of a
  nonterminal basket. Prior approval does not carry over.
- GET /workspace/jobs/{id}/events: gateway audit events array.
- GET /workspace/jobs/{id}/export: downloadable JSON including plan, evaluation,
  order, and audit events. Tenant/grant checks apply.

Application authorization: only a human with requests:create can start a job.
The trusted workspace broker creates the immutable gateway request, grants only
the configured buyer-agent and manager for that request, and invokes the planner
with request facts. Users cannot choose principal IDs, policy, prices, or mode.
Approval is never automatically performed by the planner or the workspace.
autoCommit is the human's explicit instruction to commit only inside authority;
it never supplies approval. Auto-commit is used only when the worker's first
evaluation is allowed; a human approval leaves explicit commitment as a separate
human action. Rejection stops the workflow. Human commits retain human actor IDs.

Live recipe matching is a reviewed catalog shortlist, not unbounded keyword
matching. Technical sales units cannot substitute for physical ingredient units.
Structured pack metadata is used; the live recipe's egg component uses a clearly
labeled 50 g-per-egg mass assumption. Unsupported recipe variants remain blocked.

## Job Shape

```json
{
  "id": "uuid", "requestId": "uuid", "createdAt": "UTC timestamp",
  "brief": "Pies for 100 wedding guests", "servings": 100,
  "deliveryDate": "2026-11-16", "maxGrossMinor": 50000,
  "state": "planning", "mode": "fixture", "agentMode": "deterministic",
  "autoCommit": false, "scenario": "normal", "preference": "balanced",
  "plan": null, "basket": null, "evaluation": null, "order": null,
  "messages": [], "error": null
}
```

States: planning, checking, needs_clarification, blocked, awaiting_approval,
ready, ordered_mock, rejected, cancelled, failed. Messages are short factual
progress/decision summaries, never private model reasoning. error is a readable
sanitized string. plan/basket/evaluation/order may be absent until available.
Gateway response shapes remain those in gateway.openapi.json.

Plan:

```json
{
  "title": "Vegetable wedding pies", "recipeId": "vegetable-pie",
  "servings": 100, "recipeSource": "Curated synthetic demo recipe v1",
  "imageUrl": null, "questions": [], "warnings": [], "explanations": [],
  "ingredients": [{
    "key": "flour", "label": "Wheat flour", "unit": "kg",
    "required": "5", "pantry": "1", "needed": "4",
    "productId": "demo-flour", "quantity": 2, "packAmount": "2",
    "overage": "0", "candidates": [{
      "productId": "demo-flour", "name": "Flour 2 kg", "salesUnit": "BAG",
      "packAmount": "2", "imageUrl": null, "labels": [],
      "reliability": 0.98, "carbonKgPerKg": 0.8,
      "unitNet": null, "unitGross": null, "available": null
    }]
  }],
  "lines": [{"productId": "demo-flour", "salesUnit": "BAG", "quantity": 2}],
  "comparison": {"reliability": null, "carbonKgEstimate": null, "carbonCoverage": 0}
}
```

Decimal physical amounts are strings. Reliability/CO2 values are informational,
nullable, and never a promise. Carbon is a category average, not an individual
product measurement. Coverage must accompany basket estimates. Candidate live
prices/availability are filled by the trusted integration, not guessed by planner.
Missing conversion/evidence means a question or block, not fabricated completeness.

## Planner Module Interface

Own src/aimo_gateway/planner.py and tests/test_planner.py. No changes to auth,
gateway policy/commit, app routing, existing catalog or upstream modules.

- demo_catalog(): Catalog with existing demo-milk/demo-flour retained plus
  enough synthetic pie ingredients and alternatives. Precise physical pack amounts,
  lot rules, dietary/allergen evidence, labels, reliability and carbon metadata.
- DemoSource(clock, scenario='normal'): FixtureSource-compatible object,
  mode='fixture', fetch(customer,date,ids), close(). Correct prices/stock/units for
  its demo catalog; one reproducible stock shortage and late-date scenario. Do not
  change the meaning of the original technical fixture module.
- Planner(catalog, data_dir=None).recipes(): list of supported recipe metadata.
- Planner(...).plan(brief, servings, constraints, pantry=None,
  preference='balanced'): Plan shape above. Curated recipe + direct milk/product
  quantity requests, genuine deterministic serving/pack/lot rounding. Unsupported
  needs return questions. Candidate matching uses actual static catalog metadata;
  supported explicit conversion or curated verified mapping only. No API calls.
- Planner(...).select(plan, excluded_product_ids): recompute selection/lines from
  existing candidates when the integration excludes unavailable products.

No external LLM access is available at handoff. Main integration adds an optional
xAI tool-calling interpreter; deterministic mode must be visibly identified.

## UI Deliverable

Own only src/aimo_gateway/static/index.html, app.js, styles.css and permitted
static images/icons as necessary. Vanilla JS served by FastAPI; no build server.
Match docs/brand-research.md and docs/prototype-spec.md. Compact teal #005670,
lime #C0E021, white/neutral surfaces, condensed headings and readable body type.
Use Lucide icons from a known library, with accessible labels/tooltips. Use real
permitted food imagery, not decorative SVG illustrations. Mobile and desktop.

Views: request workspace, job plan/basket/comparison/activity, approvals, orders.
Include login token form (password input), refresh/reload recovery, logout,
new request, servings/date/budget/preferences, dietary confirmation, pantry edit,
fixture-only scenario selector, explicit auto-commit checkbox, submit progress,
questions/errors, selectable comparison ranking preference, approval/rejection,
mock commit, cancel, and export. Do not show unavailable controls as functional.
Do not invent metrics, order history, customer endorsements, or live AI activity.

Keep background job polling and state updates functional. A manager sees approval
actions only with approvals:decide scope. Chef without that scope sees awaiting
approval, not an automatic role switch. Editing an existing request starts a new
request; it cannot silently retain the old approval. No frontend secret defaults.