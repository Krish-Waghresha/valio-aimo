# Demo video — final script (hard limit 2:00, target 1:55)

Format: screen recording + separate voiceover + round face-cam bubble.
Voiceover budget: ~125 words/minute → **≤ 230 words total** (this script: 210 words ≈ 1:41 spoken, leaving pauses). No row faster than ~140 words/minute.
One story only: the brief's own request. One contrast. One guardrail moment. No pies, no feature tour.

| Time | Screen | Face bubble | Voiceover (exact words) | Caption (burned in) |
|---|---|---|---|---|
| 0:00–0:10 | **Slide 1** – Title: "Trusted Trade Agents" + the brief's quote "1,000 litres of lactose-free milk by Monday" | Large, centre-right | "Hotel kitchens will soon buy through their own AI agents. Valio Aimo needs one open door for them — with rules it controls." (21) | Agents buy. Rules decide. |
| 0:10–0:20 | **Slide 2** – Diagram: Hotel's agent → Aimo gateway (open API) → catalog · live price · stock. Manager icon on "approve". Three boxes: Alone ≤ €500 · Needs manager > €500 · Never: self-approve, stale price, unsafe allergen | Small, bottom-left | "The agent orders alone up to five hundred euros. Above that, a manager signs. Some things it can never do." (20) | What the agent may decide |
| 0:20–0:30 | **Outside agent** (MCP client / terminal) sends the request; structured products, prices, stock come back | Small | "Here the hotel's own agent sends Valio Aimo's example request through our open interface." (14) | The hotel's agent, not our website |
| 0:30–0:40 | Workspace: request card with chips, "Mon 16 Nov" dashed → "Working on it": 17,546 products → 11 matches → live price & stock | Small | "It reads the need — a thousand litres, lactose-free, Monday — and marks what it assumed. Then one live price and stock check." (22) | Understood · assumptions marked |
| 0:40–0:55 | Exception card "Only 384 L of your usual Arla…" → click **Recommended: Switch all 1,000 L to Valio Arki Eila — €1,150** | Small | "The usual milk is short: only three hundred eighty-four litres. The agent proposes Valio Aimo's official substitute — same spec, fully in stock, and six hundred euros cheaper than splitting." (29) | Stock-out → best substitute |
| 0:55–1:15 | Split screen: buyer "Waiting for approval" ↔ manager taps **Approve & place order** → "Final price & stock check → order placed" → AIMO-xxxx | Small | "It costs eleven hundred fifty euros — over the agent's limit — so it stops and asks the kitchen manager. One tap. Price and stock are checked again, then the order is placed." (32) | Over limit → human approves |
| 1:15–1:25 | "20 kg butter for Friday" → order placed, **Placed by: Buyer agent** | Small | "Under the limit, it simply orders — like this butter." (9) | Under limit → automatic |
| 1:25–1:35 | Terminal/caption pair: agent tries to place the order without approval → `APPROVAL_REQUIRED`; tries to approve itself → `An authenticated human is required` | Small | "And when the agent tries to skip the manager, or approve itself, the gateway refuses." (15) | The gateway says no |
| 1:35–1:45 | "What happened and why" + Compare alternatives table (freeze, zoom on 3 lines) | Small | "Every decision is written down in plain language — what was skipped and why — for the buyer and for Valio Aimo." (21) | Every step on record |
| 1:45–1:55 | **Slide 3** – "Open by design": OpenAPI 3.1 · MCP · live challenge data · Next: signed price & stock proof, real order API | Large again | "Built on open standards and live challenge data. Next: signed price and stock proof. Open to agents — on Valio Aimo's terms." (22) | Open to agents. On Valio's terms. |
| 1:55–2:00 | End card: team name · repo link | Off | — | — |

## Scenarios (3, no more)
1. **Hero – brief's milk request** (partial stock → substitute → manager approval). Covers end-to-end 30 %, user need 20 %, exceptions 15 %.
2. **Contrast – butter under limit, ordered autonomously.** Covers autonomy 20 %.
3. **Guardrail – refused skip/self-approval.** Covers controls 20 %.
Openness 15 % = slide 2 + outside-agent shot + slide 3.

## Slides (3, simple, Aimo teal/lime)
1. Title + the brief's quote. 2. Diagram + the three rule boxes (Alone / Needs manager / Never). 3. Open by design + next steps.
No strategy deck in the video — the strategy *is* slide 2. Put deeper material (market, competitors, trust protocol) in the submission description / PDF.

## Dependency
Shot 0:20–0:30 needs an outside agent to send the request (not possible today: requests are human-only).
**Fallback if not built:** show a terminal where the agent searches the catalog (`GET /v1/products`) and caption "Any agent, plain HTTP"; change the line to "Any agent can query the same open interface." Never imply the website *is* the external agent.

## Recording plan
- Record screen in Screen Studio (camera bubble on, circle; mic off) or QuickTime + separate webcam clip.
- Record voiceover separately afterwards against this script (one take per row), face cam at the same time.
- Edit in CapCut: cut video to voice, speed up waits 2–4×, burn captions, music off or −28 dB.
- Fresh database (`scripts/demo_reset.sh`), manager in a second Chrome profile, approve within 60 s of the check.
- Export 1080p MP4, check length ≤ 2:00 in the player, upload YouTube Unlisted.
