# Judge critique: "Aimo Purchasing agent" storyboard

## 1. Scores (based only on what the video would show)

| Criterion | Weight | Score | Why |
|---|---|---|---|
| Working end-to-end demo | 30 | 8 | One continuous request → lookup → stock-out → approval → order number, with real data. Loses points because a person types into a web page. It looks like a webshop with automation, not an agent calling an interface. |
| Solving the user need | 20 | 8 | The brief's exact request, assumptions shown, official substitute. "Budget = your per-order limit" is odd: the hotel never gave a budget. |
| Autonomy & controls | 20 | 8 | Split-screen approval, butter auto-order and refused actions are strong. The rules flash past as a 7-item card, so I never see the full matrix of what the agent may and may not do. |
| Exceptions | 15 | 7 | The stock-out with three ranked options is good. Delivery constraints (cutoff passed) appear only as a text line. Allergen and preference limits are not shown. |
| Openness / path to production | 15 | 5 (7 with MCP) | Scrolling a /docs page proves very little. Without an outside agent ordering, "external-agent-ready" is only claimed. The honest assumptions card helps. |
| **Weighted total** | | **74/100 (≈79 with MCP shot)** | Top-10 territory. Not yet top-3. |

## 2. Moments that confuse, bore or make me skeptical
- **Shot 0:00–0:04:** "AIMO-XXXXXXXX" placeholder. Make sure the real number is on screen. A shot that cuts in 4 s gives me no time to read it.
- **Shot 0:10–0:18:** the diagram says "Buyer agent", but the next 80 s show a chef typing into *your* UI. **Who is the agent?** It reads as "Valio's website with a smart search box". This is the biggest problem.
- **Shot 0:18–0:28:** "the budget is your per-order limit" is confusing. Is it a budget or an authority limit? Pick one word.
- **Shot 0:28–0:38:** "17,546 products searched" is a vanity number. "These are the real backend calls" is a claim with no proof on screen.
- **Shot 0:38–0:56:** 18 s of reading options aloud is too long, and "€637 more" is spoken before I've seen the price. Lead with the outcome.
- **Shot 1:22–1:40:** scrolling an audit page is boring and the text is unreadable at video speed. Freeze on 2–3 lines.
- **Shot 1:52–2:04:** "RFC 9457", "problem JSON", "idempotent", "forged fields", "adversarial tester" are jargon or unproven. A red JSON blob means nothing to a commercial judge. Show it as a plain sentence: "Refused: needs manager approval."
- **Shot 2:04–2:16:** the wedding-pie montage at 2 s per cut is a second story. It dilutes the one idea, and "savory pies" for a hotel chain is off-brief. Cut it.
- **Shot 2:16–2:38:** "13 operations, scopes" is a dev-tool scroll with no payoff. The "If MCP is built / if not" branch shows the team is undecided. Commit to one.
- **Shot 2:38–2:50:** "verifiable credentials" appears only as a future item. That is fine, but there is no trust moment in the present.
- **General:** "Here's what I understood" and "Working on it" are first-person agent voice. That edges toward a chatbot feel, so keep it to UI labels and don't read them aloud.

## 3. Hook, story, roles
- **Hook:** good idea ("placed by an agent, approved by a human"), but at 4 s with a placeholder it doesn't land. I'd care by 0:10, not because of the problem framing, which arrives late and generically.
- **Buyer need solved?** Yes, clearly: 1,000 L lactose-free milk, Monday, ordered. This is the strongest part.
- **Who is the agent? External-ready?** Not clear. The hotel chain's *own* agent never appears. Without an outside client ordering through the same rules, the challenge's central question ("expose Valio Aimo to *external* agents") is answered only by a diagram.

## 4. Missing for a top-3 entry
1. **An outside agent ordering through the open interface**, ideally the hotel's request sent by a different client (MCP or a scripted agent using curl), landing in the same manager queue. This is the decisive shot.
2. **A trust moment:** what the agent can rely on (price valid until 14:02, stock as of now, origin label from the catalog), even if it is unsigned today. Show the "quote valid 2 min" countdown as the trust contract.
3. **A visible guardrail matrix:** a single table of agent alone / needs human / never, with thresholds (€500, substitutions outside spec, allergens).
4. **A numbers slide:** time from request to order vs today's process, clicks saved, % of orders auto-approved. Even estimates, labelled as such.
5. **The Valio Aimo view of the audit:** the brief asks for both buyer and wholesaler.

## 5. Revised shot list (2:25)

| Time | Screen | Voiceover | Caption |
|---|---|---|---|
| 0:00–0:07 | Manager phone: real order number, "Placed by: Hotel buyer agent · Approved by: Kitchen manager" | "A hotel's purchasing agent just bought 1,000 litres of milk from Valio Aimo. It wasn't allowed to do it alone, so a human signed." | Agent buys. Human signs. |
| 0:07–0:17 | Simple diagram: Hotel's agent → Valio Aimo open gateway → catalog, price, stock. Manager icon on the approve arrow | "Soon kitchens will buy through their own AI agents. Valio Aimo needs one open door with rules it controls." | One open door. Valio's rules. |
| 0:17–0:30 | Outside agent (MCP client or terminal) sends the brief's milk request. Structured product, price and stock results return | "Here's the hotel's own agent, not our website, asking for Valio Aimo's example request." | The hotel's agent, not our UI |
| 0:30–0:40 | Same request in the workspace: chips, dashed "Mon 16 Nov" | "Our workspace shows the same request so people can follow it. Anything assumed is marked, like which Monday." | Assumptions marked |
| 0:40–0:55 | Exception card, cursor on Recommended Valio Arki Eila €1,150 | "The usual milk is short. Only 384 litres for Monday. The agent picks Valio's official lactose-free substitute, fully in stock. Splitting the order would cost €637 more." | Stock-out → best substitute |
| 0:55–1:15 | Split screen: buyer "Waiting for approval" ↔ manager reads reason, taps Approve → price re-checked → order number | "€1,150 is over this agent's €500 limit, so it stops. The manager sees why and approves. Price and stock are checked again before the order is placed." | Over limit → human approves |
| 1:15–1:25 | Butter request, auto-placed, "Placed by: Buyer agent" | "Under the limit, it just orders. Still on the record." | Under limit → automatic |
| 1:25–1:40 | Guardrail matrix card: Alone / Needs human / Never, with thresholds | "These are the rules: what the agent does alone, what needs a person, and what it can never do." | Clear rules, set by humans |
| 1:40–1:52 | Agent tries to commit without approval, then with an expired price. Plain red banners | "We tried to make it cheat. No approval: refused. Price older than two minutes: refused." | The gateway says no |
| 1:52–2:04 | Audit: freeze on 3 plain lines, then a "Valio Aimo view" toggle and the JSON download | "Every decision is written in plain language, for the buyer and for Valio Aimo, plus a machine-readable record." | Every step on record |
| 2:04–2:14 | Impact card: request to order in about 1 minute vs a manual estimate, X % auto-approved (labelled estimate) | "A minute instead of a phone call and a catalog hunt, with the risky parts still in human hands." | Minutes, not hours |
| 2:14–2:22 | Assumptions & next steps: live challenge data · rule-based reading (AI pluggable) · next: signed price and stock proof, real order API | "Real data, real approval flow. Next: signed proof of price and stock, and a live order connection." | Honest scope. Clear next steps. |
| 2:22–2:25 | Logo | "Open to agents, on Valio Aimo's terms." | Trusted Trade Agents |

If MCP isn't shipped, use the terminal version of 0:17–0:30 and caption it "Any agent, plain HTTP". Never imply the workspace *is* the external agent.
