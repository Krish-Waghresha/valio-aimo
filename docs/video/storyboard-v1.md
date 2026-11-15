# Aimo Purchasing agent: demo video storyboard (max 3:00)

## 1. Research takeaways (quick pass)
- **Respect the length limit. Show the product, not the code.** Judges score what the product does. 60–120 s is the usual advice, so 3:00 is the ceiling, not the goal. About 30 % problem, 70 % solution. ([tips.hackathon.com](https://tips.hackathon.com/article/creating-the-best-demo-video-for-a-hackathon-what-to-know), [dev.to: make your Devpost submissions not suck](https://dev.to/jacklynbiggin/how-to-make-your-devpost-submissions-not-suck-37i0))
- **The first line decides attention.** Get a one-line positioning out within 5–15 s, and say what it is, for whom, and why it matters. ([Inc42: 10 demo days](https://inc42.com/buzz/10-things-i-have-learned-from-running-10-demo-days-about-startup-pitches))
- **Tell it as a story, with one clear idea.** Judges remember one thing, so say it plainly. ([YC: Guide to Demo Day Presentations](https://www.ycombinator.com/blog/guide-to-demo-day-pitches/))
- **Put the product on screen within 15 s. Pre-record and keep a backup take.** Use problem → demo → how → impact. ([Reskilll: pitch in 3 minutes](https://blogs.reskilll.com/hackathon-demo-presentation-tips-pitch-3-minutes-win-2026/))
- **Captions:** many judges watch on mute. Every beat needs a burned-in caption that works without the voiceover. Keep captions to 7 words or fewer, so the caption shows the claim and the voiceover adds the colour.

Caveat: most of these sources are practitioner blogs, not official guidance. The advice agrees across them, though.

**The one idea for this video:** *"An agent can buy from Valio Aimo on its own, but only inside rules a human set, and every step is on the record."*

## 2. Production rules
- Record at 1920×1080 with browser zoom at 125 % so text reads on a phone. Hide bookmarks and extensions.
- Do the main take in **one continuous run** from "Find products" to "Approve". Price checks expire after 2 min, so the manager must approve within about 60 s. Cut for time in the edit, but don't fake the order.
- Don't speed up the "Working on it" steps. They are real backend calls, and that is the point. Show them at 1x and say "these are real calls".
- Voiceover: one calm voice. Music very low, ducked under the voice.
- Captions: teal #005670 bar with white text. Use a lime #C0E021 underline for the criterion keyword.
- Use only the three scripted requests below. **Don't type anything unscripted on camera.**

## 3. Shot-by-shot (target 2:55)

| Time | On screen (view · exact text · exact button) | Voiceover | Caption | Criterion |
|---|---|---|---|---|
| 0:00–0:04 | **Cold open.** Manager phone view, already approved: "Order placed · AIMO-XXXXXXXX". Hard cut to the empty Request bar. | "This order for a thousand litres of milk was placed by an agent…" | "Placed by an agent. Approved by a human." | Hook |
| 0:04–0:10 | Request bar. Typing appears fast (pre-typed, then reveal): `I need 1,000 litres of lactose-free milk by Monday. Find an option that meets our requirements based on price and availability.` | "…and it couldn't spend one euro more than it was allowed. Here's the whole run, live." | "Valio Aimo's own example request" | Hook / E2E |
| 0:10–0:18 | Hold on the request, then a simple 3-box diagram over a blurred UI: **Buyer agent → Trusted gateway (OpenAPI) → Valio Aimo catalog, price & stock**, with a person icon on the "approve" arrow. | "Kitchens will soon order through AI agents. Valio Aimo needs to control what those agents can see, decide, and be trusted with." | "Open gateway + human sign-off" | Problem / Openness |
| 0:18–0:28 | Press Enter. "Reading your request" (1.5 s). Then **"Here's what I understood"** chips: Products 1,000 L lactose-free milk · Delivery **Mon 16 Nov** (dashed) · Budget (dashed) · Diet lactose-free. Zoom on the dashed chip. | "It reads the request into structured needs. Dashed means assumed: 'Monday' became the 16th, and the budget is your per-order limit. Nothing hidden." | "Assumptions shown, not hidden" | User need (20 %) |
| 0:28–0:38 | Click **Find products**. "Working on it" list ticks: Searched the catalog 17,546 → 11 matches · Checked live price & stock (12 products, one lookup) · Compared price, stock & reliability (3 skipped). | "These are the real backend calls: 17,546 products searched, live price and stock checked in one lookup." | "Real lookups, live challenge data" | E2E (30 %) |
| 0:38–0:56 | **Exception card:** "Only 384 L of your usual Arla … for Mon 16 Nov". Highlight the three options one at a time. Cursor clicks **Recommended: Switch all 1,000 L to Valio Arki Eila — €1,150**. | "The usual milk is short, with only 384 litres for Monday. The agent doesn't guess. It ranks good, better, best: the official Valio substitute with the same lactose-free spec and 100 % delivered in full, a split order that costs €637 more, or a short delivery." | "Stock-out → ranked substitutes" | Exceptions (15 %) |
| 0:56–1:06 | Stepper Request → Lookup → **Order** → Approval. Status: **"Waiting for approval — sent to Kitchen manager"**. Callout: "€1,150 > your €500 limit". | "€1,150 is over this buyer's €500 limit. So the agent stops and asks a human." | "Over limit → human sign-off" | Guardrails (20 %) |
| 1:06–1:22 | **Split screen.** Left: chef/buyer view, frozen on "Waiting for approval". Right: Kitchen manager (separate login) sees the request with reason and price. Tap **Approve & place order**. Live steps: "Approved" → "Final price & stock check → order placed" → **AIMO-XXXXXXXX**. | "The kitchen manager logs in separately, sees why approval is needed, and approves with one tap. Price and stock are checked again at commit, and only then is the order placed." | "Separate approver. Re-checked at commit." | Guardrails / E2E |
| 1:22–1:40 | Scroll **"What happened and why"**: decision "Skipped 3 products — cutoff passed (2), not available (1)" → timeline → **Compare alternatives** table (price/L, stock, delivered-in-full %, Hyvää Suomesta label) → Order record (gateway audit). Click to download the JSON record. | "Every decision is written down in plain language, for the buyer and for Valio Aimo: what was skipped and why, what it compared, and a machine-readable record of the whole order." | "Human-readable audit trail + JSON" | Guardrails (audit) / Explainability |
| 1:40–1:52 | **Contrast shot.** New request: `20 kg butter for Friday`. It goes straight through, ≈ €42, badge **"Placed by: Buyer agent"**. Optional voice input here (see §6). | "Under the limit, the agent just does it. No approval needed, still fully logged." | "Under limit → fully autonomous" | Autonomy (20 %) |
| 1:52–2:04 | **Refused actions.** Terminal (large font) or /docs "Try it out": call commit for the pending order *without* approval → RFC 9457 problem JSON, red. Then the same call with a stale quote → refused. A rules card slides in: *Agent can't approve itself · chef can't self-approve · forged fields rejected · hard limit blocks · stale quotes (>2 min) refused · idempotent*. | "And it can't cheat. Committing without approval is refused, a stale price is refused, and the agent can't approve its own order. We had an adversarial tester try." | "The gateway says no" | Guardrails (20 %) |
| 2:04–2:16 | **Need → recipe → order montage** (fast cuts, ~2 s each): `Savory pies for 100 wedding guests on Saturday, under 400 euros` → recipe → scaled ingredients → real products → €93 → manager approval. | "It also works from a need, not a product list: a wedding for a hundred becomes a recipe, then ingredients, then an order for approval." | "From need to order" | User need (20 %) |
| 2:16–2:38 | **Openness.** Browser at `/docs`: OpenAPI 3.1, scroll the 13 operations, open one to show scopes and the RFC 9457 error schema. **If MCP is built:** cut to Claude Desktop with the prompt `Order 20 kg butter for Friday from Valio Aimo`, showing tool calls lookup → quote → order, then the order appears in the same audit log. **If not built:** use the alternative below. | MCP version: "The UI is just one client. This is the same gateway: an open OpenAPI 3.1 contract with scopes and standard errors. Here an outside agent, Claude, orders through it under the same rules." | "Open standard: OpenAPI 3.1 (+ MCP)" | Openness (15 %) |
| 2:38–2:50 | **Assumptions & next steps** card (static, 4 lines): ✔ Live challenge catalog, price & stock · ◻ Rule-based request reading today, LLM pluggable · ◻ Next: signed stock/price evidence (verifiable credentials), real order API, MCP for any agent (drop if shipped) · Orders recorded for approval (the challenge has no order API). | "What's real: live challenge data and the full approval flow. What's next: signed evidence for stock and price, and a real order API." | "Assumptions visible. Path to production." | Openness (15 %) |
| 2:50–2:55 | Back to the manager screen with the AIMO order number, then the logo. | **Closing:** "Agents that can buy, rules they can't break, and a record anyone can read. That's how Valio Aimo stays open to agents, on its own terms." | "Aimo Purchasing agent · Trusted Trade Agents" | Close |

Screen-time share: end-to-end flow 0:18–1:40 ≈ 82 s (47 %). Guardrails beats ≈ 50 s. Exceptions 18 s plus skipped reasons. Openness ≈ 34 s.

## 4. Trust/guardrails in about 20 seconds (standalone version, if you need a tighter cut)
1. **Split screen (8 s):** chef left on "Waiting for approval", manager right taps "Approve & place order". The two different logins are the visual proof of separation of duties.
2. **A refused action (6 s):** big-font terminal or Swagger. POST commit without approval gives a red problem+json response. Show the actual error `title`/`detail` the gateway returns, and check the exact text before recording.
3. **Audit (6 s):** "What happened and why" plus the "Placed by:" / "Approved by:" lines, then the JSON download.
Caption over all of it: "Agent decides inside limits. Human signs the rest."

## 5. Openness
- **Always show:** `/docs` with OpenAPI 3.1, the 13 operations, OAuth-style scopes, and RFC 9457 errors. Hold 2 s on the spec version and the scopes. Say "open, documented contract, not a proprietary format".
- **If MCP ships:** Claude Desktop (or any MCP client) runs lookup → order → pending approval. The killer frame is the manager's queue showing an order **from the external agent** with the same guardrails. Keep it to 12 s. Use a scripted butter or milk prompt and pre-test it 3 times.
- **If MCP isn't ready (alternative):** a terminal running 2–3 `curl` calls against the gateway: product search, then price & availability (structured JSON), then commit without approval being refused. Caption: "Any agent, any framework: plain HTTP + OpenAPI". **Don't** show or claim an external agent *starting* a request if that still isn't supported. Frame it as "lookup and order operations are open; MCP adapter is next".

## 6. Voice input
- Use it at most once, on the low-stakes **butter** shot (1:40–1:52). Framing: "Hands full in the kitchen? Just say it." It is quick input into the same structured request bar, not a conversation. The response is chips and an order, never chat bubbles.
- Never use voice on the main milk run (risk of misrecognition, and it reads like a chatbot). If voice misfires in more than 1 of 3 takes, drop it entirely. It adds nothing to the score.
- Don't use the words "chat" or "assistant" anywhere. Say "request", "agent", "gateway".

## 7. Weak spots to steer around

| Weak spot | How to avoid it on camera |
|---|---|
| Only 6 product families + 3 recipes ("oat milk" → cow's milk, "salmon" not found) | Type only the 3 scripted requests. No live audience prompts. If the clarifying-question card ships, you could add it as a 6 s exceptions beat ("oat milk?" → options), but only if it is reliable. |
| No real LLM (rule-based) | Never say "AI understands" or "LLM". Say "the agent reads the request into structured needs". Disclose it on the assumptions card ("LLM pluggable"). Honesty scores on openness. |
| No MCP / external agent can't start a request | Use the §5 alternative. Show only operations that work over HTTP. Put MCP under "next" unless it has shipped. |
| No signed/verifiable evidence | Don't use the words "verified" or "credential" for current features. List them as the next step. |
| "12 L milk for tomorrow" on Saturday is blocked without offering Monday | Don't use "tomorrow". Record so "Monday" resolves to Mon 16 Nov (it is shown as an assumption, which is a plus). Re-check the inferred date on recording day. |
| Price checks expire after 2 min | Do the milk run in one continuous take and approve within about 60 s. If you take a break, restart from "Find products". Make the stale-quote refusal a *feature* (1:52 beat). |
| Orders not sent to a real supplier | Say "order placed in the gateway". One line on the assumptions card: "no supplier order API in the challenge; recorded for approval, as organizers specified". |
| Pacing animations (1.5 s / 3 s) | Keep them at 1x and say they are real calls, so they read as substance, not filler. |

## 8. 30-second cut (social / first judge pass)

| Time | Screen | VO | Caption |
|---|---|---|---|
| 0:00–0:03 | Manager: "Order placed · AIMO-…" | "An agent placed this order, within rules a human set." | "Agent buys. Human signs." |
| 0:03–0:09 | Typing the milk request → understood chips (dashed date) | "A thousand litres of lactose-free milk by Monday, read into structured needs." | "Valio Aimo's own example" |
| 0:09–0:16 | Exception card → click Recommended "Valio Arki Eila — €1,150" | "Usual milk is short, so it ranks substitutes and picks the official one." | "Stock-out handled" |
| 0:16–0:22 | Split screen: "Waiting for approval" ↔ manager taps **Approve & place order** → AIMO number | "Over the €500 limit, so a manager approves. Price re-checked at commit." | "Over limit → human" |
| 0:22–0:27 | "What happened and why" scroll → flash of `/docs` OpenAPI 3.1 | "Every step logged, behind an open, documented OpenAPI gateway." | "Auditable. Open." |
| 0:27–0:30 | Logo | "Trusted trade agents, on Valio Aimo's terms." | "Aimo Purchasing agent" |
