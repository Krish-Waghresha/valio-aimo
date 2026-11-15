#!/usr/bin/env bash
# Build the 2:00 film: voices -> music -> narration-timed recording of the real app -> render -> final.mp4
# Usage: video/make.sh            (re-uses cached voices, music and recordings)
#        video/make.sh --record   (re-record the app; needs a FRESH workspace on AIMO_URL, default :8004)
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -I video/voice.py
python3 -I video/music.py
if [[ "${1:-}" == "--record" || ! -f video/build/rec/index.json ]]; then uv run python video/record.py; fi
uv run python video/build.py
open video/build/final.mp4 2>/dev/null || true
