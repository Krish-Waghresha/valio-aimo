# Demo video production notes (researched 2026-11-14)

## 1. Junction submission (Junction 2026 runs Nov 13-15, Espoo, per hackernoon listing)
- **Submission form (Junction Platform, junction.app).** The default fields in the live platform's JS bundle are: Project Name (required, max 30 chars), Punchline (required, max 200 chars), Description (required), Challenge selection (required), plus optional Demo URL (live app), Source Code link, **Video URL ("YouTube, Loom, etc.")**, Other link, and Presentation upload (PDF/PPTX/KEY/ODP). By default the video is a **link, not an upload**, and **optional**. UNCERTAIN: individual events or challenge partners can make it mandatory, so check the event page and your challenge brief.
- **Length.** UNCERTAIN. No official Junction max length was found (the Notion guide pages are JS-only and could not be read). A partner blog for the Miro x Junction 2024 challenge listed "short demo video" + source code + deployment URL as required. The industry norm is 2-3 min (Devpost: "under three minutes"). **Aim for 2:00-2:30.** Set the YouTube video to Unlisted (not Private) or use a public Loom.
- **Judging.** Challenge partners pick their own challenge winners from the submissions. The video and description are what reviewers see first. Historically, finalists (one per track/challenge) then pitched live on stage on Sunday, about 5 min each (2016/2017 Devpost pages; Wikipedia describes a two-stage Gavel then expert-panel process). Some years also used peer review. In 2024, finalists could pitch on stage or show a recorded video pitch. UNCERTAIN for 2026.
- **Deadline.** Typically **Sunday morning**. Confirm the exact time on the event page or in the guidebook. Submit an early draft and edit it later.

## 2. Fastest polished recording on macOS
- **Best pick: Screen Studio** (Mac only). It gives automatic zoom on clicks, smoothed and enlarged cursor, and up to 4K60 export (about $29/mo monthly; pricing sources conflict). The alternatives:
  - **CleanShot X** records cleanly with click highlighting but no auto-zoom.
  - **Loom** gives an instant shareable link and a camera bubble, but no real zoom.
  - **Cmd+Shift+5 / QuickTime** are free, plain, and have no zoom.
  - **OBS** is flexible for side-by-side scenes but slow to set up.
- **Setup.** Record a 1920x1080 window (or a 1440x900 display scaled up), with Chrome zoom at 110-125% so text reads on a laptop. Use a fresh Chrome profile with no extensions or bookmarks bar (Cmd+Shift+B), and hide the dock. Use Guest or a new profile for the second role.
- **Two roles (buyer and manager).** Prefer **switching** between two full-size windows, with a one-line caption at each switch ("Manager view"). Side-by-side halves the readable size. Use it only for one "approval appears instantly" moment. For that shot, use Screen Studio on two windows tiled, or an OBS two-source scene.
- **Voiceover.** Record **separately**, after the cut, from a tight script of about 130 words per minute (about 300 words for 2:20). Live narration adds stumbles.
- **ElevenLabs.** The free plan is **non-commercial and requires attribution**. Paid plans (Starter, about $5-6) include a commercial license. A hackathon demo is arguably non-commercial, but $5 removes doubt. UNCERTAIN: no Junction rule on AI voices was found. Judges rarely mind a clean AI voice for a video, but a human voice reads as more authentic, and a live pitch must be human anyway. A good USB/AirPods recording in a quiet room is fine.
- **Captions.** Burn them in, because many judges watch muted. CapCut and Descript auto-caption in one click.
- **Music.** Keep it at about -25 to -30 dB under the voice (10-15% volume), or skip it.
- **Time limit.** Cut dead time such as loading and typing (speed up 2-4x), and start with the problem in the first 10 seconds.
- **Editing.**
  - **CapCut** (fastest: captions, speed ramps, music).
  - **Descript** (edit by transcript, good for a voiceover-first workflow).
  - **iMovie** (simple, no auto-captions).
  - **DaVinci Resolve** (powerful, but too slow for a hackathon).

## 3. Recording checklist
- [ ] Reset and seed a **fresh demo DB** with realistic data and no test junk.
- [ ] **Pre-type requests** in a text file and paste them, or use the snippet tool.
- [ ] Log the **second browser profile** (manager) in, on the right page.
- [ ] Turn on **Do Not Disturb/Focus**. Quit Slack, Mail, and Messages. Hide desktop icons and the menu bar clock if needed.
- [ ] Use a clean Chrome profile, bookmarks hidden, zoom set, no other tabs.
- [ ] Make sure the network/LLM is warm. Do a cache-warming run so the agent responds fast, and keep a fallback if the API is slow.
- [ ] Do a **rehearsal run** of the full flow and time it.
- [ ] Record **2+ takes**, plus a **backup take** of the key moment. Save the raw files.
- [ ] Write the script, record the voiceover, then cut to the voice.
- [ ] Add burned-in captions and a title card plus an end card (name, one-liner, repo link).
- [ ] **Export:** MP4 H.264, 1080p, 30 or 60 fps, about 10-16 Mbps, AAC 48 kHz. Upload as YouTube Unlisted, test in an incognito window, and paste the link into the submission early.

## Sources
- Junction Platform form fields: the live JS bundle of junction.app/hackjunction.app (default field definitions)
- https://hackjunction.app/
- https://junctionhq.notion.site/Project-Submission-fff59a11813781a38121ccc1a3fb14d4 (not readable)
- https://junctionhq.notion.site/Pitching-21bfe4c81be94571a9cda396a3897a9f (search snippet: 2024 stage or video pitch)
- https://www.appfox.io/blog/appfox-attends-miro-junction-hackathon/
- https://en.wikipedia.org/wiki/Junction_(hackathon)
- https://hackernoon.com/12-hackathons-worth-your-fall-and-winter (Junction 2026 dates)
- https://info.devpost.com/blog/6-tips-for-making-a-hackathon-demo-video
- https://help.elevenlabs.io/hc/en-us/articles/13313564601361
- https://screen.studio/ ; https://toolquestor.com/tool/screen-studio
