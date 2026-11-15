#!/usr/bin/env python3
"""Generate the two-speaker voiceover with ElevenLabs, including word timings.

Reads video/config.json, writes video/build/audio/<id>.mp3 and <id>.json (word timings).
Cached by text+voice+settings hash: re-running only pays for changed lines.
Needs ELEVENLABS_API_KEY in the environment or the untracked .env file.
"""

import base64
import hashlib
import json
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BUILD = ROOT / "build" / "audio"


def load_key():
    if os.environ.get("ELEVENLABS_API_KEY"):
        return os.environ["ELEVENLABS_API_KEY"]
    env = ROOT.parent / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("ELEVENLABS_API_KEY="):
                return line.split("=", 1)[1].strip().strip("'\"")
    sys.exit("Set ELEVENLABS_API_KEY (or add it to the untracked .env).")


def words_from_alignment(alignment):
    chars = alignment["characters"]
    starts = alignment["character_start_times_seconds"]
    ends = alignment["character_end_times_seconds"]
    words, current, start, last_end = [], "", None, 0.0
    for char, begin, end in zip(chars, starts, ends):
        if char.isspace():
            if current:
                words.append({"word": current, "start": start, "end": last_end})
            current, start = "", None
            continue
        if not current:
            start = begin
        current += char
        last_end = end
    if current:
        words.append({"word": current, "start": start, "end": last_end})
    return words


def main(only=None):
    config = json.loads((ROOT / "config.json").read_text())
    key = load_key()
    BUILD.mkdir(parents=True, exist_ok=True)
    total = 0
    for segment in config["segments"]:
        if only and segment["id"] not in only:
            continue
        voice = config["voices"][segment["speaker"]]
        settings = {**config["voiceSettings"], **voice.get("settings", {})}
        fingerprint = hashlib.sha256(json.dumps([segment["text"], voice["voiceId"], config["model"], settings]).encode()).hexdigest()[:16]
        meta_path = BUILD / f"{segment['id']}.json"
        if meta_path.exists() and json.loads(meta_path.read_text()).get("fingerprint") == fingerprint:
            meta = json.loads(meta_path.read_text())
            print(f"cached  {segment['id']} {meta['duration']:5.2f}s  {voice['name']}: {segment['text'][:60]}")
            total += meta["duration"]
            continue
        body = {"text": segment["text"], "model_id": config["model"], "voice_settings": settings}
        request = urllib.request.Request(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice['voiceId']}/with-timestamps?output_format=mp3_44100_128",
            data=json.dumps(body).encode(), method="POST", headers={"xi-api-key": key, "Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=120) as response:
            result = json.load(response)
        (BUILD / f"{segment['id']}.mp3").write_bytes(base64.b64decode(result["audio_base64"]))
        words = words_from_alignment(result["alignment"])
        duration = round(result["alignment"]["character_end_times_seconds"][-1] + 0.05, 3)
        meta = {"id": segment["id"], "speaker": segment["speaker"], "text": segment["text"], "words": words, "duration": duration, "fingerprint": fingerprint}
        meta_path.write_text(json.dumps(meta, indent=1))
        print(f"voiced  {segment['id']} {duration:5.2f}s  {voice['name']}: {segment['text'][:60]}")
        total += duration
    print(f"total speech {total:.1f}s")


if __name__ == "__main__":
    main(set(sys.argv[1:]) or None)
