# Gateway Contract Review Record

Date: 2026-11-14. Status: initial contract review record; subsequent implementation review below.

## Review Method

Two independent read-only subagent reviews were requested with identical prompts.
Neither reviewer was supplied with the other's findings or a list of suspected
defects. Short prompts reduce steering but cannot establish absence of bias.

Requested Gemini model: `Gemini 3.1 Pro (Preview) (copilot)`. The tool rejected
that selection because Gemini was not in the environment's available model list.
No Gemini review occurred. Successful review invocations explicitly selected:

- `GPT-5.3-Codex (copilot)`
- `Grok 4.7 (copilot)`

Both used the read-only Explore agent. No Anthropic or Auto model was requested.

Exact prompt sent to each reviewer:

> Review docs/gateway-contract.md and docs/gateway.openapi.json against data/valio/openapi.json. Report concrete flaws with severity, file references, and minimal fixes. Read-only.

Codex returned four findings; Grok returned eleven, with substantial overlap.
These are not fifteen distinct proven bugs. Findings were checked against the
upstream schema/descriptions and existing smoke-test evidence before revision.

## Findings and Disposition

| Finding | Reviewer severity | Resolution |
| --- | --- | --- |
| Offset timestamps and date-time echoes need explicit normalization | High/low, both reviews | Accept offsets including +HHMM, normalize UTC output, compare Helsinki dates; reject ambiguous local DST times. Check upstream/server clocks with an explicit demo skew bound. |
| Decimal numeric input and duplicated gross/tax checks underspecified | Medium/high, both | Require decimal-token parsing, independent nested validity checks, explicit gross equalities and tax-rounding tolerance. Never charge list/comparison prices. |
| Single schedule assumption conflates unavailable with malformed | Medium/high, both | Empty schedules block delivery. Multiple lines are explicitly unsupported by this adapter, not declared invalid under the upstream schema. |
| Availability does not echo customer or currency | High, Grok | Compare echoed identity/currency only on price responses; retain outbound tenant provenance for availability. |
| Earlier offered delivery may not match human authorization | High, Grok | Adopt conservative exact-date matching. This is our v1 policy, not proof that the upstream cannot deliver later. |
| Nullable/unknown logistics, cutoff and dates need representable outcomes | Medium/high, Grok | Normalize Unknown model; distinguish legal missing evidence from malformed values; terminal/sentinel quantities never become confirmed stock. |
| Stock quantity versus sales/comparison unit ambiguity | Medium/low, Grok | Compare decimal amount to integer quantity; require matching catalog/schedule sales units. Zero stock is a business block. Narrowed examples to observed technical units. |
| Gateway credentials/errors must not be forwarded upstream/downstream | Medium, Grok | Explicit server-only X-API-Key, redirect restrictions, sanitized status mapping and no raw validation-error echo. |
| Evaluation lacks reproducible source evidence | Medium, Grok | Persist an immutable allowlisted evidence record and expose its protected ID. Retain separate final-commit evidence. |
| Gateway 503 could be misread as an upstream guarantee | Low, Grok | Explicitly identify it as gateway error mapping. |
| Example SKU 460000/RAS is not in the upstream example list | Low, Grok | Retained: it was verified in the downloaded catalog and successful smoke test. An example list is not the full product domain. Sample evaluation is explicitly fixture data, not a current stock assertion. |

Additional local consistency checks replaced a content-only HTTP ETag with an
explicit expected-content-version header, rejected mixed human/agent credentials,
and specified that line reordering cannot clear a human rejection.

A negative schema check exposed an allowed evaluation containing unconfirmed
terminal stock. Eligible evaluation/order lines now require confirmed Stock
availability, no sales block, dated evidence, pricing, and no line-level blockers.

## Reproducible Validation

OpenAPI and example lint:

```sh
npx --yes @redocly/cli@2.78.0 lint docs/gateway.openapi.json --config docs/redocly.yaml
```

Wire-schema and operation-boundary checks, in an isolated Python environment:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install 'jsonschema[format]==4.25.1'
.venv/bin/python scripts/check_gateway_contract.py
```

The portal downloader remains dependency-free. The optional schema checker is
the only Python code here requiring jsonschema. Validation during this task used
a temporary environment outside the repository, not a global installation.

Redocly 2.14.4 produced composed-example false positives that the standards
validator did not reproduce. Redocly 2.78.0 validates the examples with the
checked-in configuration. `allowAdditionalProperties: true` prevents the linter
from inventing extra restrictions in partial composition schemas; explicit
`additionalProperties: false` on boundary objects still applies and is tested.

The remaining lint warning is the intentionally unspecified API license. No
license was assigned on the owner's behalf. Source references, local links,
schema examples, and declared endpoint boundaries are checked; this is not a
running service, a security certification, or proof of race-free implementation.

## Owner Decisions and Remaining Gates

- Krish must approve the contract and policy defaults before implementation.
- Confirm whether exact-date matching, integer-only sales units, and blocking
  terminal quantity uncertainty fit the intended demo. They are conservative
  v1 restrictions, not organizer requirements.
- Choose the human authentication/bootstrap mechanism and actual approval limits
  without allowing the buyer agent to issue its own grants.
- Confirm the source of trustworthy dietary evidence. Missing evidence remains
  blocking; synthetic reviewed fixtures must be clearly separated from live facts.
- Implement and run G01-G28 from the contract against the real gateway before
  claiming authorization, freshness, concurrency, or idempotency guarantees.

The two subagents reviewed the pre-revision draft. The revisions received local
schema/static validation, not a second independent review. This record preserves
that distinction. No production endpoint or order was used during this work.

## Implementation Review and Verification

The owner subsequently authorized implementation. Both GPT-5.3-Codex and Grok
4.7 were invoked again as independent read-only reviewers with this prompt:

> Review src/aimo_gateway and tests against docs/gateway-contract.md. Report concrete bugs with severity, references, and minimal fixes. Read-only.

Accepted findings were addressed: distinct internal/framework error codes,
canonical basket-body idempotency, 403 on lost approver authority, bounded
serialization of different-key basket evaluations, a same-request/two-basket
HTTP race test, realistic nested decimal parsing tests, and tests for each
nested price-validity window. Live allergen normalization was added after
verifying code meanings against the GS1 vocabulary, including conflicting and
may-contain declarations. Missing evidence still blocks.

Two recommendations were not adopted as proposed. The catalog does not specify
a default lot step, so missing lot data remains blocked instead of assuming 1.
Retry-After for in-progress requests remains a short retry interval: a 120-second
recovery lease is not an estimate of actual task duration. Deposit-bearing items
remain explicitly ineligible until their charges can be included correctly.

The final local suite has 71 passing runtime tests, with the original 29 schema
checks also passing. Both fixture and live-data HTTP demo harnesses were run
successfully. They exercised separate human/agent principals, approval refusal,
simulated human-principal approval, final recheck, one mock order, identical replay,
and audit retrieval. No actual supplier order or payment was submitted.

These reviewers examined the implementation before the final fixes; the fixes
received local tests, not a claim of a subsequent independent security audit.
The chef agent, branded UI, production SSO, operational monitoring/retention,
and actual supplier commitment remain outside the implemented backend.