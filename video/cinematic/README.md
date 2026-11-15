# Cinematic business pitch

A separate **118-second, 1920x1080, 60fps** revision of the demo. The hard ceiling is
119 seconds. It preserves the milk/manager, butter/autonomy, and refused-agent
scenarios, using the original recorded UI and refusal responses.

**Output:** `video/build/final-cinematic.mp4`, with an optional
`video/build/final-cinematic.srt` subtitle file. The original
`video/build/final.mp4` is never overwritten; its checksum is verified.
The first cinematic export is preserved locally as `video/build/final-cinematic-v1.mp4`.

The revised direction uses a music-led opening, a stable 28-second architecture
explanation, and 70 seconds for three distinct scenarios. The two trained voices
use Eleven v4: the team selected the **confident** audition for Krish and the
**energetic** audition for Jakub.

| Time | Scene |
| --- | --- |
| 0:00–0:11 | Business stakes and "Open to agents" reveal |
| 0:11–0:39 | Workspace, external agents, gateway, approval and local order record |
| 0:39–1:23 | Milk shortage, comparison and manager approval |
| 1:23–1:38 | Everyday butter order and agent decision trail |
| 1:38–1:49 | Refused bypass and self-approval |
| 1:49–1:58 | Business payoff and closing |

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

# Optional paid auditions: two delivery directions using both trained voices.
# Listen in video/cinematic/audition.html before choosing directions in config.json.
uv run --no-sync --env-file .env.cinematic python video/cinematic/audition.py --generate

# Paid: only uncached narration. Identical requests share an immutable recording.
uv run --no-sync --env-file .env.cinematic python video/cinematic/audio.py voices --generate

# Local: measured speech in fixed editorial slots; no automatic speed-up.
uv run --no-sync --env-file .env.cinematic python video/cinematic/audio.py plan --generate

# Cache-only: the original score is reused, not commissioned again for this edit.
uv run --no-sync --env-file .env.cinematic python video/cinematic/audio.py music

# Local: centered narration, stereo music, tactile effects, ducking, and mastering.
uv run --no-sync --env-file .env.cinematic python video/cinematic/audio.py mix --generate

uv run --no-sync python video/cinematic/build.py preview
uv run --no-sync python video/cinematic/build.py render --workers 2
uv run --no-sync python video/cinematic/build.py verify
```

Omit `--generate` on audio commands to verify their caches without generating
anything. With `timing: fixed`, `targetSeconds` is the actual slot length, not a
weight. An overlong line fails explicitly: shorten it or re-edit the slots without
changing the 118-second total. The legacy weighted mode retains its opt-in tempo
correction, but this business-pitch edit never speeds up narration.

The opening has two seconds of actual silence in its narration stem, leaving
space for music and typography. Its word timings are delayed by the same amount.
Performance tags never become captions. Eleven v4 can align sentence punctuation
to a trailing pause beyond the MP3's end; word end times use the final content
character, while the complete audio and original provider alignment are retained.
A residual v4 clock overhang of at most one 44.1 kHz MP3 frame is covered by
sample-exact silence at the end of the derived PCM stem. Larger discrepancies
fail for review; the source audio and word timestamps are never shortened.

Provider attempts are journaled before sending. A timeout or interrupted request
must be investigated, not blindly repeated. Valid retained responses can be
repaired locally without another request. A changed music brief is explicitly
rejected rather than commissioning a second score.

## Editing and evidence

`config.json` owns narration, fixed slots, chapters, reading holds and two explicit
zoom windows. `motion.js` draws deterministic graphics. `film.html` keeps the real
UI full-frame and steady, apart from the **approval** and **agent decisions**
zooms. Scenario labels sit in the unused page gutter and move out of the way
during close-ups. Abstract architecture illustrations never replace demo evidence.

Every recorded interval plays at or below its original speed. The butter outcome
gets a four-second reading hold. The renderer rejects extra zooms, a zoom in the
wrong scenario, shifted chapter boundaries, or a hold that would accelerate the
preceding footage. The captured 409 and 403 responses remain mandatory.

`edit.musicDynamics` controls local mix timing independently of the immutable
music-generation request. A short dip precedes the seven-second reveal; the
existing instrumental score is ducked beneath the chosen voice performances.

Source recordings are native 1536x864 at 30fps. They remain unchanged; camera and
graphic animation run at 60fps. The renderer streams screenshots into cached,
eight-second H.264 chunks instead of keeping thousands of new full-size frames.
Render caches are keyed by the timeline, renderer source, and original recordings.

The audio master targets -16 LUFS and -2 dBTP at stereo 48kHz. Verification decodes
the exported AAC/H.264 file and checks its actual peak ceiling of -1.5 dBTP, frame
count, duration, stereo channels, interior black intervals, and original checksum.
It also binds the exported movie to the current renderer, source images, timeline
and mastered mix, so an older same-length movie cannot pass as the revision.
Preview images and encoded playback still need visual review; voice enthusiasm
must be judged by listening, not by a loudness meter.

All generated audio, provider responses, journals, previews, manifests, and render
chunks stay under the ignored `video/build/cinematic/`.

## Direction

The story is about giving kitchens a new buying interface while Valio Aimo keeps
authority over the transaction. It does not claim a live production integration,
real payments, measured business ROI, or a newly built marketplace.

The [Stripe Treasury production case study](https://bartlomiejotlowski.com/stripe-treasury-product-animation/)
informed the UI-first framing, recurring transition element, and assembled closing
composition. The team's earlier film informed opening tension and pacing. No
reference footage, music, or artwork was copied into this film.

The voice revision follows ElevenLabs' official
[v4 cloning and delivery guide](https://elevenlabs.io/docs/overview/capabilities/text-to-speech/eleven-v4),
[audio-tag guidance](https://elevenlabs.io/docs/overview/capabilities/text-to-speech/best-practices#prompting-eleven-v4),
and [timestamped speech API](https://elevenlabs.io/docs/api-reference/text-to-speech/convert-with-timestamps).
V4 requests use stability and similarity, not the unsupported speed/style controls.
