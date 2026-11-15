# Demo film

The separate [cinematic cut pipeline](cinematic/README.md) targets **118 seconds at 1080p60**,
using the team's two trained voices and an original stereo score. It writes
`video/build/final-cinematic.mp4` without replacing the published cut below.

[Watch the public demo](https://www.youtube.com/watch?v=BWGWDc29ZfQ).
The locally inspected cut is **118.6 seconds, 1920×1080, about 19 MB**.
It combines actual app footage and gateway replies with rendered titles, transitions and generated
ElevenLabs narration/music. Challenge price/stock services are synthetic; orders are local mock records,
not supplier orders.

`config.json` contains 21 narration segments and a 120-second limit. Source wording now identifies mock
orders; the published cut and previously generated media remain unchanged. Original production sources
are preserved on the archive branch. Generated files in `video/build/` are ignored, not clean-clone inputs.

## Rendering existing caches

```sh
uv run --no-sync python video/build.py --preview  # video/build/preview.jpg
uv run --no-sync python video/build.py            # video/build/final.mp4
```

Both commands require cached audio metadata, recordings and `terminal.json`, plus Playwright Chromium
and FFmpeg/ffprobe. The full render also needs cached speech and music. They reuse cached narration,
which may predate the source corrections; neither bootstraps a clean-clone offline build.

## Regeneration can incur charges

`video/make.sh` runs `voice.py` (key required even with cached speech) and `music.py`, then records missing
captures or re-records with `--record`. Changed/uncached narration and missing music use **paid ElevenLabs
APIs**; `music.py --force` also incurs generation charges. Do not run these unintentionally.
`ELEVENLABS_API_KEY` comes from the environment or a local untracked `.env`, not the challenge brief.
Never copy or commit secrets.

Recording requires an already-running, disposable local workspace. Defaults:
`http://127.0.0.1:8004` and `data/gateway/video-draft/credentials.json`, overridden with
`AIMO_URL` and `AIMO_CREDENTIALS`. Recording creates demo jobs and mock orders.
