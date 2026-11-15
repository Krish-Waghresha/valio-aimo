# Presentation guide — The Delusional (Krish Waghresha, Jakub Piotrowski)

Two deliverables: **(A) the 2:00 video** (hard limit) and **(B) the live final pitch** (if we're picked).
Slides: `docs/presentation/index.html` — open in Chrome, press **F** for fullscreen, **→ / Space** next (reveals bullets one by one), **←** back. `#5` in the URL jumps to slide 5. Append `?all` to show slides fully revealed (for screenshots/PDF: Cmd+P → Save as PDF, landscape, no margins).

---

## 0. Pre-flight (15 min before any recording or pitch)

1. `scripts/demo_reset.sh` → fresh database, Approvals (0) / Orders (0).
2. Chrome profile **"Buyer"**: http://127.0.0.1:8003 → sign in as `chef`. Profile **"Manager"**: sign in as `manager`.
   Both: zoom **125 %**, bookmarks bar hidden (Cmd+Shift+B), one tab, window 1920×1080.
3. Terminal: font size 20, dark theme, window ~1100×500, `cd` to repo, clear screen.
4. Do Not Disturb on; Slack/Mail/Messages quit; dock hidden.
5. Rehearse once (creates orders) → run `scripts/demo_reset.sh` again → sign in again.
6. Paste-ready text file:
   - `I need 1,000 litres of lactose-free milk by Monday. Find an option that meets our requirements based on price and availability.`
   - `20 kg butter for Friday`

**Never type:** "tomorrow", fish, oat milk, anything outside milk/cream/butter/wheat flour/yogurt/eggs/pies.
**Timing rule:** the manager must approve within **~60 s** of the price check (quotes expire after 2 min; the app re-checks, but keep it clean).

---

## A. The 2:00 video — exact shot list

Record each shot separately in Screen Studio (camera bubble OFF while recording screen); record voiceover + face afterwards (script: `docs/video/final-2min-script.md`). Speed up any waiting 2–4×, but **keep the "Working on it" steps readable (1×)**.

| # | Time | Screen & clicks | Zoom / reveal |
|---|---|---|---|
| 1 | 0:00–0:10 | Slide 1 (title + brief quote) | Face bubble large. No zoom. |
| 2 | 0:10–0:20 | Slide 4 "What the agent may decide" — press → three times to reveal Alone / Needs a human / Never | Face bubble small. Hold each card ~2 s. |
| 3 | 0:20–0:30 | Terminal: `uv run python scripts/agent_console.py search "milk drink 1 l lactose free"` | Zoom on the `GET /v1/products` line, then on the list of Valio lactose-free milks. Caption: "The hotel's agent, plain HTTP". |
| 4 | 0:30–0:40 | Buyer: click into "What do you need?", paste the milk request, **Continue** → "Reading your request" → chips | Zoom on the chips; hover the dashed **Delivery Mon 16 Nov** chip ("assumed"). Tick **Diet and allergies above are correct** → **Find products**. Let "Working on it" play at 1× and zoom on "17,546 products → 11 matches". |
| 5 | 0:40–0:55 | Exception card appears | Zoom on the title "Only 384 L of your usual Arla…", then on the three options. Hover **Recommended: Switch all 1,000 L to Valio Arki Eila — €1,150** for 1 s, click. |
| 6 | 0:55–1:15 | Split screen (Buyer left, Manager right). Buyer shows "Working…" → **Waiting for approval**. Manager: click **Approvals (1)** → order → **Approve & place order** → **Yes, continue** → live steps → **Order number AIMO-…** | Zoom on manager's side panel: "Over the buyer's €500 limit…", then on the steps, then on Order number / Requested by / Sourced by / **Approved by Kitchen manager**. |
| 7 | 1:15–1:25 | Buyer: **← New request**, paste `20 kg butter for Friday` → Continue → tick diet → Find products | Zoom on side panel: **Placed by: Buyer agent · Approval: Not needed (within limit)**. |
| 8 | 1:25–1:35 | Before shot 6 is approved (record it right after shot 5 on a second, waiting order) — Terminal: `uv run python scripts/agent_console.py guardrails` | Zoom on the two red lines: `✗ 409 · Approval required` and `✗ 403 · An authenticated human is required`. Must run within 2 min of the order's price check. |
| 9 | 1:35–1:45 | Milk order page, scroll to **What happened and why** → open **Compare alternatives** | Freeze on: "Skipped 3 products — cutoff passed (2), not available (1)", then the table rows **In basket** / **Cutoff passed**. |
| 10 | 1:45–1:55 | Slide 8 "Open by design" (press → to reveal next steps) | Face bubble large again. |
| 11 | 1:55–2:00 | Slide 9 end card | No voice. |

**Recording order (to beat the 2-minute quote expiry):** create milk order → shot 4–5 → immediately run terminal shot 8 on it (Buyer waiting) → then shot 6 approval. Butter (shot 7) any time.

---

## B. Live final pitch (5 min stage format, if selected)

| Time | Slide / screen | Who | What to say (key line) |
|---|---|---|---|
| 0:00–0:30 | Slide 1 | Jakub | "Valio Aimo's own example: 1,000 litres of lactose-free milk by Monday — sent by a hotel's agent, not a person." |
| 0:30–1:00 | Slide 2 | Jakub | "Agents will buy. Today the only rules are in people's heads. If Valio doesn't define the door, someone else's platform will." |
| 1:00–1:40 | Slides 3 → 4 | Krish | "One gateway. The agent orders alone up to €500, a human signs above, and some things it can never do — enforced by the gateway, not by the agent's good behaviour." |
| 1:40–3:40 | Slide 6 → **live demo** (shots 3–9 above, unscripted pace) | Jakub drives buyer, Krish drives manager | Narrate outcomes, not clicks: "It found the shortage, proposed the official substitute, €637 cheaper than splitting… over the limit, so it stops… one tap, price re-checked, ordered." |
| 3:40–4:20 | Slide 5 (exception) + slide 7 (trust & audit) | Krish | "Good-better-best on live data. Every shortcut refused, every decision in plain language for buyer and Valio." |
| 4:20–4:50 | Slide 8 | Krish | "Open standards, honest assumptions, clear next steps: MCP, signed price & stock proof, the real order API." |
| 4:50–5:00 | Slide 9 | both | "Open to agents — on Valio Aimo's terms." |

**Backup:** if Wi-Fi/API fails, play the recorded video from 0:20 to 1:45 instead of the live demo.

### Likely judge questions — short answers
- **"Where is the AI?"** — Understanding and sourcing are deterministic today on purpose: the agent proposes, the gateway enforces. An LLM plugs in behind the same tools and can never change prices, limits or approvals.
- **"Can a real external agent use it?"** — Yes for lookup today (open OpenAPI, bearer token, shown in the terminal); creating requests is human-only in v1 by design; next step is delegated agent requests + MCP.
- **"Why switch from Arla?"** — Same lactose-free 1 L spec, Valio Aimo lists it as the official substitute, 100 % delivered in full, €637 cheaper. The buyer can still keep Arla with one tap.
- **"What if prices change after approval?"** — Approval is bound to one exact priced basket; at order time price and stock are re-checked; any change needs a new approval.
- **"What's not real?"** — Orders are recorded for approval, not sent to a supplier (no order API in the challenge). Data is the synthetic challenge catalog and live mock APIs.
