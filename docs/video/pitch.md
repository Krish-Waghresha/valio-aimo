# Pitch — The Delusional (Krish Waghresha, Jakub Piotrowski)

**Decision:** opening slide → demo (3 moments) → closing slide. Detail slides live in the appendix for Q&A only.
**Demo moments:** ① Milk — the brief's own request, end to end (stock-out → best substitute → manager approves).
② Butter — small order the agent places alone. ③ Refusal — the agent tries to skip the manager (6 s).
Why: ① covers lookup, partial availability, good-better-best, cutoffs, approval; ② is the "within its authority" half of the brief's sentence; ③ proves the guardrail is enforced by the gateway. More scenarios cost end-to-end clarity (30 %) for at most +1 point on exceptions (15 %).
**Verified live numbers (14 Nov):** 17,546 products → 11 matches · 3 skipped (cutoff passed 2, not available 1) · Arla only 384 L for Mon 16 Nov · Switch all to Valio Arki Eila €1,150 · keep Arla + Valio €1,787.44 (+€637.44) · only Arla 384 L €1,079.04 · agent limit €500 · butter 20 kg = 1 × 20 kg Valio Eila, €42.37, placed by buyer agent · refusal: "409 · Approval required", "403 · An authenticated human is required".

---

## A. Video — hard 2:00 (voiceover 209 words ≈ 1:40 spoken; no row faster than ~130 words/min)

| Time | Screen (what to show / zoom / reveal) | Voiceover (exact) |
|---|---|---|
| **0:00–0:10** | **Opening slide.** Face bubble large. Slow zoom toward the quote. | "Soon, hotel kitchens will buy through their own AI agents. We built the open door they use — with rules Valio Aimo controls." (22) |
| **0:10–0:22** | ① Buyer screen. Paste the brief's request → **Continue** → "Reading your request" → chips. Zoom on chips; hover dashed **Mon 16 Nov**. Tick diet → **Find products**. | "This is Valio Aimo's own example: a thousand litres of lactose-free milk by Monday. The agent turns it into an order and marks what it assumed." (26) |
| **0:22–0:30** | "Working on it" at 1×. Zoom on "11 matches" and "one lookup". | "It shortlists eleven products and checks live price and stock once." (11) |
| **0:30–0:45** | Exception card. Zoom title "Only 384 L of your usual Arla…", then the 3 options; hover **Recommended €1,150** 1 s, click. | "The usual Arla milk is short — only three hundred eighty-four litres. The agent proposes Valio Aimo's official substitute: same spec, fully in stock, six hundred euros cheaper than splitting." (29) |
| **0:45–1:05** | Split screen. Left buyer "Working…" → **Waiting for approval**. Right manager: **Approve & place order** → **Yes, continue** → live steps → **Order number**. Zoom on *Requested by / Sourced by / Approved by / Placed by*. | "It's over the agent's five-hundred-euro limit, so it stops and asks the kitchen manager. One tap. Price and stock are checked again, and the order is placed — with who asked, who sourced and who approved." (37) |
| **1:05–1:15** | Scroll to **What happened and why**. Freeze on "Skipped 3 products — cutoff passed (2), not available (1)". | "Every decision is logged in plain language — including what it skipped, and why." (13) |
| **1:15–1:32** | ② New request: `20 kg butter for Friday` → Continue → tick → Find products → **Order placed · Placed by: Buyer agent · Approval: Not needed**. Speed up typing 3×. | "Under the limit, it doesn't bother anyone. Twenty kilos of butter for Friday, forty-two euros — ordered on its own, still on the record." (23) |
| **1:32–1:40** | ③ Terminal: `scripts/agent_console.py guardrails` (on a milk order still waiting). Zoom on the two red ✗ lines. | "And if the agent tries to skip the manager, or approve itself, the gateway refuses." (15) |
| **1:40–1:58** | **Closing slide.** Face bubble large. Let the three rule columns sit 4 s, then the tagline. | "What the agent may do alone, what needs a person, and what it can never do — all enforced by one open, documented gateway. Open to agents. On Valio Aimo's terms." (31) |
| 1:58–2:00 | Hold closing slide | — |

