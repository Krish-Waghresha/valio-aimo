# Original demo film pipeline

[Watch the latest published demo](https://youtu.be/CB_NcgdgK5k).

## Fresh v4 narration

`video/build/final-v4.mp4` is a fresh reading of the **same original script** by
the two saved team voices. The original picture, transitions, music and
118.600-second running time stay unchanged; the earlier versions are retained.

The effective ElevenLabs request uses `eleven_v4`, stability **0.45**,
similarity **0.75**, and `mp3_44100_192`. Each line includes the adjacent script
lines as context, including when the speaker changes. Literal `[pause]` hints
become `...` in the request only; `config.json` is not edited. No extra delivery
tags are added. [V4](https://elevenlabs.io/docs/overview/capabilities/text-to-speech/eleven-v4)
does not support `style` or `use_speaker_boost`, so those requested controls are
explicitly omitted rather than advertised as applied.

With the same ignored `.env.cinematic` described below:

```sh
uv run --no-sync python video/cinematic/revoice.py prepare
uv run --no-sync --env-file .env.cinematic python video/cinematic/revoice_v4.py voices --generate
uv run --no-sync --env-file .env.cinematic python video/cinematic/revoice_v4.py mix
uv run --no-sync --env-file .env.cinematic python video/cinematic/revoice_v4.py export
```

Only `voices --generate` can make paid requests; matching takes are reused and
failed/unknown attempts are never automatically retried. `inspect` checks the
physical 192 kbps MP3s. `fit --only s01 s02` can check selected lines locally.
Fresh raw takes remain immutable in `video/build/cinematic/voices/`; fitted
stems, the mix and verification report live in `video/build/cinematic/original-v4/`.

New performances can be longer than the locked scenes. The fitter first reduces
only measured quiet pauses, checks every removed sample against a -55 dBFS limit,
and preserves pause edges and complete spoken material. Remaining differences use
pitch-preserving tempo adjustment, capped at 1.30x. This includes the short, fast
original lines: preserving their scene timing can require a faster delivery than
the unedited v4 take. Word timings, pause cuts and each line's actual tempo are
recorded; no original narration is mixed underneath. Export copies the original
video packets and refuses any picture or timestamp change.

## Voice-only edition

`video/build/final-conversational.mp4` keeps the original **118.600-second,
1080p30 picture** and all 21 original narration lines. Only the two speakers are
replaced with the team's trained voices. It does not use the rewritten cinematic
script, new slides, camera moves or transitions.

[ElevenLabs Voice Changer](https://elevenlabs.io/docs/overview/capabilities/voice-changer)
transfers the original isolated performances to the supplied voices, preserving
their words and pacing. This edition uses `eleven_multilingual_sts_v2`, stability
0.5, similarity 0.75, and style exaggeration **0**: no excited/pitch delivery tags.

Use the ignored, mode-600 `.env.cinematic` containing `ELEVENLABS_API_KEY`,
`ELEVENLABS_VOICE_ID` (Krish) and `ELEVENLABS_VOICE_JAKUB` (Jakub):

```sh
uv run --no-sync python video/cinematic/revoice.py prepare
uv run --no-sync --env-file .env.cinematic python video/cinematic/revoice.py voices --generate
uv run --no-sync --env-file .env.cinematic python video/cinematic/revoice.py mix
uv run --no-sync --env-file .env.cinematic python video/cinematic/revoice.py export
```

Only `voices --generate` can spend; omit `--generate` to check the conversion
caches. `--only s01 s02` selects original lines without creating disposable takes.
Attempts are journaled and never automatically retried. Conversions stay under
the ignored `video/build/cinematic/original-revoice/`.

The original narration stems are the conversion inputs, not the mixed movie.
The original score and its ducking are reconstructed separately; the reconstructed
original mix must match the retained original PCM before synthesis. Small timing
differences can receive at most 5% pitch-preserving correction, with a silence
flush; complete speech is never trimmed to force a fit.

Export copies the original video stream instead of rendering frames. Every
encoded video packet and timestamp must remain identical. The old narration is
not mixed underneath the new voices, and `final.mp4` is never overwritten.
Do not run `make.sh` or `build.py` for this voice-only edition.

## Other cuts

For the separate 118-second revision with the team's trained voices, see the
[cinematic cut pipeline](cinematic/README.md). It writes
`video/build/final-cinematic.mp4` and leaves the original film untouched.

## Earlier production pipeline

The production notes below describe the earlier pipeline.

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
| `config.json` | The script: 21 lines, speaker per line, visual per line (scene or app shot), timing knobs |
| `voice.py` | Text → speech + word timings (cached by text/voice/settings) |
| `music.py` | 2-minute score (cached; `--force` to regenerate) |
| `record.py` | Operates the real app (chef, manager, chef) on the narration's schedule with a visible cursor; Chrome screencast at 1920×1080 resampled to 30 fps; captures the real terminal output |
| `film.html` | The renderer: scenes (hook, history, AI agent, question, title, architecture, terminal, rules, end), camera moves over the screenshots, crossfades, captions with speaker flags |
| `build.py` | Timeline from voice lengths → frame-by-frame render (30 fps) → loudness-matched voice mix + ducked music → `final.mp4`; refuses anything over the limit |

**Edit loop:** change a line in `config.json` → `video/make.sh` (only that line is re-voiced).
Camera plans per app shot are in `film.html` → `SHOTS` (image, element to frame, zoom or "fit", weight).

**Fresh capture workspace:** `uv run aimo-gateway init --mode live --database data/gateway/video-draft/gateway.sqlite --origin http://127.0.0.1:8004`,
`policy ... --autonomous-limit 50000 --order-limit 500000 --manager-approval-limit 500000`, then `serve --workspace` on port 8004.
