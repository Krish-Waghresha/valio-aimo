# Cinematic cut

A separate **118-second, 1920x1080, 60fps** revision of the demo. The hard ceiling is
119 seconds. It preserves the milk/manager, butter/autonomy, and refused-agent
scenarios, using the original recorded UI and refusal responses.

**Output:** `video/build/final-cinematic.mp4`, with an optional
`video/build/final-cinematic.srt` subtitle file. The original
`video/build/final.mp4` is never overwritten; its checksum is verified.

## Production

Use the existing development environment, Playwright Chromium, FFmpeg, and
ffprobe. The original `video/build/rec/{A,B,C}/` JPEGs and
`video/build/terminal.json` must be present. Do not run the original `make.sh` or
`record.py` to rebuild this cut: they target the original film and recording cache.

Set these variables in the ignored `.env.cinematic`, then restrict that file to
mode `600`. Never commit the credential file.

```dotenv
ELEVENLABS_API_KEY=
ELEVENLABS_VOICE_ID=
ELEVENLABS_VOICE_JAKUB=
```

The first voice variable selects Krish's approved trained voice; the second
selects Jakub's. Source configuration contains environment references, not voice
IDs or credentials.

Run from the repository root:

```sh
# Read-only voice availability check.
uv run --no-sync --env-file .env.cinematic python video/cinematic/audio.py probe

# Paid: pilot lines, then only the remaining uncached narration.
uv run --no-sync --env-file .env.cinematic python video/cinematic/audio.py voices --only s01 s02 --generate
uv run --no-sync --env-file .env.cinematic python video/cinematic/audio.py voices --generate

# Local: measured word-aligned timing, complete speech, and a clear closing hold.
uv run --no-sync --env-file .env.cinematic python video/cinematic/audio.py plan --generate --allow-tempo

# Paid: one original instrumental score, cached for every subsequent edit.
uv run --no-sync --env-file .env.cinematic python video/cinematic/audio.py music --generate

# Local: centered narration, stereo music, tactile effects, ducking, and mastering.
uv run --no-sync --env-file .env.cinematic python video/cinematic/audio.py mix --generate

uv run --no-sync python video/cinematic/build.py preview
uv run --no-sync python video/cinematic/build.py render --workers 2
uv run --no-sync python video/cinematic/build.py verify
```

Omit `--generate` on audio commands to verify their caches without generating
anything. `--allow-tempo` permits at most one uniform, pitch-preserving correction
up to 1.10x, only if complete narration otherwise exceeds the available time.
It never clips speech. Shorten the script if that bound cannot fit.

Provider attempts are journaled before sending. A timeout or interrupted request
must be investigated, not blindly repeated. Valid retained responses can be
repaired locally without another request. A changed music brief is explicitly
rejected rather than commissioning a second score.

## Editing and evidence

`config.json` owns narration and original source-time windows. `motion.js` draws
deterministic dimensional scenes; `film.html` composes them with real UI crops,
continuous camera moves, chapter labels, and word-aligned captions. Abstract
architecture illustrations are not substituted for the recorded demonstration.

Source recordings are native 1536x864 at 30fps. They remain unchanged; camera and
graphic animation run at 60fps. The renderer streams screenshots into cached,
eight-second H.264 chunks instead of keeping thousands of new full-size frames.
Render caches are keyed by the timeline, renderer source, and original recordings.

The audio master targets -16 LUFS and -2 dBTP at stereo 48kHz. Verification decodes
the exported AAC/H.264 file and checks its actual peak ceiling of -1.5 dBTP, frame
count, duration, stereo channels, interior black intervals, and original checksum.
Preview images still need visual review for framing, timing, and readability.

All generated audio, provider responses, journals, previews, manifests, and render
chunks stay under the ignored `video/build/cinematic/`.

## Direction

The revised edit uses a recurring request tile and gateway, restrained dimensional
motion, larger evidence close-ups, and alternating team narration. It reaches the
demonstration earlier than the original cut and keeps synthetic-service/local-order
context visible.

The [Stripe Treasury production case study](https://bartlomiejotlowski.com/stripe-treasury-product-animation/)
informed the UI-first framing, recurring transition element, and assembled closing
composition. The team's earlier film informed opening tension and pacing. No
reference footage, music, or artwork was copied into this film.
