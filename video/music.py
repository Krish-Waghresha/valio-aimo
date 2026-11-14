#!/usr/bin/env python3
"""Generate the background score with the ElevenLabs Music API (cached in video/build/music.mp3)."""

import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from voice import load_key  # noqa: E402

ROOT = Path(__file__).resolve().parent


def main(force=False):
    config = json.loads((ROOT / "config.json").read_text())["music"]
    out = ROOT / "build" / "music.mp3"
    if out.exists() and not force:
        print(f"cached  {out}")
        return
    body = {"prompt": config["prompt"], "music_length_ms": int(config["seconds"] * 1000)}
    request = urllib.request.Request("https://api.elevenlabs.io/v1/music?output_format=mp3_44100_128", data=json.dumps(body).encode(),
                                     method="POST", headers={"xi-api-key": load_key(), "Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=600) as response:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(response.read())
    print(f"music   {out}")


if __name__ == "__main__":
    main("--force" in sys.argv)
