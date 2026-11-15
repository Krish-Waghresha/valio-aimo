#!/usr/bin/env python3
"""Create cached, explicitly authorized team-voice delivery auditions."""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from video.cinematic import audio  # noqa: E402


TEXT = {
    "krish": (
        "Twenty thousand kitchens. The next buyer is an agent. "
        "We're making that opportunity work for Valio Aimo, "
        "with faster purchasing, and control built in!"
    ),
    "jakub": (
        "Our workspace handles the buying. Our gateway enforces the rules. "
        "Routine orders can move on their own. Important decisions stay with people. "
        "Open to agents. On Valio Aimo's terms!"
    ),
}
DELIVERIES = {
    "energetic": "[excited, confident, energetic presentation]",
    "confident": "[confident, upbeat business pitch, smiling voice]",
}


def voice_sample(config, model, delivery, speaker, generate):
    identity = audio.voice_identity(config, speaker)
    body = {
        "model_id": model,
        "text": f"{DELIVERIES[delivery]} {TEXT[speaker]}",
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
    }
    inputs = {
        "version": 1,
        "operation": "pitch-delivery-audition",
        "voiceIdentitySha256": hashlib.sha256(identity.encode()).hexdigest(),
        "outputFormat": audio.OUTPUT_FORMAT,
        "request": body,
    }
    signature = audio.fingerprint(inputs)
    folder = audio.BUILD / "auditions" / model / delivery / speaker
    path = folder / f"{signature}.mp3"
    metadata = path.with_suffix(".json")
    journal = path.with_suffix(".attempt.json")
    cached = audio.cached_artifact(path, metadata, signature)
    if cached is not None:
        return cached
    if journal.exists():
        raise audio.AudioError("This audition was already attempted; inspect its journal before any further request.")
    if not generate:
        raise audio.AudioError(f"Missing {delivery}/{speaker} audition; --generate authorizes this paid sample.")
    audio.require_audio_tools()
    print(f"request {delivery} / {config['voices'][speaker]['name']} / {model} (one paid attempt)", flush=True)
    with audio.paid_attempt(journal, inputs) as attempt:
        payload, provider = audio.provider_request(
            f"text-to-speech/{identity}/with-timestamps?output_format={audio.OUTPUT_FORMAT}",
            body, audio.api_key(), timeout=120, operation=f"Audition {delivery}/{speaker}",
        )
        attempt["provider"] = provider
        try:
            response = json.loads(payload)
            encoded = response["audio_base64"]
        except (ValueError, KeyError, TypeError):
            raise audio.AudioError("The audition response is not usable audio JSON; no request was repeated.") from None
        audio.atomic_json(path.with_suffix(".response.json"), response)
        try:
            decoded = base64.b64decode(encoded, validate=True)
        except (ValueError, TypeError, binascii.Error):
            raise audio.AudioError("The audition audio is invalid; its response was retained for review.") from None
        if not decoded:
            raise audio.AudioError("The audition response contains no audio; no request was repeated.")
        audio.atomic_bytes(path, decoded)
        measured = audio.probe_audio(path, decode=True)
        cached = audio.artifact_metadata(
            path, inputs, measured, provider=provider, speaker=speaker,
            delivery=delivery, text=TEXT[speaker], createdAt=audio.timestamp(),
        )
        audio.atomic_json(metadata, cached)
    return cached


def comparison(config, model, delivery, generate):
    samples = [voice_sample(config, model, delivery, speaker, generate) for speaker in TEXT]
    folder = audio.BUILD / "auditions" / model
    inputs = {
        "operation": "pitch-audition-comparison",
        "sources": [sample["audioSha256"] for sample in samples],
        "ffmpeg": audio.tool_version(),
        "delivery": delivery,
        "gap": 0.8,
        "monoLufs": -19,
    }
    path = folder / f"{delivery}.mp3"
    meta_path = path.with_suffix(".json")
    signature = audio.fingerprint(inputs)
    cached = audio.cached_artifact(path, meta_path, signature, immutable=False)
    if cached is None:
        if not generate:
            raise audio.AudioError("The local audition comparison is missing; use --generate.")
        stems = []
        for sample in samples:
            stem = folder / f"{delivery}-{sample['speaker']}-{signature[:16]}.wav"
            audio.normalize_audio(
                audio.from_relative(sample["audio"]), stem, channels=1,
                target=-19, peak=-3, lra=7,
            )
            stems.append(stem)
        with audio.staged(path) as scratch:
            audio.ffmpeg(
                "-v", "error", "-i", stems[0], "-i", stems[1],
                "-filter_complex",
                "[0:a]apad=pad_dur=0.8[first];"
                "[first][1:a]concat=n=2:v=0:a=1,pan=stereo|FL=c0|FR=c0[out]",
                "-map", "[out]", "-ar", "48000", "-c:a", "libmp3lame", "-b:a", "192k", scratch,
            )
            scratch.replace(audio.output_path(path))
        cached = audio.artifact_metadata(path, inputs, audio.probe_audio(path, decode=True))
        audio.atomic_json(meta_path, cached)
    print(f"{delivery}: {path} ({cached['probe']['duration']:.2f}s; Krish, then Jakub)", flush=True)
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=("eleven_v4", "eleven_v3"), default="eleven_v4")
    parser.add_argument("--delivery", nargs="+", choices=tuple(DELIVERIES), default=list(DELIVERIES))
    parser.add_argument("--generate", action="store_true")
    args = parser.parse_args()
    config = audio.read_json(audio.CONFIG)
    for delivery in args.delivery:
        comparison(config, args.model, delivery, args.generate)


if __name__ == "__main__":
    try:
        main()
    except audio.AudioError as error:
        raise SystemExit(f"Audition error: {error}") from None
