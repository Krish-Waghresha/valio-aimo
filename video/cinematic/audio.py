#!/usr/bin/env python3
"""Opt-in audio production for the approved 118-second cinematic cut.

Run from the repository root (this module never reads an environment file):

    uv run --env-file .env.cinematic python video/cinematic/audio.py probe
    uv run --env-file .env.cinematic python video/cinematic/audio.py voices --only s01 s02 --generate
    uv run --env-file .env.cinematic python video/cinematic/audio.py voices --generate
    uv run --env-file .env.cinematic python video/cinematic/audio.py plan --generate --allow-tempo
    uv run --env-file .env.cinematic python video/cinematic/audio.py music --generate
    uv run --env-file .env.cinematic python video/cinematic/audio.py mix --generate

Omitting --generate verifies existing outputs; it never makes a paid request.
Only voices/music can spend, and neither retries. An attempt journal survives
timeouts and interrupts, blocking an ambiguous repeat even with --generate.
Investigate its state before manually authorizing another request. A changed
music request is always rejected: this cut gets ONE original score.

Plan/mix verify config and audio checksums plus current voice-identity hashes;
both need the voice environment variables, but not the API key. Changed
identity/text/settings cannot silently reuse a previous plan. mix.json records
the exact stereo graph, inputs, dynamics, and independently measured loudness.

All writes, including staging files, stay under video/build/cinematic.
Source recordings, the original terminal transcript, and older film/audio
builds are read-only. No silence is trimmed. Timing uses decoded, normalized
WAV durations, not the final alignment timestamp. --allow-tempo permits one
uniform atempo correction (at most 1.10x); it does not rewrite or regenerate
dialogue. A small documented silence pad flushes atempo's final window.

film.json is the compositor contract: 60 fps, 1920x1080, duration 118.0,
maxSeconds 119, unchanged config segment fields plus start/duration/speech,
segment-relative words and a build-relative audio path. All cuts are on frame
boundaries. `speech` is the complete final stem duration, excluding its
following segment hold. Only voice display names enter the film.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import copy
import hashlib
import http.client
import json
import math
import os
import random
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import wave
from array import array
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


HERE = Path(__file__).resolve().parent
CONFIG = HERE / "config.json"
BUILD = HERE.parent / "build" / "cinematic"
TERMINAL = HERE.parent / "build" / "terminal.json"
API = "https://api.elevenlabs.io/v1"
VOICE_ENVS = {"krish": "ELEVENLABS_VOICE_ID", "jakub": "ELEVENLABS_VOICE_JAKUB"}
VERSION = 1
SAMPLE_RATE = 48_000
ALIGNMENT_TOLERANCE = 0.0005 + 1 / SAMPLE_RATE
GAP = 0.18
END_HOLD = 1.3
MAX_TEMPO = 1.10
TEMPO_PAD = 0.12
TEMPO_MARGIN = 0.04
VOICE_LUFS = -21.0  # Duplicating centered mono into stereo adds about 3 LU.
MUSIC_LUFS = -23.0
MASTER_LUFS = -16.0
MASTER_TP = -2.0  # Leave AAC overshoot headroom for the builder's -1.5 dBTP ceiling.
MASTER_LRA = 6.0
OUTPUT_FORMAT = "mp3_44100_128"
TOOL_TIMEOUT = 1_800


class AudioError(Exception):
    """An actionable, credential-free failure."""


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()


def fingerprint(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def number(value, label, minimum=0.0):
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise AudioError(f"{label} must be a finite number.")
    if not math.isfinite(value) or value < minimum:
        raise AudioError(f"{label} must be finite and at least {minimum}.")
    return float(value)


def read_json(path):
    try:
        with path.open(encoding="utf-8") as stream:
            return json.load(stream)
    except (OSError, ValueError) as exc:
        raise AudioError(f"Cannot read valid JSON from {path.name}.") from exc


def output_path(path):
    """Reject traversal and symlinks before any write or cached-audio read."""
    path = Path(path).absolute()
    root = BUILD.absolute()
    if not path.is_relative_to(root):
        raise AudioError("An output path escaped video/build/cinematic.")
    current = path
    while True:
        if current.is_symlink():
            raise AudioError("Symlinks are not allowed in cinematic audio output paths.")
        if current == root.parent:
            break
        current = current.parent
    if not path.resolve().is_relative_to(root):
        raise AudioError("The cinematic output directory resolves outside its intended location.")
    return path


def relative(path):
    return output_path(path).relative_to(BUILD.absolute()).as_posix()


def from_relative(name):
    if not isinstance(name, str) or Path(name).is_absolute():
        raise AudioError("Expected a cinematic-build-relative audio path.")
    return output_path(BUILD / name)


@contextmanager
def staged(path):
    path = output_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    scratch = output_path(path.with_name(f".{path.stem}.{uuid.uuid4().hex}.part{path.suffix}"))
    try:
        yield scratch
    finally:
        scratch.unlink(missing_ok=True)


def atomic_bytes(path, data, *, exclusive=False):
    with staged(path) as scratch:
        with scratch.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if exclusive:
            try:
                os.link(scratch, output_path(path))
            except FileExistsError as exc:
                raise AudioError(
                    f"Existing request journal {relative(path)} blocks a duplicate request. "
                    "Investigate the previous attempt; no automatic retry is permitted."
                ) from exc
        else:
            os.replace(scratch, output_path(path))


def atomic_json(path, data, *, exclusive=False):
    atomic_bytes(path, json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False).encode() + b"\n",
                 exclusive=exclusive)


def atomic_copy(source, destination):
    output_path(source)
    with staged(destination) as scratch:
        with source.open("rb") as incoming, scratch.open("xb") as outgoing:
            shutil.copyfileobj(incoming, outgoing, 1 << 20)
            outgoing.flush()
            os.fsync(outgoing.fileno())
        os.replace(scratch, output_path(destination))


def run_tool(arguments, *, timeout=TOOL_TIMEOUT):
    try:
        result = subprocess.run(arguments, capture_output=True, text=True, timeout=timeout, check=False)
    except FileNotFoundError as exc:
        raise AudioError(f"Required local tool is missing: {arguments[0]}.") from exc
    except subprocess.TimeoutExpired as exc:
        raise AudioError(f"{arguments[0]} exceeded its local render timeout; no provider request was retried.") from exc
    if result.returncode:
        # Only local media paths reach this runner; provider URLs/headers never do.
        raise AudioError(f"{arguments[0]} failed ({result.returncode}):\n{result.stderr[-2400:]}")
    return result


def ffmpeg(*arguments):
    return run_tool(["ffmpeg", "-hide_banner", "-nostdin", "-y", *map(str, arguments)])


def tool_version():
    return run_tool(["ffmpeg", "-version"]).stdout.splitlines()[0]


def require_audio_tools():
    for name in ("ffmpeg", "ffprobe"):
        if not shutil.which(name):
            raise AudioError(f"{name} is required before a paid request; no request was made.")


def probe_audio(path, *, decode=False):
    result = run_tool([
        "ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries",
        "format=duration:stream=codec_name,sample_rate,channels,channel_layout,duration,duration_ts,time_base",
        "-of", "json", str(path),
    ])
    try:
        document = json.loads(result.stdout)
        stream = document["streams"][0]
        if stream.get("duration_ts") is not None and stream.get("time_base"):
            numerator, denominator = map(int, stream["time_base"].split("/"))
            duration = float(stream["duration_ts"]) * numerator / denominator
        else:
            duration = float(stream.get("duration", document.get("format", {}).get("duration")))
        sample_rate = int(stream["sample_rate"])
        channels = int(stream["channels"])
    except (KeyError, IndexError, TypeError, ValueError, ZeroDivisionError) as exc:
        raise AudioError(f"ffprobe could not measure {path.name}.") from exc
    if not math.isfinite(duration) or duration <= 0 or sample_rate <= 0 or channels not in (1, 2):
        raise AudioError(f"Unsupported or empty audio in {path.name}.")
    if decode:
        ffmpeg("-v", "error", "-xerror", "-i", path, "-map", "0:a:0", "-f", "null", "-")
    return {
        "duration": duration, "sampleRate": sample_rate, "channels": channels,
        "channelLayout": stream.get("channel_layout", "mono" if channels == 1 else "stereo"),
        "codec": stream.get("codec_name"),
    }


def cached_artifact(audio, meta_path, expected, *, immutable=True):
    audio, meta_path = output_path(audio), output_path(meta_path)
    if not audio.exists() and not meta_path.exists():
        return None
    if not audio.is_file() or not meta_path.is_file():
        if not immutable:
            return None
        raise AudioError(f"Incomplete cache at {relative(meta_path)}; no paid regeneration will be attempted.")
    meta = read_json(meta_path)
    if not isinstance(meta, dict) or meta.get("fingerprint") != expected:
        if not immutable:
            return None
        raise AudioError(f"Stale or mismatched cache at {relative(meta_path)}.")
    if not isinstance(meta.get("inputs"), dict) or fingerprint(meta["inputs"]) != expected:
        raise AudioError(f"Cache provenance does not match its fingerprint: {relative(meta_path)}.")
    if meta.get("audio") != relative(audio) or meta.get("audioSha256") != sha256(audio):
        raise AudioError(f"Audio checksum/path mismatch at {relative(meta_path)}; investigate before proceeding.")
    measured = probe_audio(audio)
    stored = meta.get("probe", {})
    if any(measured.get(key) != stored.get(key) for key in ("sampleRate", "channels", "codec")):
        raise AudioError(f"Audio format does not match its metadata: {relative(audio)}.")
    if abs(measured["duration"] - number(stored.get("duration"), "cached duration")) > 1 / SAMPLE_RATE:
        raise AudioError(f"Audio duration does not match its metadata: {relative(audio)}.")
    return meta


def artifact_metadata(audio, inputs, measured, **extra):
    return {
        "version": VERSION, "fingerprint": fingerprint(inputs), "inputs": inputs,
        "audio": relative(audio), "audioSha256": sha256(audio), "probe": measured, **extra,
    }


def validate_config(config):
    if not isinstance(config, dict):
        raise AudioError("The cinematic configuration must be an object.")
    for key, expected in (("duration", 118.0), ("maxSeconds", 119.0), ("fps", 60), ("width", 1920), ("height", 1080)):
        if config.get(key) != expected:
            raise AudioError(f"The approved cinematic {key} must be {expected}.")
    if config.get("model") not in ("eleven_multilingual_v2", "eleven_v4"):
        raise AudioError("Use the original multilingual v2 model or the auditioned Eleven v4 model.")
    if config.get("timing", "weighted") not in ("weighted", "fixed"):
        raise AudioError("Timing must be weighted or fixed.")
    if not isinstance(config.get("voiceSettings"), dict):
        raise AudioError("voiceSettings must be an object.")
    voices = config.get("voices", {})
    if set(voices) != set(VOICE_ENVS):
        raise AudioError("The cinematic cut requires the two configured speakers.")
    for speaker, env in VOICE_ENVS.items():
        voice = voices[speaker]
        if not isinstance(voice, dict) or voice.get("env") != env:
            raise AudioError(f"The {speaker} voice must be supplied by its approved environment variable.")
        if not isinstance(voice.get("name"), str) or not voice["name"].strip():
            raise AudioError("Each speaker needs a display name.")
        if any(key.lower() in ("voiceid", "voice_id", "api_key", "key") for key in voice):
            raise AudioError("Voice identities and credentials belong only in environment variables.")
        delivery = voice.get("delivery", "")
        if not isinstance(delivery, str) or (delivery and not re.fullmatch(r"\[[^\[\]\r\n]+\]", delivery)):
            raise AudioError("Delivery must be one explicit leading audio tag.")
        if delivery and config["model"] != "eleven_v4":
            raise AudioError("Performance tags require the auditioned expressive model, not multilingual v2.")
        if config["model"] == "eleven_v4":
            settings = {**config["voiceSettings"], **voice.get("settings", {})}
            if set(settings) - {"stability", "similarity_boost"}:
                raise AudioError("Eleven v4 supports stability and similarity here, not style, speed or speaker boost.")
            for key, value in settings.items():
                if number(value, key) > 1:
                    raise AudioError(f"{key} must be between zero and one.")
    segments = config.get("segments")
    if not isinstance(segments, list) or not segments:
        raise AudioError("No cinematic segments were configured.")
    seen = set()
    for segment in segments:
        ident = segment.get("id", "")
        if not isinstance(ident, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", ident) or ident in seen:
            raise AudioError("Segment IDs must be unique, safe filename components.")
        seen.add(ident)
        if segment.get("speaker") not in voices or not isinstance(segment.get("text"), str) or not segment["text"].strip():
            raise AudioError(f"{ident} needs an approved speaker and nonempty text.")
        slot = number(segment.get("targetSeconds"), f"{ident} targetSeconds", 0.001)
        lead_in = number(segment.get("leadInSeconds", 0), f"{ident} leadInSeconds")
        if lead_in and (config.get("timing") != "fixed" or lead_in >= slot):
            raise AudioError("A music-only lead-in requires a fixed slot with room for the complete speech.")
        if not isinstance(segment.get("visual"), dict):
            raise AudioError(f"{ident} needs its original visual specification.")
        visual = segment["visual"]
        if "rec" in visual:
            start = number(visual.get("sourceStart"), f"{ident} sourceStart")
            if number(visual.get("sourceEnd"), f"{ident} sourceEnd") <= start:
                raise AudioError(f"{ident} has an invalid recording window.")
            hold = number(visual.get("holdEndSeconds", 0), f"{ident} holdEndSeconds")
            if hold >= slot:
                raise AudioError(f"{ident} must leave time to play its recording before the reading hold.")
            if config.get("timing") == "fixed" and visual["sourceEnd"] - start > slot - hold + 1e-9:
                raise AudioError(f"{ident} would accelerate the recorded demo; extend its fixed viewing time.")
    if config.get("timing") == "fixed":
        if abs(sum(segment["targetSeconds"] for segment in segments) - config["duration"]) > 1e-9:
            raise AudioError("Fixed editorial slots must add up to the complete 118-second film.")
    music_request(config)
    return config


def voice_identity(config, speaker):
    env = config["voices"][speaker]["env"]
    identity = os.environ.get(env, "").strip()
    if not identity or not re.fullmatch(r"[A-Za-z0-9_-]+", identity):
        raise AudioError(f"Set a valid {env} in the process environment. No environment files are read by this tool.")
    return identity


def api_key():
    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not key:
        raise AudioError("Set ELEVENLABS_API_KEY in the process environment before a provider operation.")
    if any(ord(char) < 33 or ord(char) > 126 for char in key):
        raise AudioError("ELEVENLABS_API_KEY contains invalid header characters; its value was withheld.")
    return key


def speech_request(config, index):
    segment = config["segments"][index]
    identity = voice_identity(config, segment["speaker"])
    delivery = config["voices"][segment["speaker"]].get("delivery", "")
    body = {
        "text": f"{delivery} {segment['text']}".strip(), "model_id": config["model"],
        "voice_settings": {**config["voiceSettings"], **config["voices"][segment["speaker"]].get("settings", {})},
    }
    # Only contiguous same-speaker lines provide continuity; never another narrator's text.
    for neighbor, field in ((index - 1, "previous_text"), (index + 1, "next_text")):
        if 0 <= neighbor < len(config["segments"]):
            adjacent = config["segments"][neighbor]
            if adjacent["speaker"] == segment["speaker"]:
                body[field] = adjacent["text"]
    inputs = {
        "version": VERSION, "provider": "elevenlabs", "operation": "tts-with-timestamps",
        "outputFormat": OUTPUT_FORMAT, "voiceIdentitySha256": hashlib.sha256(identity.encode()).hexdigest(),
        "request": body,
    }
    return inputs, identity


def words_from_alignment(alignment, text, *, delivery="", exclude_pause_timing=False):
    if not isinstance(alignment, dict):
        raise AudioError("The timestamped response has no usable alignment; the paid request will not be repeated.")
    chars = alignment.get("characters")
    starts = alignment.get("character_start_times_seconds")
    ends = alignment.get("character_end_times_seconds")
    if not all(isinstance(value, list) and value for value in (chars, starts, ends)):
        raise AudioError("Alignment arrays must be nonempty.")
    if len(chars) != len(starts) or len(chars) != len(ends) or not all(isinstance(char, str) for char in chars):
        raise AudioError("Alignment arrays have inconsistent lengths or characters.")
    aligned = "".join(chars)
    if delivery and aligned.lstrip().startswith(delivery):
        # v4 aligns the delivery tag too; remove only the exact requested prefix.
        remaining = len(aligned) - len(aligned.lstrip()) + len(delivery)
        kept = []
        for char, begin, end in zip(chars, starts, ends, strict=True):
            skip = min(len(char), remaining)
            remaining -= skip
            if char[skip:]:
                kept.append((char[skip:], begin, end))
        if not kept:
            raise AudioError("The provider aligned a direction but no spoken words.")
        chars, starts, ends = map(list, zip(*kept, strict=True))
    if " ".join("".join(chars).split()) != " ".join(text.split()):
        raise AudioError("The returned alignment does not match the requested text; retained for manual review.")
    words, current, first, last, content_end, previous_start, previous_end = [], "", 0.0, 0.0, None, 0.0, 0.0
    for char, begin, end in zip(chars, starts, ends, strict=True):
        begin = number(begin, "character start")
        end = number(end, "character end")
        if end < begin or begin < previous_start or end < previous_end:
            raise AudioError("Character alignment is not chronological.")
        previous_start, previous_end = begin, end
        for part in re.findall(r"\s+|\S+", char):
            if part.isspace():
                if current:
                    words.append({"word": current, "start": first, "end": content_end if content_end is not None else last})
                current = ""
                content_end = None
            else:
                if not current:
                    first = begin
                current += part
                last = end
                # v4 assigns trailing punctuation a pause that can outlast the MP3.
                if not exclude_pause_timing or part.strip(".,!?;:"):
                    content_end = end
    if current:
        words.append({"word": current, "start": first, "end": content_end if content_end is not None else last})
    if not words:
        raise AudioError("No word timings were returned.")
    return words


def validate_words(words, duration):
    if not isinstance(words, list) or not words:
        raise AudioError("A narration stem has no word alignment.")
    previous = 0.0
    for word in words:
        if not isinstance(word, dict) or not isinstance(word.get("word"), str) or not word["word"].strip():
            raise AudioError("Invalid aligned word.")
        start = number(word.get("start"), "word start")
        end = number(word.get("end"), "word end")
        # Provider timestamps round to milliseconds; decoded audio is sample-exact.
        if start < previous or end < start or end > duration + ALIGNMENT_TOLERANCE:
            raise AudioError("Word alignment lies outside the complete audio stem; no timings were clipped.")
        previous = start


def alignment_padding(words, measured, model):
    overhang = max(word["end"] for word in words) - measured["duration"]
    if overhang <= ALIGNMENT_TOLERANCE:
        return 0.0
    if (
        model != "eleven_v4" or measured["codec"] != "mp3" or measured["sampleRate"] != 44100
        or overhang > 1152 / measured["sampleRate"] + ALIGNMENT_TOLERANCE
    ):
        raise AudioError("Spoken alignment exceeds the audio by more than one MP3 frame; retained for review.")
    # Keep both the original MP3 and its timestamps; pad the derived PCM, not the speech.
    return (math.ceil(overhang * SAMPLE_RATE - 1e-9) + 1) / SAMPLE_RATE


def retime_words(words, tempo):
    return [{"word": word["word"], "start": word["start"] / tempo, "end": word["end"] / tempo} for word in words]


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def provider_request(endpoint, body, key, *, timeout, operation, max_bytes=48 << 20):
    """One HTTP attempt, no redirects/retries, and no response-body error logging."""
    request = urllib.request.Request(
        f"{API}/{endpoint}", data=None if body is None else canonical(body),
        method="GET" if body is None else "POST",
        headers={"xi-api-key": key, "Content-Type": "application/json", "Accept": "*/*"},
    )
    started = time.monotonic()
    try:
        opener = urllib.request.build_opener(NoRedirect())
        with opener.open(request, timeout=timeout) as response:
            chunks, size = [], 0
            while True:
                if time.monotonic() - started > timeout:
                    raise TimeoutError
                block = response.read1(64 << 10)
                if not block:
                    break
                chunks.append(block)
                size += len(block)
                if size > max_bytes:
                    raise AudioError(f"{operation}: provider response exceeded the safety size limit.")
            request_id = response.headers.get("request-id") or response.headers.get("x-request-id")
            return b"".join(chunks), {
                "httpStatus": response.status, "receivedAt": timestamp(),
                "requestIdSha256": hashlib.sha256(request_id.encode()).hexdigest() if request_id else None,
            }
    except urllib.error.HTTPError as exc:
        status = exc.code
        exc.close()
        descriptions = {
            400: "request rejected", 401: "authentication rejected", 403: "voice or model access denied",
            404: "voice or endpoint unavailable", 422: "request validation failed",
            429: "quota or rate limit", 500: "provider failure", 502: "provider gateway failure",
            503: "provider unavailable", 504: "provider gateway timeout",
        }
        raise AudioError(
            f"{operation}: HTTP {status} ({descriptions.get(status, 'provider request failed')}). "
            "Provider details were withheld; no retry was made."
        ) from None
    except (TimeoutError, socket.timeout):
        raise AudioError(
            f"{operation}: timed out; billing/completion may be unknown. No retry was made."
        ) from None
    except urllib.error.URLError:
        raise AudioError(
            f"{operation}: connection/TLS failure; completion may be unknown. No retry was made."
        ) from None
    except OSError:
        raise AudioError(f"{operation}: network read failed; completion may be unknown. No retry was made.") from None
    except http.client.HTTPException:
        raise AudioError(f"{operation}: incomplete HTTP response; completion may be unknown. No retry was made.") from None


@contextmanager
def paid_attempt(journal, inputs):
    record = {"fingerprint": fingerprint(inputs), "inputs": inputs, "startedAt": timestamp(), "state": "started"}
    atomic_json(journal, record, exclusive=True)
    try:
        yield record
    except BaseException as exc:
        record.update(state="failed_or_unknown", finishedAt=timestamp())
        record["error"] = str(exc) if isinstance(exc, AudioError) else type(exc).__name__
        atomic_json(journal, record)
        raise
    else:
        record.update(state="complete", finishedAt=timestamp())
        atomic_json(journal, record)


def voice_paths(ident, request_hash):
    stem = BUILD / "voices" / ident / request_hash
    return stem.with_suffix(".mp3"), stem.with_suffix(".json"), stem.with_suffix(".attempt.json")


def voice_cache(config, index):
    segment = config["segments"][index]
    inputs, identity = speech_request(config, index)
    request_hash = fingerprint(inputs)
    audio, meta_path, journal = voice_paths(segment["id"], request_hash)
    meta = cached_artifact(audio, meta_path, request_hash)
    if meta is None:
        if output_path(journal).exists() or output_path(audio.with_suffix(".response.json")).exists():
            raise AudioError(
                f"{segment['id']}: an earlier request has no committed, valid cache. "
                f"Investigate {relative(journal)}; no duplicate request is allowed."
            )
        for candidate in sorted((BUILD / "voices").glob(f"*/{request_hash}.json")):
            meta = cached_artifact(candidate.with_suffix(".mp3"), candidate, request_hash)
            if meta:
                audio = from_relative(meta["audio"])
                break
    if meta:
        if meta.get("inputs") != inputs:
            raise AudioError(f"{segment['id']}: synthesis metadata is stale.")
        response_path = output_path(audio.with_suffix(".response.json"))
        if not response_path.is_file() or sha256(response_path) != meta.get("responseSha256"):
            raise AudioError(f"{segment['id']}: alignment response cache is missing or modified.")
        response = read_json(response_path)
        words = words_from_alignment(
            response.get("alignment"), segment["text"],
            delivery=config["voices"][segment["speaker"]].get("delivery", ""),
            exclude_pause_timing=config["model"] == "eleven_v4",
        )
        if words != meta.get("words"):
            raise AudioError(f"{segment['id']}: word metadata differs from the saved alignment.")
        padding = alignment_padding(words, meta["probe"], config["model"])
        if meta.get("alignmentPaddingSeconds", 0) != padding:
            raise AudioError("The voice cache does not record its required bounded alignment padding.")
        validate_words(words, meta["probe"]["duration"] + padding)
    return inputs, identity, meta


def voices(config, *, only=None, generate=False, timeout=120):
    selected = set(only or [segment["id"] for segment in config["segments"]])
    unknown = selected - {segment["id"] for segment in config["segments"]}
    if unknown:
        raise AudioError("Unknown segment IDs in --only: " + ", ".join(sorted(unknown)))
    entries = []
    for index, segment in enumerate(config["segments"]):
        if segment["id"] in selected:
            inputs, identity, meta = voice_cache(config, index)
            entries.append((segment, inputs, identity, meta))
    missing = [segment["id"] for segment, _, _, meta in entries if meta is None]
    if missing and not generate:
        raise AudioError("Missing/stale voice cache for " + ", ".join(missing) + "; use --generate to authorize synthesis.")
    if missing:
        require_audio_tools()
    key = api_key() if missing else None
    results, completed_requests = [], {}
    for segment, inputs, identity, meta in entries:
        request_hash = fingerprint(inputs)
        if meta is None:
            meta = completed_requests.get(request_hash)
        if meta is None:
            audio, meta_path, journal = voice_paths(segment["id"], request_hash)
            prior = list(audio.parent.glob("*.mp3")) if audio.parent.is_dir() else []
            if prior:
                print(f"{segment['id']}: synthesis inputs changed; creating a new immutable voice cache.", flush=True)
            print(f"request {segment['id']} / {config['voices'][segment['speaker']]['name']} (one paid attempt)", flush=True)
            with paid_attempt(journal, inputs) as attempt:
                payload, provider = provider_request(
                    f"text-to-speech/{urllib.parse.quote(identity, safe='')}/with-timestamps?output_format={OUTPUT_FORMAT}",
                    inputs["request"], key, timeout=timeout, operation=f"TTS {segment['id']}",
                )
                attempt["provider"] = provider
                try:
                    result = json.loads(payload)
                    retained = {"audio_base64": result["audio_base64"], "alignment": result.get("alignment")}
                except (ValueError, KeyError, TypeError):
                    raise AudioError("TTS returned an unusable JSON response; the request will not be repeated.") from None
                response_path = audio.with_suffix(".response.json")
                atomic_json(response_path, retained)
                try:
                    decoded = base64.b64decode(retained["audio_base64"], validate=True)
                except (ValueError, TypeError, binascii.Error):
                    raise AudioError("TTS returned invalid base64 audio; retained for review, not regeneration.") from None
                if not decoded:
                    raise AudioError("TTS returned empty audio; no regeneration was attempted.")
                atomic_bytes(audio, decoded)
                measured = probe_audio(audio, decode=True)
                words = words_from_alignment(
                    retained["alignment"], segment["text"],
                    delivery=config["voices"][segment["speaker"]].get("delivery", ""),
                    exclude_pause_timing=config["model"] == "eleven_v4",
                )
                padding = alignment_padding(words, measured, config["model"])
                validate_words(words, measured["duration"] + padding)
                meta = artifact_metadata(
                    audio, inputs, measured, id=segment["id"], speaker=segment["speaker"], words=words,
                    responseSha256=sha256(response_path), provider=provider, createdAt=timestamp(),
                    alignmentPaddingSeconds=padding,
                )
                atomic_json(meta_path, meta)
        print(f"cached  {segment['id']} {meta['probe']['duration']:.3f}s / {config['voices'][segment['speaker']]['name']}")
        completed_requests[request_hash] = meta
        results.append(meta)
    return results


def music_request(config):
    music = config.get("music", {})
    if music.get("model") != "music_v1":
        raise AudioError("The approved score model is music_v1.")
    sections = []
    for section in music.get("sections", []):
        seconds = number(section.get("seconds"), "music section seconds", 0.001)
        milliseconds = round(seconds * 1000)
        if abs(seconds * 1000 - milliseconds) > 1e-6:
            raise AudioError("Music section lengths must resolve to whole milliseconds.")
        positive = section.get("positive_local_styles")
        if positive is None:
            positive = [section.get("style", "")]
        sections.append({
            "section_name": section.get("name"), "positive_local_styles": positive,
            "negative_local_styles": section.get("negative_local_styles", []),
            "duration_ms": milliseconds, "lines": [],
        })
    if not sections or sum(section["duration_ms"] for section in sections) != 118_000:
        raise AudioError("The single composition plan must sum to exactly 118000 ms.")
    for section in sections:
        if not isinstance(section["section_name"], str) or not section["section_name"].strip():
            raise AudioError("Each music section needs a name.")
    composition = {
        "positive_global_styles": music.get("positive_global_styles"),
        "negative_global_styles": music.get("negative_global_styles"), "sections": sections,
    }
    for styles in [composition["positive_global_styles"], composition["negative_global_styles"]] + [
        section[key] for section in sections for key in ("positive_local_styles", "negative_local_styles")
    ]:
        if not isinstance(styles, list) or not all(isinstance(style, str) and style.strip() for style in styles):
            raise AudioError("Music styles must be lists of nonempty strings.")
    # force_instrumental belongs to prompt-based generation, not composition plans.
    return {"model_id": "music_v1", "composition_plan": composition, "respect_sections_durations": True}


def music(config, *, generate=False, timeout=600):
    inputs = {
        "version": VERSION, "provider": "elevenlabs", "operation": "music",
        "outputFormat": OUTPUT_FORMAT, "request": music_request(config),
    }
    expected = fingerprint(inputs)
    directory = BUILD / "score"
    audio, meta_path = directory / "music.mp3", directory / "music.json"
    request_path, journal = directory / "request.json", directory / "attempt.json"
    if output_path(request_path).exists() and read_json(request_path) != inputs:
        raise AudioError("The score request changed. Refusing to commission a second composition, even with --generate.")
    meta = cached_artifact(audio, meta_path, expected)
    if meta:
        if not request_path.is_file() or meta.get("inputs") != inputs:
            raise AudioError("The score cache is missing matching request provenance.")
    else:
        if output_path(journal).exists() or request_path.exists():
            raise AudioError(
                "A score request was already attempted without a committed cache. "
                "Investigate score/attempt.json; a second paid request is blocked."
            )
        if not generate:
            raise AudioError("No cached original score. music --generate authorizes its ONE paid request.")
        require_audio_tools()
        key = api_key()
        print("request one original instrumental score (118000 ms; no retries)", flush=True)
        with paid_attempt(journal, inputs) as attempt:
            atomic_json(request_path, inputs)
            payload, provider = provider_request(
                f"music?output_format={OUTPUT_FORMAT}", inputs["request"], key,
                timeout=timeout, operation="Music", max_bytes=64 << 20,
            )
            attempt["provider"] = provider
            atomic_bytes(audio, payload)
            measured = probe_audio(audio, decode=True)
            meta = artifact_metadata(audio, inputs, measured, provider=provider, createdAt=timestamp())
            atomic_json(meta_path, meta)
    duration = meta["probe"]["duration"]
    if duration < 117.5 or duration > 119.0:
        raise AudioError(f"Cached score is {duration:.3f}s, outside the requested duration tolerance. No new request allowed.")
    if meta["probe"]["channels"] != 2:
        raise AudioError("The original score is not stereo. Retained for review; no second composition will be requested.")
    print(f"cached  original score {duration:.3f}s / stereo")
    return meta


def loudness_report(stderr):
    matches = re.findall(r'\{\s*"input_i"\s*:.*?\}', stderr, flags=re.DOTALL)
    if not matches:
        raise AudioError("FFmpeg returned no loudness measurement.")
    try:
        report = json.loads(matches[-1])
        for field in ("input_i", "input_tp", "input_lra", "input_thresh", "target_offset"):
            if not math.isfinite(float(report[field])):
                raise ValueError
    except (ValueError, KeyError, TypeError):
        raise AudioError("Audio is silent or its loudness could not be measured; no silent fallback is used.") from None
    return report


def loudnorm_filter(target, peak, lra, measured=None):
    expression = f"loudnorm=I={target}:TP={peak}:LRA={lra}"
    if measured:
        for argument, field in (
            ("measured_I", "input_i"), ("measured_TP", "input_tp"), ("measured_LRA", "input_lra"),
            ("measured_thresh", "input_thresh"), ("offset", "target_offset"),
        ):
            expression += f":{argument}={float(measured[field])}"
        expression += ":linear=true"
    return expression + ":print_format=json"


def measure_loudness(path, *, target=MASTER_LUFS, peak=MASTER_TP, lra=MASTER_LRA, prefix=None):
    filters = ([prefix] if prefix else []) + [loudnorm_filter(target, peak, lra)]
    result = ffmpeg("-v", "info", "-i", path, "-map", "0:a:0", "-af", ",".join(filters), "-f", "null", "-")
    return loudness_report(result.stderr)


def normalize_audio(source, destination, *, channels, target, peak, lra, prefix="anull"):
    first = measure_loudness(source, target=target, peak=peak, lra=lra, prefix=prefix)
    filters = f"{prefix},{loudnorm_filter(target, peak, lra, first)},aresample={SAMPLE_RATE}"
    with staged(destination) as scratch:
        result = ffmpeg(
            "-v", "info", "-i", source, "-map", "0:a:0", "-af", filters,
            "-ar", SAMPLE_RATE, "-ac", channels, "-c:a", "pcm_s24le", scratch,
        )
        second = loudness_report(result.stderr)
        measured = probe_audio(scratch, decode=True)
        os.replace(scratch, output_path(destination))
    return measured, {"firstPass": first, "secondPass": second, "targetLufs": target, "targetTruePeak": peak, "targetLra": lra}


def normalized_voice(raw, *, generate, ffmpeg_version, tempo=1.0, base=None, lead_in=0.0):
    if not 1.0 <= tempo <= MAX_TEMPO:
        raise AudioError("Only a single 1.00–1.10x pitch-preserving tempo correction is supported.")
    lead_in = number(lead_in, "narration lead-in")
    if lead_in and (tempo != 1 or base is not None):
        raise AudioError("A fixed music-only lead-in cannot be tempo-corrected or added twice.")
    source_meta = base if base is not None else raw
    source = from_relative(source_meta["audio"])
    inputs = {
        "version": VERSION, "operation": "normalized-voice", "requestFingerprint": raw["fingerprint"],
        "sourceSha256": source_meta["audioSha256"], "ffmpeg": ffmpeg_version, "tempo": tempo,
        "tempoPadSeconds": TEMPO_PAD if tempo > 1 else 0, "sampleRate": SAMPLE_RATE, "channels": 1,
        "targetLufs": VOICE_LUFS, "targetTruePeak": -3.0, "targetLra": 7.0, "edgeFadeSeconds": 0.004,
    }
    if lead_in:
        inputs["leadInSeconds"] = lead_in
    padding = raw.get("alignmentPaddingSeconds", 0)
    if padding:
        inputs["alignmentPaddingSeconds"] = padding
    stem = BUILD / "stems" / raw["id"] / fingerprint(inputs)
    audio, meta_path = stem.with_suffix(".wav"), stem.with_suffix(".json")
    meta = cached_artifact(audio, meta_path, fingerprint(inputs), immutable=False)
    words = retime_words(raw["words"], tempo)
    if lead_in:
        words = [{"word": word["word"], "start": word["start"] + lead_in, "end": word["end"] + lead_in}
                 for word in words]
    if meta:
        if meta.get("words") != words or meta.get("tempo") != tempo:
            raise AudioError("Cached normalized stem has inconsistent word timings.")
    else:
        if not generate:
            raise AudioError(f"Missing normalized {raw['id']} stem. Run plan --generate (local processing only).")
        filters = [f"aresample={SAMPLE_RATE}", "aformat=channel_layouts=mono"]
        if tempo > 1:
            # Flush WSOLA's trailing window instead of truncating the last phoneme.
            filters += [f"apad=pad_dur={TEMPO_PAD}", f"atempo={tempo:.9f}"]
        if lead_in:
            filters.append(f"adelay={round(lead_in * SAMPLE_RATE)}S:all=1")
        if padding and base is None:
            filters.append(f"apad=pad_len={round(padding * SAMPLE_RATE)}")
        filters += ["afade=t=in:d=0.004", "areverse", "afade=t=in:d=0.004", "areverse"]
        measured, normalization = normalize_audio(
            source, audio, channels=1, target=VOICE_LUFS, peak=-3.0, lra=7.0, prefix=",".join(filters),
        )
        validate_words(words, measured["duration"])
        meta = artifact_metadata(
            audio, inputs, measured, id=raw["id"], speaker=raw["speaker"], words=words, tempo=tempo,
            sourceAudio=relative(source), normalization=normalization, silenceTrim=None,
        )
        atomic_json(meta_path, meta)
    validate_words(words, meta["probe"]["duration"])
    return meta


def minimum_frames(durations, fps, *, gap=GAP, end_hold=END_HOLD):
    return [
        math.ceil((duration + (end_hold if index == len(durations) - 1 else gap)) * fps - 1e-9)
        for index, duration in enumerate(durations)
    ]


def choose_tempo(durations, *, seconds=118.0, fps=60, allow=False):
    total_frames = round(seconds * fps)
    if sum(minimum_frames(durations, fps)) <= total_frames:
        return 1.0

    def budget(tempo):
        return sum(minimum_frames([(duration + TEMPO_PAD) / tempo + TEMPO_MARGIN for duration in durations], fps))

    if budget(MAX_TEMPO) > total_frames:
        excess = (budget(MAX_TEMPO) - total_frames) / fps
        raise AudioError(
            f"Speech cannot fit without clipping, even at {MAX_TEMPO:.2f}x. "
            f"Shorten the approved narration by at least {excess * MAX_TEMPO:.2f}s of original-speed audio "
            f"({excess:.2f}s over budget after correction, including holds/flush margin). No text was changed."
        )
    low, high = 1.0, MAX_TEMPO
    for _ in range(60):
        middle = (low + high) / 2
        if budget(middle) <= total_frames:
            high = middle
        else:
            low = middle
    tempo = min(MAX_TEMPO, math.ceil(high * 1_000_000) / 1_000_000)
    if not allow:
        raise AudioError(
            f"The measured speech requires a uniform {tempo:.6f}x tempo correction. "
            "Explicitly use plan --allow-tempo --generate, or shorten the narration. No speech was clipped."
        )
    return tempo


def allocate_timeline(segments, durations, *, seconds=118.0, fps=60, fixed=False):
    if not segments or len(segments) != len(durations):
        raise AudioError("Every segment needs a measured speech duration.")
    durations = [number(duration, "speech duration", 1 / SAMPLE_RATE) for duration in durations]
    total_frames = round(seconds * fps)
    if abs(total_frames / fps - seconds) > 1e-9:
        raise AudioError("The film duration must be a whole number of frames.")
    minimum = minimum_frames(durations, fps)
    spare = total_frames - sum(minimum)
    if spare < 0:
        raise AudioError(
            f"Complete rendered speech and required holds exceed the film by {-spare / fps:.3f}s. "
            "Shorten narration; it will not be clipped or corrected a second time."
        )
    weights = [number(segment["targetSeconds"], "targetSeconds", 0.001) for segment in segments]
    if fixed:
        slots = [round(weight * fps) for weight in weights]
        if any(abs(frames / fps - weight) > 1e-9 for frames, weight in zip(slots, weights, strict=True)):
            raise AudioError("Fixed editorial slots must land on whole frames.")
        if sum(slots) != total_frames:
            raise AudioError("Fixed editorial slots must fill exactly the complete film.")
        for segment, frames, required in zip(segments, slots, minimum, strict=True):
            if frames < required:
                raise AudioError(
                    f"{segment['id']}: complete speech and its hold exceed the fixed slot "
                    f"by {(required - frames) / fps:.3f}s. Re-edit the slot or shorten the line; "
                    "no automatic speed-up or clipping is allowed."
                )
    else:
        weighted = [spare * weight / sum(weights) for weight in weights]
        extra = [math.floor(value) for value in weighted]
        order = sorted(range(len(segments)), key=lambda index: (-(weighted[index] - extra[index]), index))
        for index in order[:spare - sum(extra)]:
            extra[index] += 1
        slots = [floor + addition for floor, addition in zip(minimum, extra, strict=True)]
    clock, result = 0, []
    for index, segment in enumerate(segments):
        frames = slots[index]
        result.append({
            **copy.deepcopy(segment), "index": index, "start": clock / fps,
            "duration": frames / fps, "speech": durations[index],
        })
        clock += frames
    if clock != total_frames:
        raise AudioError("Internal frame allocation failed.")
    return result


def make_film(config, stems, terminal, tempo):
    segments = allocate_timeline(
        config["segments"], [stem["probe"]["duration"] for stem in stems],
        seconds=config["duration"], fps=config["fps"], fixed=config.get("timing") == "fixed",
    )
    for segment, stem in zip(segments, stems, strict=True):
        segment.update(audio=stem["audio"], words=copy.deepcopy(stem["words"]))
        validate_words(segment["words"], segment["speech"])
    return {
        "fps": config["fps"], "width": config["width"], "height": config["height"],
        "duration": config["duration"], "maxSeconds": config["maxSeconds"], "segments": segments,
        "terminal": copy.deepcopy(terminal),
        "edit": copy.deepcopy(config.get("edit", {})),
        "voices": {speaker: {"name": voice["name"]} for speaker, voice in config["voices"].items()},
        "audioPlan": {
            "version": VERSION, "tempo": tempo, "sampleRate": SAMPLE_RATE,
            "gapSeconds": GAP, "minimumEndHoldSeconds": END_HOLD,
            "narrationMonoLufs": VOICE_LUFS, "silenceTrim": None,
        },
    }


def plan(config, *, generate=False, allow_tempo=False):
    terminal = read_json(TERMINAL)
    if not isinstance(terminal, list) or not all(isinstance(line, str) for line in terminal):
        raise AudioError("The original terminal transcript must be a list of lines.")
    raws = voices(config, generate=False)
    version = tool_version()
    base = [
        normalized_voice(raw, generate=generate, ffmpeg_version=version, lead_in=segment.get("leadInSeconds", 0))
        for raw, segment in zip(raws, config["segments"], strict=True)
    ]
    tempo = 1.0 if config.get("timing") == "fixed" else choose_tempo(
        [stem["probe"]["duration"] for stem in base], seconds=config["duration"], fps=config["fps"], allow=allow_tempo,
    )
    if tempo > 1:
        print(f"Applying ONE uniform {tempo:.6f}x pitch-preserving correction; no dialogue is cut.", flush=True)
        stems = [
            normalized_voice(raw, generate=generate, ffmpeg_version=version, tempo=tempo, base=unretimed)
            for raw, unretimed in zip(raws, base, strict=True)
        ]
    else:
        stems = base
    film = make_film(config, stems, terminal, tempo)
    film_path, meta_path = output_path(BUILD / "film.json"), output_path(BUILD / "plan.json")
    record = {
        "version": VERSION, "configSha256": fingerprint(config), "terminalSha256": fingerprint(terminal),
        "filmSha256": fingerprint(film), "ffmpeg": version, "tempo": tempo,
        "rawSpeechSeconds": sum(raw["probe"]["duration"] for raw in raws),
        "unretimedSpeechSeconds": sum(stem["probe"]["duration"] for stem in base),
        "finalSpeechSeconds": sum(stem["probe"]["duration"] for stem in stems),
        "finalHoldSeconds": film["segments"][-1]["duration"] - film["segments"][-1]["speech"],
        "stems": [{"audio": stem["audio"], "fingerprint": stem["fingerprint"], "sha256": stem["audioSha256"]} for stem in stems],
    }
    if generate:
        atomic_json(film_path, film)
        atomic_json(meta_path, record)
    elif not film_path.is_file() or not meta_path.is_file() or read_json(film_path) != film or read_json(meta_path) != record:
        raise AudioError("The film plan is missing/stale. Use plan --generate to publish it locally.")
    print(f"plan    118.000s / 7080 frames / tempo {tempo:.6f}x / final hold {record['finalHoldSeconds']:.3f}s")
    for segment in film["segments"]:
        print(f"  {segment['id']} start={segment['start']:.3f} duration={segment['duration']:.3f} speech={segment['speech']:.3f}")
    return film


def load_film(config):
    film = read_json(output_path(BUILD / "film.json"))
    record = read_json(output_path(BUILD / "plan.json"))
    if (
        not isinstance(record, dict) or not isinstance(film, dict) or record.get("version") != VERSION
        or record.get("configSha256") != fingerprint(config) or record.get("filmSha256") != fingerprint(film)
    ):
        raise AudioError("The film plan is stale or modified. Run plan --generate before mixing.")
    if record.get("terminalSha256") != fingerprint(read_json(TERMINAL)):
        raise AudioError("The terminal transcript changed; republish the plan before mixing.")
    segments, stem_records = film.get("segments", []), record.get("stems", [])
    if len(segments) != len(config["segments"]) or len(segments) != len(stem_records):
        raise AudioError("The film/stem manifest is incomplete.")
    expected_start = 0.0
    for index, (segment, configured, stem_record) in enumerate(zip(segments, config["segments"], stem_records, strict=True)):
        if any(segment.get(key) != value for key, value in configured.items()):
            raise AudioError("A film segment no longer preserves its configured story/source window.")
        if abs(segment["start"] - expected_start) > 1e-8:
            raise AudioError("Film segments are not contiguous.")
        audio = from_relative(segment["audio"])
        meta = cached_artifact(audio, audio.with_suffix(".json"), stem_record["fingerprint"])
        if meta is None or meta["audioSha256"] != stem_record["sha256"] or stem_record["audio"] != segment["audio"]:
            raise AudioError("A planned narration stem is missing or modified.")
        synthesis_inputs, _ = speech_request(config, index)
        if meta["inputs"].get("requestFingerprint") != fingerprint(synthesis_inputs):
            raise AudioError("Voice identity or synthesis inputs changed. Refresh voices/plan before mixing.")
        if abs(meta["probe"]["duration"] - segment["speech"]) > 1 / SAMPLE_RATE or meta["words"] != segment["words"]:
            raise AudioError("The plan no longer matches the complete stem and its word timings.")
        if meta["probe"]["sampleRate"] != SAMPLE_RATE or meta["probe"]["channels"] != 1:
            raise AudioError("Planned narration must be normalized 48 kHz mono.")
        validate_words(segment["words"], segment["speech"])
        hold = END_HOLD if index == len(segments) - 1 else GAP
        if segment["speech"] + hold > segment["duration"] + 1e-8:
            raise AudioError("The plan would clip speech or its required following hold.")
        expected_start += segment["duration"]
    if abs(expected_start - 118.0) > 1e-8 or film.get("duration") != 118.0:
        raise AudioError("The planned film is not exactly 118 seconds.")
    return film, record


def normalized_music(raw, *, generate, ffmpeg_version):
    inputs = {
        "version": VERSION, "operation": "normalized-score", "sourceSha256": raw["audioSha256"],
        "requestFingerprint": raw["fingerprint"], "ffmpeg": ffmpeg_version,
        "targetLufs": MUSIC_LUFS, "targetTruePeak": -3.0, "targetLra": 9.0, "channels": 2, "sampleRate": SAMPLE_RATE,
    }
    audio = BUILD / "score" / f"normalized-{fingerprint(inputs)}.wav"
    meta_path = audio.with_suffix(".json")
    meta = cached_artifact(audio, meta_path, fingerprint(inputs), immutable=False)
    if not meta:
        if not generate:
            raise AudioError("No normalized stereo score. Run mix --generate (local processing only).")
        measured, normalization = normalize_audio(
            from_relative(raw["audio"]), audio, channels=2, target=MUSIC_LUFS, peak=-3.0, lra=9.0,
            prefix=f"aresample={SAMPLE_RATE},aformat=channel_layouts=stereo,highpass=f=28",
        )
        meta = artifact_metadata(audio, inputs, measured, normalization=normalization)
        atomic_json(meta_path, meta)
    return meta


def section_dynamics(config):
    if "musicDynamics" in config.get("edit", {}):
        sections = config["edit"]["musicDynamics"]
        clock = 0.0
        if not isinstance(sections, list) or not sections:
            raise AudioError("Editorial score dynamics need nonempty, explicit sections.")
        for section in sections:
            if abs(number(section.get("start"), "music start") - clock) > 1e-9:
                raise AudioError("Editorial score dynamics must be contiguous.")
            clock += number(section.get("duration"), "music duration", 0.001)
            gain = section.get("gainDb")
            if isinstance(gain, bool) or not isinstance(gain, (int, float)) or not math.isfinite(gain):
                raise AudioError("Each editorial music section needs a finite gainDb.")
        if abs(clock - config["duration"]) > 1e-9:
            raise AudioError("Editorial score dynamics must cover the full film.")
        return copy.deepcopy(sections)
    levels = {
        "Anticipation": -3.0, "The gateway": 0.0, "The evidence": -4.5,
        "The boundary": -2.5, "Open to agents": 0.5,
    }
    result, clock = [], 0.0
    for section in config["music"]["sections"]:
        if section["name"] not in levels:
            raise AudioError("A music section has no explicitly approved local mix dynamics.")
        result.append({"name": section["name"], "start": clock, "duration": section["seconds"], "gainDb": levels[section["name"]]})
        clock += section["seconds"]
    return result


def dynamics_expression(sections, final_speech_end):
    expression = f"{sections[0]['gainDb']:.6f}"
    for previous, current in zip(sections, sections[1:]):
        boundary = current["start"]
        width = min(0.7, previous["duration"] / 2, current["duration"] / 2)
        start, end = max(0.0, boundary - width / 2), boundary + width / 2
        ramp = f"{previous['gainDb']:.6f}+({current['gainDb'] - previous['gainDb']:.6f})*(t-{start:.6f})/{end-start:.6f}"
        expression = f"if(lt(t,{start:.6f}),({expression}),if(lt(t,{end:.6f}),({ramp}),{current['gainDb']:.6f}))"
    return f"pow(10,(({expression})+3*clip((t-{final_speech_end:.6f})/0.5,0,1))/20)"


def effect_events(film):
    by_id = {segment["id"]: segment for segment in film["segments"]}
    cues = [
        ("s01", "impact", 0.18, 0.7, 0.055, 0.0),
        ("s01", "tick", 3.35, 0.065, 0.028, -0.10),
        ("s01", "riser", 4.8, 1.7, 0.018, 0.0),
        ("s04", "impact", 0.03, 0.65, 0.060, 0.0),
        ("s12", "tick", 0.25, 0.055, 0.025, -0.12),
        ("s14", "tick", 0.12, 0.065, 0.023, 0.12),
        ("s16", "tick", 0.55, 0.045, 0.020, 0.08),
        ("s17", "impact", 0.15, 0.38, 0.028, -0.05),
        ("s21", "impact", 0.10, 0.65, 0.028, 0.0),
    ]
    events = []
    for ident, kind, offset, duration, gain, pan in cues:
        if ident in by_id:
            start = max(0.0, by_id[ident]["start"] + offset)
            if start + duration > film["duration"]:
                raise AudioError("A tactile cue would exceed the film.")
            events.append({"segment": ident, "kind": kind, "start": start, "duration": duration, "amplitude": gain, "pan": pan})
    return events


def synthesize_effects(path, duration, events):
    """Sparse, seeded, click-free cues; never download samples or touch old audio."""
    prepared = []
    for index, event in enumerate(events):
        rng = random.Random(0xA1_10 + index)
        count = round(event["duration"] * SAMPLE_RATE)
        samples = []
        for sample in range(count):
            t = sample / SAMPLE_RATE
            progress = sample / max(1, count - 1)
            envelope = math.sin(math.pi * progress) ** 2
            if event["kind"] == "tick":
                tone = (0.7 * math.sin(2 * math.pi * 1350 * t) + 0.3 * rng.uniform(-1, 1)) * math.exp(-45 * t)
            elif event["kind"] == "impact":
                tone = math.sin(2 * math.pi * (62 * t - 10 * t * t)) * math.exp(-5 * t)
            else:
                tone = (0.85 * math.sin(2 * math.pi * (260 * t + 240 * t * t)) + 0.15 * rng.uniform(-1, 1)) * progress
            samples.append(tone * envelope * event["amplitude"])
        left = math.sqrt((1 - event["pan"]) / 2)
        right = math.sqrt((1 + event["pan"]) / 2)
        prepared.append((round(event["start"] * SAMPLE_RATE), samples, left, right))
    with staged(path) as scratch:
        with wave.open(str(scratch), "wb") as stream:
            stream.setnchannels(2)
            stream.setsampwidth(2)
            stream.setframerate(SAMPLE_RATE)
            total = round(duration * SAMPLE_RATE)
            for start in range(0, total, 4096):
                count = min(4096, total - start)
                block = [0.0] * (count * 2)
                for event_start, samples, left, right in prepared:
                    first = max(start, event_start)
                    last = min(start + count, event_start + len(samples))
                    for position in range(first, last):
                        sample = samples[position - event_start]
                        offset = (position - start) * 2
                        block[offset] += sample * left
                        block[offset + 1] += sample * right
                pcm = array("h", [round(max(-1.0, min(1.0, value)) * 32767) for value in block])
                if sys.byteorder != "little":
                    pcm.byteswap()
                stream.writeframes(pcm.tobytes())
        os.replace(scratch, output_path(path))


def effects(film, *, generate):
    events = effect_events(film)
    inputs = {"version": VERSION, "operation": "tactile-effects", "duration": film["duration"], "sampleRate": SAMPLE_RATE,
              "seed": 0xA1_10, "events": events}
    audio = BUILD / "effects" / f"{fingerprint(inputs)}.wav"
    meta_path = audio.with_suffix(".json")
    meta = cached_artifact(audio, meta_path, fingerprint(inputs), immutable=False)
    if not meta:
        if not generate:
            raise AudioError("No cached tactile effects. Run mix --generate (entirely local synthesis).")
        synthesize_effects(audio, film["duration"], events)
        meta = artifact_metadata(audio, inputs, probe_audio(audio), events=events)
        atomic_json(meta_path, meta)
    return meta


def mix_graph(film, dynamics):
    total = round(film["duration"] * SAMPLE_RATE)
    chains, labels = [], []
    for index, segment in enumerate(film["segments"]):
        delay = round(segment["start"] * SAMPLE_RATE)
        if delay + round(segment["speech"] * SAMPLE_RATE) > total:
            raise AudioError("Refusing to trim a narration stem at the film boundary.")
        chains.append(
            f"[{index}:a]aresample={SAMPLE_RATE},aformat=channel_layouts=mono,"
            f"asetpts=PTS-STARTPTS,adelay={delay}S:all=1[v{index}]"
        )
        labels.append(f"[v{index}]")
    count = len(labels)
    chains.append(
        f"{''.join(labels)}amix=inputs={count}:normalize=0:dropout_transition=0,"
        f"apad=whole_len={total},atrim=end_sample={total},asplit=2[narration][sidechain]"
    )
    # Explicit stereo BEFORE amix prevents its first (mono) input collapsing the score.
    chains.append("[narration]pan=stereo|FL=c0|FR=c0[centered]")
    speech_end = film["segments"][-1]["start"] + film["segments"][-1]["speech"]
    expression = dynamics_expression(dynamics, speech_end)
    fade_start = max(0, film["duration"] - 1.2)
    chains.append(
        f"[{count}:a]aresample={SAMPLE_RATE},aformat=channel_layouts=stereo,asetpts=PTS-STARTPTS,"
        f"apad=whole_len={total},atrim=end_sample={total},volume='{expression}':eval=frame,"
        f"afade=t=in:d=0.45,afade=t=out:st={fade_start:.9f}:d=1.2[bed]"
    )
    chains.append(
        "[bed][sidechain]sidechaincompress=threshold=0.03:ratio=4:attack=15:release=320:"
        "knee=4:link=maximum:detection=rms:makeup=1[ducked]"
    )
    chains.append(f"[{count + 1}:a]aresample={SAMPLE_RATE},aformat=channel_layouts=stereo[fx]")
    chains.append(
        f"[centered][ducked][fx]amix=inputs=3:normalize=0:dropout_transition=0,apad=whole_len={total},"
        f"atrim=end_sample={total},aformat=sample_rates={SAMPLE_RATE}:channel_layouts=stereo[mix]"
    )
    return ";".join(chains)


def verify_master(audio, duration):
    measured = probe_audio(audio, decode=True)
    if measured["channels"] != 2 or measured["sampleRate"] != SAMPLE_RATE:
        raise AudioError("Final mix is not stereo 48 kHz.")
    if abs(measured["duration"] - duration) > 1 / SAMPLE_RATE:
        raise AudioError("Final audio is not exactly the planned duration.")
    loudness = measure_loudness(audio)
    if abs(float(loudness["input_i"]) - MASTER_LUFS) > 0.35:
        raise AudioError(f"Final loudness {loudness['input_i']} LUFS is outside the -16 LUFS tolerance.")
    if float(loudness["input_tp"]) > MASTER_TP + 0.1:
        raise AudioError(f"Final WAV true peak {loudness['input_tp']} dBTP leaves insufficient AAC headroom (target -2.0).")
    if float(loudness["input_lra"]) > 8.0:
        raise AudioError(f"Final loudness range {loudness['input_lra']} LU is not suitably restrained.")
    return measured, loudness


def mix(config, *, generate=False):
    film, plan_record = load_film(config)
    raw_music = music(config, generate=False)
    version = tool_version()
    score = normalized_music(raw_music, generate=generate, ffmpeg_version=version)
    tactile = effects(film, generate=generate)
    dynamics = section_dynamics(config)
    graph = mix_graph(film, dynamics)
    inputs = {
        "version": VERSION, "operation": "cinematic-mix", "filmSha256": fingerprint(film),
        "stems": plan_record["stems"], "scoreSha256": score["audioSha256"], "effectsSha256": tactile["audioSha256"],
        "graph": graph, "ffmpeg": version, "masterLufs": MASTER_LUFS, "masterTruePeak": MASTER_TP,
        "masterLra": MASTER_LRA, "sampleRate": SAMPLE_RATE, "channels": 2,
    }
    expected = fingerprint(inputs)
    rendered = BUILD / "renders" / f"{expected}.wav"
    metadata = rendered.with_suffix(".json")
    meta = cached_artifact(rendered, metadata, expected, immutable=False)
    if meta is None:
        if not generate:
            raise AudioError("No matching rendered mix. Run mix --generate (no provider requests).")
        sources = [from_relative(segment["audio"]) for segment in film["segments"]]
        sources += [from_relative(score["audio"]), from_relative(tactile["audio"])]
        input_arguments = [argument for source in sources for argument in ("-i", str(source))]
        premaster = BUILD / "renders" / f"{expected}.premaster.wav"
        with staged(premaster) as scratch:
            ffmpeg(
                "-v", "error", *input_arguments, "-filter_complex", graph, "-map", "[mix]",
                "-ar", SAMPLE_RATE, "-ac", 2, "-c:a", "pcm_f32le", scratch,
            )
            os.replace(scratch, output_path(premaster))
        measured, normalization = normalize_audio(
            premaster, rendered, channels=2, target=MASTER_LUFS, peak=MASTER_TP, lra=MASTER_LRA,
            prefix=f"aformat=sample_rates={SAMPLE_RATE}:channel_layouts=stereo",
        )
        measured, verified = verify_master(rendered, film["duration"])
        meta = artifact_metadata(
            rendered, inputs, measured, normalization=normalization, verifiedLoudness=verified,
            dynamics=dynamics, effects=tactile["events"], scoreRequestFingerprint=raw_music["fingerprint"],
            scoreDurationAdjustmentSeconds=film["duration"] - score["probe"]["duration"],
            premaster={"audio": relative(premaster), "sha256": sha256(premaster)},
            createdAt=timestamp(),
        )
        atomic_json(metadata, meta)
    final, final_meta = output_path(BUILD / "mix.wav"), output_path(BUILD / "mix.json")
    published = {**meta, "audio": relative(final), "renderAudio": relative(rendered)}
    if generate:
        if not final.is_file() or sha256(final) != meta["audioSha256"]:
            atomic_copy(rendered, final)
        atomic_json(final_meta, published)
    elif not final.is_file() or not final_meta.is_file() or read_json(final_meta) != published or sha256(final) != meta["audioSha256"]:
        raise AudioError("mix.wav is missing/stale. Run mix --generate to publish the verified local render.")
    measured = meta["verifiedLoudness"]
    print(f"mix     118.000s / stereo 48000 Hz / {measured['input_i']} LUFS / {measured['input_tp']} dBTP")
    return published


def availability(config, *, timeout=20):
    key = api_key()
    for speaker, voice in config["voices"].items():
        identity = voice_identity(config, speaker)
        _, provider = provider_request(
            f"voices/{urllib.parse.quote(identity, safe='')}", None, key, timeout=timeout,
            operation=f"Availability of {voice['name']}", max_bytes=2 << 20,
        )
        print(f"{voice['name']}: available (HTTP {provider['httpStatus']}; personal voice metadata not displayed)")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    for name, help_text in (
        ("voices", "verify/synthesize timestamped speech; paid only with --generate"),
        ("plan", "publish an exact-length plan and normalized stems; entirely local"),
        ("music", "verify/commission ONE original instrumental score"),
        ("mix", "render, duck and master stereo audio; entirely local"),
        ("probe", "read-only voice availability, without displaying personal metadata"),
    ):
        command = commands.add_parser(name, help=help_text)
        if name != "probe":
            command.add_argument("--generate", action="store_true", help="authorize missing output generation; otherwise cache-only")
        if name in ("voices", "music", "probe"):
            default = {"voices": 120, "music": 600, "probe": 20}[name]
            command.add_argument("--timeout", type=float, default=default, help=f"HTTP timeout in seconds (default {default}); no retries")
        if name == "voices":
            command.add_argument("--only", nargs="+", metavar="SEGMENT_ID", help="pilot segments, e.g. s01 s02 (commas also accepted)")
        if name == "plan":
            command.add_argument("--allow-tempo", action="store_true", help="explicitly permit one reported uniform correction, at most 1.10x")
    args = parser.parse_args(argv)
    try:
        config = validate_config(read_json(CONFIG))
        if hasattr(args, "timeout") and (not math.isfinite(args.timeout) or args.timeout <= 0 or args.timeout > 1800):
            raise AudioError("HTTP timeout must be positive and at most 1800 seconds.")
        if args.command == "voices":
            only = [part for item in args.only for part in item.split(",") if part] if args.only else None
            voices(config, only=only, generate=args.generate, timeout=args.timeout)
        elif args.command == "music":
            music(config, generate=args.generate, timeout=args.timeout)
        elif args.command == "plan":
            plan(config, generate=args.generate, allow_tempo=args.allow_tempo)
        elif args.command == "mix":
            mix(config, generate=args.generate)
        else:
            availability(config, timeout=args.timeout)
    except AudioError as exc:
        print(f"Audio error: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"Audio error: local I/O failed ({type(exc).__name__}). No automatic provider retry.", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("Interrupted. Any started paid request remains journaled; no automatic retry.", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