**Captions (burned in):** 0:00 "Agents buy. Rules decide." · 0:10 "Valio Aimo's own example" · 0:22 "One live lookup" · 0:30 "Stock-out → best substitute" · 0:45 "Over €500 → manager approves" · 1:05 "Every step on record" · 1:15 "Under €500 → agent orders alone" · 1:32 "The gateway says no" · 1:40 "Open to agents. On Valio Aimo's terms."

**Do not show/say:** "17,546" aloud · "budget" (say "limit") · pies · oat milk / fish / "tomorrow" · raw JSON · /docs scrolling · "LLM", "verified", "MCP" as if built.

---

## B. Live pitch (~5 min) — same 3 moments, slower, two presenters

| Time | Screen | Who | What to say |
|---|---|---|---|
| 0:00–0:40 | Opening slide | **Jakub** | "Valio Aimo asked a simple question: how can a wholesaler let *other people's* AI agents buy from it — without losing control? Here's the example from the brief: a hotel's agent needs a thousand litres of lactose-free milk by Monday. Today a buyer clicks through a webshop; spending limits live in people's heads. We built the open door agents use — with rules Valio Aimo and the buyer control." |
| 0:40–2:30 | ① Milk demo (Jakub drives buyer, Krish drives manager) | **Jakub** → **Krish** | Jakub: "I'll paste the brief word for word… it understood: a thousand litres, lactose-free, *Monday* — dashed because it inferred which Monday. One live lookup over the shortlist… and here's reality: the hotel's usual Arla milk has only 384 litres. The agent doesn't guess — it ranks options: Valio Aimo's official substitute, same spec, fully in stock, €1,150; keep Arla and split, €637 more; or deliver short. I take the recommendation." — Krish: "It's over the agent's €500 limit, so it's waiting for me. I see why, I approve — and before the order is placed the gateway checks price and stock again. Order number, and the record shows who asked, which agent sourced it, who approved." |
| 2:30–3:10 | ② Butter | **Jakub** | "Small things shouldn't need a manager. Twenty kilos of butter for Friday, €42 — the agent orders on its own. Same rules, same record." |
| 3:10–3:40 | ③ Terminal refusal | **Krish** | "Now the agent misbehaves: it tries to place the milk order without approval — refused. It tries to approve itself — refused. The rules live in the gateway, not in the agent's good manners." |
| 3:40–4:10 | Milk order → **What happened and why** → **Compare alternatives** | **Krish** | "For the buyer and for Valio Aimo: every decision in plain language — eleven candidates, three skipped because the cutoff had passed or nothing was available, and why this product won." |
| 4:10–4:50 | Closing slide | **Jakub** | "So: what the agent decides alone, what needs a person, what it can never do — enforced by one open, documented gateway on live challenge data. Next: an MCP interface so any agent can plug in, signed proof of price and stock, and the real order API. Open to agents — on Valio Aimo's terms." |
| 4:50–5:00 | Closing slide | both | "Thank you — we're The Delusional." |

**If the live API fails:** play the video from 0:10 to 1:40 and narrate over it.

### Q&A — one-line answers (appendix slides ready: Problem, How it works, Rules, Exceptions, Trust & audit, Open by design)
- **Where's the AI?** "The agent proposes; the gateway enforces. Understanding and ranking are deterministic today so they're auditable — a language model plugs in behind the same tools and can never change prices, limits or approvals."
- **Can a real external agent use it?** "Lookup and the guardrails are on the open API today — you saw the terminal. Agent-created requests and MCP are the next step."
- **Why recommend switching from Arla?** "Same lactose-free 1 L spec, listed by Valio Aimo as the official substitute, 100 % delivered in full, €637 cheaper — and the buyer keeps Arla with one tap."
- **What if the price changes after approval?** "Approval binds to one exact priced basket; at order time price and stock are re-checked; any change needs a new approval."
- **What's mocked?** "Orders are created for approval, not transmitted — the challenge has no order API. Prices and stock are the live challenge APIs."
- **What if the usual product is unreliable?** "If the usual product's delivered-in-full rate is below 90 %, the agent asks before switching — e.g. the usual yogurt at 50 %."
