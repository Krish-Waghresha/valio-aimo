# Demo film pipeline (hard limit 2:00 — current cut 1:44)

Style borrowed from Junction's "European Tech Renaissance" film: a hook, kinetic typography synced to the
voice, a "the center is moving" through-line, fast but smooth pacing. Everything is real: the demo is a continuous,
narration-timed screen recording of the running product on live challenge data; the terminal shows the gateway's real replies.

**Voices (ElevenLabs, two speakers):** Krish 🇮🇳 = library voice "Aahir – Expressive and Lively" (young, high-energy,
Indian-accented English), Jakub 🇵🇱 = "Szymon" (young, Polish-accented English). Speed 1.12 (Krish) and 1.10 (Jakub). Every line is
loudness-matched to -16 LUFS so both voices are equally loud. Music: ElevenLabs Music, ducked under the voices.
Key: `ELEVENLABS_API_KEY` in the untracked `.env`. All generated files live in `video/build/` (git-ignored).

```sh
video/make.sh              # build video/build/final.mp4 (cached voices/music/captures)
video/make.sh --record     # re-record the app first (fresh workspace on :8004, see below)
uv run python video/build.py --preview   # fast contact sheet: video/build/preview.jpg
```

| File | Role |
|---|---|
| `config.json` | The script: 18 lines, speaker per line, visual per line (scene or app shot), timing knobs |
| `voice.py` | Text → speech + word timings (cached by text/voice/settings) |
| `music.py` | 2-minute score (cached; `--force` to regenerate) |
| `record.py` | Operates the real app (chef, manager, chef) on the narration's schedule with a visible cursor; Chrome screencast at 1920×1080 resampled to 30 fps; captures the real terminal output |
| `film.html` | The renderer: scenes (hook, history, AI agent, question, title, architecture, terminal, rules, end), camera moves over the screenshots, crossfades, captions with speaker flags |
| `build.py` | Timeline from voice lengths → frame-by-frame render (30 fps) → loudness-matched voice mix + ducked music → `final.mp4`; refuses anything over the limit |

**Edit loop:** change a line in `config.json` → `video/make.sh` (only that line is re-voiced).
Camera plans per app shot are in `film.html` → `SHOTS` (image, element to frame, zoom or "fit", weight).

**Fresh capture workspace:** `uv run aimo-gateway init --mode live --database data/gateway/video-draft/gateway.sqlite --origin http://127.0.0.1:8004`,
`policy ... --autonomous-limit 50000 --order-limit 500000 --manager-approval-limit 500000`, then `serve --workspace` on port 8004.
