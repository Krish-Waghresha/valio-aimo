# Demo Script: "Pies for 100 by Saturday"

Goal: in 3 minutes, judges understand the problem, see the agent do real work on
real challenge data, see the controls hold, and remember one sentence.

**One-liner:** *Tell Aimo what you're cooking. The agent plans and shops it on live
prices and stock, and it can never spend more than you allow.*

## Pitch Structure (3:00)

| Time | Beat | What is said / shown |
| --- | --- | --- |
| 0:00-0:20 | **Problem** | "It's Thursday. A caterer gets a wedding for 100 on Saturday. Today: recipe math, 20,000 products, pack sizes, stock, delivery cutoff, allergy check, boss sign-off. That's an evening of work, and one typo orders 1,000 kg of butter." |
| 0:20-0:30 | **Who** | Chef Anna (fictional). Head chef can spend small amounts freely; big orders need the manager. Same rules Aimo's B2B customers live by. |
| 0:30-1:30 | **Live demo, the magic** | Anna types (later: speaks) one sentence. The agent shows what it understood, asks one question only if needed, builds a basket of **real Aimo catalog products** with live prices, pack rounding and delivery-date checks. |
| 1:30-2:15 | **Live demo, the trust** | The basket is above Anna's limit, so the gateway routes it to the manager. Manager approves on another device and places the (mock) order. Show one guardrail: unsafe allergen product blocked, or an absurd quantity questioned. |
| 2:15-2:40 | **Why it's different** | Not a chatbot that fills a cart: the AI understands, deterministic code calculates, and the gateway enforces. The same open API works for *any* external buyer agent. Brand-neutral and fully audited. |
| 2:40-3:00 | **Value + close** | For Aimo: more orders through digital channels and stickier customers, plus fewer mis-orders and less waste (their 2030 waste goal names the order-delivery process). Close on the one-liner. |

## Click Path That Works Today (live data, port 8003)

Preparation (do every time):

1. Fresh database per rehearsal (tokens last 8 h):
   `uv run aimo-gateway init --mode live --database data/gateway/demo-live-N/gateway.sqlite --origin http://127.0.0.1:8003`
   then `policy ... --autonomous-limit 3000` (EUR 30), then `serve --workspace ...`.
2. Window A (chef) and window B (manager, private window), both logged in, zoom 110%.
3. Run the flow once 10 minutes before to warm up; then start a fresh DB so Approvals/Orders show 0.
4. Keep a screen recording of a perfect run as backup (venue Wi-Fi can kill live APIs).

On stage:

1. **Chef:** "Fill savory wedding-pie example", budget 500, confirm dietary, Submit.
2. Show **Basket**: real products (Myllyn Paras flour, Valio Eila lactose-free butter, ...),
   pack math ("needed 2.5 kg → 13 × 200 g"), cost per serving ~EUR 0.93.
3. Point at the **Decision** panel: "Above the autonomous spend limit, so the agent cannot order this."
4. **Manager window:** Approvals (1) → Approve purchase → Confirm → Place mock order → Confirm.
5. Back to chef: "Mock order placed", then show Activity/audit and Export record.
6. Optional 15 s: "12 litres lactose-free milk" with auto-commit, which goes through
   **without** approval because it is under EUR 30. Shows "humans only when needed".

## Target Story (after the agent/UX work on this branch)

1. 🎤 "Savory pies for a wedding, 100 guests, Saturday, one guest has a nut allergy, keep it under 400."
2. Chips: `100 servings` `Sat` `savory` `nut-free` `≤ €400`. Only the inferred one (delivery Friday for prep time) asks for a tap.
3. The basket builds line by line with real products; one low-reliability item is swapped with a "Why?".
4. Guardrail moment: the chef edits butter to "1000 kg" by mistake, and the agent asks "Did you mean 10?".
5. Manager approves on a phone; the order is placed with an audit trail.
6. (Stretch) A third-party agent calls the same gateway via MCP with a restricted role and gets refused above its limit.

## Rules for a Perfect Demo

- Show, don't tell: no slides during the demo segment; at most 3 slides total (problem, architecture, value).
- One persona, one scenario, one guardrail. Don't tour every feature.
- Say numbers out loud: "100 guests, 8 products, EUR 93, 0.93 per serving, 1 approval".
- Name the trust model in one breath: *"AI proposes, code checks, the gateway enforces, humans approve only exceptions."*
- Never say "real order": say "mock order; Aimo exposes no order API in the challenge".
- Have answers ready: Why not just A.I.mo? (it answers questions; ours executes a controlled purchase).
  What if the LLM is wrong? (it can't change quantities, prices or authority; the gateway re-checks everything).
  How does an outside agent use it? (OpenAPI now, MCP adapter next).

## Polish Issues Found in the Current UI (fix before judging)

- Live availability shows raw `9999999999` (the "unlimited stock" sentinel). Show "In stock" instead.
- Every live line repeats "Net price was not found. List and comparison prices are not charged.", which reads as an error.
- "No product image" on every row: the catalog only has media IDs, no URLs. Use category icons instead of empty boxes.
- Disclaimers on every screen ("Fictional prototype account", "Not a live organizer result"). Collapse them into one badge.
- The request form has ~15 controls, and "Fixture scenario" is visible to the chef. Hide it behind a demo mode.
- The Plan tab is a wall of text that duplicates the ingredient table. Make the Basket the default tab.
- "Deterministic planner. No external model is interpreting this request." undersells the product. Reword or add the model.
