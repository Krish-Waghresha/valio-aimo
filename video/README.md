# Demo film

[Watch the latest public demo](https://youtu.be/CB_NcgdgK5k).
The published v4 edition is **118.6 seconds, 1920×1080 at 30 fps, about 20 MB**.
It keeps the original picture, transitions, script and music, with fresh narration
from the team's two trained voices. The local output is `video/build/final-v4.mp4`;
the original `final.mp4` and earlier alternatives remain untouched.

It combines actual app footage and gateway replies with rendered titles, transitions and generated
ElevenLabs narration/music. Challenge price/stock services are synthetic; orders are local mock records,
not supplier orders.

## Fresh v4 narration

[`cinematic/revoice_v4.py`](cinematic/revoice_v4.py) uses `eleven_v4`, stability **0.45**,
similarity **0.75**, and `mp3_44100_192`. Each of the 21 original lines includes the
adjacent script lines as context, including across speaker changes. Literal `[pause]`
hints become `...` in the request only. No extra delivery tags are added.
[V4](https://elevenlabs.io/docs/overview/capabilities/text-to-speech/eleven-v4) does not
support `style` or `use_speaker_boost`; those requested controls are explicitly omitted.

### Original production inputs required

The voice-only commands require the exact original movie, original `config.json`,
21 isolated narration MP3s and their metadata, `build/music.mp3`, and `build/mix.wav`.
Run them in the original production checkout, or restore matching original sources
and retained media into a separate worktree. They are not a clean-clone build.

The cleaned-up `main` version of `video/config.json` contains later wording corrections
about scoped access and mock orders. Those corrections are not spoken in the locked
original film. The revoice tools deliberately reject a script/cache mismatch rather
than silently change its dialogue. Do not overwrite the corrected source on `main`
to recreate a historical cut. Original production sources remain on the archive branch.

Use an ignored, mode-600 `.env.cinematic` with `ELEVENLABS_API_KEY`,
`ELEVENLABS_VOICE_ID` (Krish) and `ELEVENLABS_VOICE_JAKUB` (Jakub):

```sh
uv run --no-sync python video/cinematic/revoice.py prepare
uv run --no-sync --env-file .env.cinematic python video/cinematic/revoice_v4.py voices --generate
uv run --no-sync --env-file .env.cinematic python video/cinematic/revoice_v4.py mix
uv run --no-sync --env-file .env.cinematic python video/cinematic/revoice_v4.py export
```

Only `voices --generate` can make paid requests. Matching takes are reused, and
failed or uncertain attempts are never automatically retried. `inspect` checks
the physical 192 kbps MP3s; `fit --only s01 s02` checks selected lines locally.
Immutable raw takes stay in `video/build/cinematic/voices/`; fitted stems, the mix
and verification report stay in `video/build/cinematic/original-v4/`.

The fitter shortens only measured quiet pauses and checks every removed sample
against a -55 dBFS limit. Remaining differences use pitch-preserving tempo adjustment,
capped at 1.30x, without clipping spoken material. The delivered cut's largest
correction is 1.2781x. Each line's word timings, cuts and actual tempo are recorded.

The original music and ducking are reconstructed separately and checked against
the retained mix. Old narration is never audible underneath the new voices.
Export copies every original video packet and timestamp instead of rerendering frames.

## Earlier voice-conversion edition

[`cinematic/revoice.py`](cinematic/revoice.py) transfers the original isolated
performances through ElevenLabs Voice Changer (`eleven_multilingual_sts_v2`,
stability 0.5, similarity 0.75, style 0, speaker boost enabled).
With the same original inputs and environment, use `prepare`, `voices --generate`,
`mix`, and `export`. It writes `video/build/final-conversational.mp4`, preserves the
original performance's pacing, and allows at most 5% pitch-preserving timing correction.
This is distinct from the fresh v4 readings above.

## Separate cinematic cut

The [cinematic cut pipeline](cinematic/README.md) targets **118 seconds at 1080p60**,
using the team's two trained voices and an original stereo score. It writes
`video/build/final-cinematic.mp4` without replacing the published original-picture edition.

## Original full-film pipeline

`config.json` contains 21 narration segments and a 120-second limit.
Generated files in `video/build/` are ignored, not clean-clone inputs.

### Rendering existing caches

```sh
uv run --no-sync python video/build.py --preview  # video/build/preview.jpg
uv run --no-sync python video/build.py            # video/build/final.mp4
```

Both commands require cached audio metadata, recordings and `terminal.json`, plus Playwright Chromium
and FFmpeg/ffprobe. The full render also needs cached speech and music. They reuse cached narration,
which may predate the source corrections; neither bootstraps a clean-clone offline build.

### Regeneration can incur charges

`video/make.sh` runs `voice.py` (key required even with cached speech) and `music.py`, then records missing
captures or re-records with `--record`. Changed/uncached narration and missing music use **paid ElevenLabs
APIs**; `music.py --force` also incurs generation charges. Do not run these unintentionally.
`ELEVENLABS_API_KEY` comes from the environment or a local untracked `.env`, not the challenge brief.
Never copy or commit secrets.

Recording requires an already-running, disposable local workspace. Defaults:
`http://127.0.0.1:8004` and `data/gateway/video-draft/credentials.json`, overridden with
`AIMO_URL` and `AIMO_CREDENTIALS`. Recording creates demo jobs and mock orders.
