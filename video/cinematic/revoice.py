#!/usr/bin/env python3
"""Replace only the original film's narrators, keeping its picture and music.

Run with --env-file .env.cinematic. Only `voices --generate` can spend.
Voice Changer preserves the existing performances, without expressive tags or
style exaggeration. Raw conversions and attempt journals are immutable.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from video import build as original_build  # noqa: E402
from video.cinematic import audio  # noqa: E402


VIDEO = Path(__file__).resolve().parents[1]
WORK = audio.BUILD / "original-revoice"
ORIGINAL = VIDEO / "build" / "final.mp4"
FINAL = VIDEO / "build" / "final-conversational.mp4"
ORIGINAL_SHA256 = "b4b5f21d1795ba3e83c49ee77e37478ea31bf6a6b8e7b5208d2d8c506327716d"
MODEL = "eleven_multilingual_sts_v2"
SETTINGS = {"stability": 0.5, "similarity_boost": 0.75, "style": 0.0, "use_speaker_boost": True}
VOICES = {"voices": {speaker: {"env": env} for speaker, env in audio.VOICE_ENVS.items()}}


def video_identity(path):
    report = audio.run_tool([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_data_hash", "sha256", "-show_entries",
        "stream=codec_name,profile,width,height,pix_fmt,time_base,duration_ts,nb_frames,extradata_hash:"
        "packet=pts,dts,duration,size,flags,data_hash",
        "-of", "json", str(path),
    ])
    document = json.loads(report.stdout)
    if len(document.get("streams", [])) != 1 or not document.get("packets"):
        raise audio.AudioError("Expected one complete video stream, including packet timestamps and hashes.")
    return {
        "stream": document["streams"][0], "packets": len(document["packets"]),
        "sha256": audio.fingerprint(document),
    }


def pcm_digest(path):
    return audio.ffmpeg(
        "-v", "error", "-i", path, "-map", "0:a:0", "-ar", "48000", "-ac", "1",
        "-c:a", "pcm_s16le", "-f", "hash", "-hash", "sha256", "-",
    ).stdout.strip()


def pipeline_identity():
    return {
        module: audio.sha256(Path(path))
        for module, path in (
            ("revoice", __file__), ("audio", audio.__file__), ("original_build", original_build.__file__),
        )
    }


def source_plan():
    if not ORIGINAL.is_file() or audio.sha256(ORIGINAL) != ORIGINAL_SHA256:
        raise audio.AudioError("The original final.mp4 changed or is missing; nothing will be replaced.")
    config = audio.read_json(VIDEO / "config.json")
    segments, total = original_build.timeline(config)
    picture = video_identity(ORIGINAL)
    if picture["packets"] != round(total * config["fps"]) or not 0 < total < 119:
        raise audio.AudioError("Original narration timing does not match the locked picture.")
    entries = []
    for segment in segments:
        ident = segment["id"]
        if segment["speaker"] not in audio.VOICE_ENVS or not isinstance(ident, str) or not ident.isalnum():
            raise audio.AudioError("Invalid original narrator or segment identifier.")
        source = VIDEO / "build" / "audio" / f"{ident}.mp3"
        metadata = audio.read_json(source.with_suffix(".json"))
        if metadata["text"] != segment["text"] or metadata["speaker"] != segment["speaker"]:
            raise audio.AudioError(f"{ident}: original narration metadata differs from the original script.")
        entries.append({
            "id": ident, "speaker": segment["speaker"], "text": segment["text"],
            "start": segment["start"], "duration": segment["duration"], "speech": segment["speech"],
            "delayMs": int(segment["start"] * 1000), "words": segment["words"],
            "sourceSha256": audio.sha256(source), "sourceMetadataSha256": audio.sha256(source.with_suffix(".json")),
        })
    plan = {
        "sourceMovieSha256": ORIGINAL_SHA256, "picture": picture, "duration": total,
        "sourceConfigSha256": audio.sha256(VIDEO / "config.json"), "segments": entries,
        "musicSha256": audio.sha256(VIDEO / "build" / "music.mp3"),
        "originalMixSha256": audio.sha256(VIDEO / "build" / "mix.wav"),
        "loudnessLufs": config["loudnessLufs"], "musicVolumeDb": config["music"]["volumeDb"],
    }
    audio.atomic_json(WORK / "source.json", plan)
    return plan


def multipart(fields, source):
    boundary = "revoice-" + uuid.uuid4().hex
    parts = [
        f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode()
        for key, value in fields.items()
    ]
    parts += [
        f'--{boundary}\r\nContent-Disposition: form-data; name="audio"; filename="narration.mp3"\r\n'
        "Content-Type: audio/mpeg\r\n\r\n".encode(),
        source.read_bytes(), f"\r\n--{boundary}--\r\n".encode(),
    ]
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def conversion_recipe(segment):
    identity = audio.voice_identity(VOICES, segment["speaker"])
    inputs = {
        "operation": "original-film-voice-change", "version": 1,
        "sourceSha256": segment["sourceSha256"], "text": segment["text"],
        "speaker": segment["speaker"], "voiceIdentitySha256": hashlib.sha256(identity.encode()).hexdigest(),
        "model": MODEL, "settings": SETTINGS, "outputFormat": audio.OUTPUT_FORMAT,
        "removeBackgroundNoise": False,
    }
    stem = WORK / "voices" / segment["id"] / audio.fingerprint(inputs)
    return identity, inputs, stem.with_suffix(".mp3")


def converted_voice(segment, *, generate=False):
    identity, inputs, path = conversion_recipe(segment)
    metadata = path.with_suffix(".json")
    journal = path.with_suffix(".attempt.json")
    cached = audio.cached_artifact(path, metadata, audio.fingerprint(inputs))
    if cached:
        return cached
    if journal.exists():
        raise audio.AudioError(f"{segment['id']}: previous conversion attempt needs review; no retry is allowed.")
    if not generate:
        raise audio.AudioError(f"{segment['id']}: missing conversion; voices --generate authorizes it.")
    audio.require_audio_tools()
    source = VIDEO / "build" / "audio" / f"{segment['id']}.mp3"
    if audio.sha256(source) != segment["sourceSha256"]:
        raise audio.AudioError("The source narration changed after preflight.")
    fields = {
        "model_id": MODEL, "voice_settings": json.dumps(SETTINGS),
        "remove_background_noise": "false", "file_format": "other",
    }
    body, content_type = multipart(fields, source)
    print(f"Converting {segment['id']} / {segment['speaker']} (one paid attempt)", flush=True)
    with audio.paid_attempt(journal, inputs) as attempt:
        result, provider = audio.provider_request(
            f"voice-changer/{identity}?output_format={audio.OUTPUT_FORMAT}",
            body, audio.api_key(), timeout=180, operation=f"Original narration {segment['id']}",
            content_type=content_type,
        )
        attempt["provider"] = provider
        audio.atomic_bytes(path, result)
        measured = audio.probe_audio(path, decode=True)
        cached = audio.artifact_metadata(
            path, inputs, measured, id=segment["id"], speaker=segment["speaker"],
            provider=provider, createdAt=audio.timestamp(),
        )
        audio.atomic_json(metadata, cached)
    return cached


def original_music(plan):
    """Rebuild the old ducking with the old voice as an inaudible sidechain."""
    inputs, chains, labels = [], [], []
    for index, segment in enumerate(plan["segments"]):
        source = VIDEO / "build" / "audio" / f"{segment['id']}.mp3"
        gain = plan["loudnessLufs"] - original_build.loudness(source)
        inputs += ["-i", source]
        chains.append(
            f"[{index}:a]aresample=48000,volume={gain:.2f}dB,"
            f"adelay={segment['delayMs']}:all=1[v{index}]"
        )
        labels.append(f"[v{index}]")
    total, count = plan["duration"], len(labels)
    chains += [
        f"{''.join(labels)}amix=inputs={count}:normalize=0,apad,atrim=duration={total:.3f}[voice]",
        f"[{count}:a]aresample=48000,volume={plan['musicVolumeDb']}dB,atrim=duration={total:.3f},"
        f"afade=t=in:d=0.6,afade=t=out:st={total - 2.5:.2f}:d=2.5[m]",
        "[voice]asplit=2[vo][key]",
        "[m][key]sidechaincompress=threshold=0.03:ratio=4:attack=25:release=350[duck]",
        "[duck]asplit=2[bed][check]",
        "[vo][check]amix=inputs=2:normalize=0,alimiter=limit=0.95[reconstructed]",
    ]
    inputs += ["-i", VIDEO / "build" / "music.mp3"]
    bed, reference = WORK / "original-music.wav", WORK / "original-mix-reference.wav"
    with audio.staged(bed) as bed_part, audio.staged(reference) as reference_part:
        audio.ffmpeg(
            "-v", "error", *inputs, "-filter_complex", ";".join(chains),
            "-map", "[bed]", "-ar", "48000", "-ac", "1", "-c:a", "pcm_f32le", bed_part,
            "-map", "[reconstructed]", "-ar", "48000", "-c:a", "pcm_s16le", reference_part,
        )
        expected, actual = pcm_digest(VIDEO / "build" / "mix.wav"), pcm_digest(reference_part)
        if actual != expected:
            raise audio.AudioError("The reconstructed original mix differs; do not generate new voices yet.")
        bed_part.replace(audio.output_path(bed))
        reference_part.replace(audio.output_path(reference))
    proof = {"source": plan, "originalPcmHash": expected, "musicStemSha256": audio.sha256(bed)}
    audio.atomic_json(WORK / "original-music.json", proof)
    return bed


def fitted_voice(segment, raw, target_lufs):
    source = VIDEO / "build" / "audio" / f"{segment['id']}.mp3"
    decoded_original = WORK / "stems" / f"{segment['id']}-original.wav"
    with audio.staged(decoded_original) as scratch:
        audio.ffmpeg("-v", "error", "-i", source, "-ar", "48000", "-ac", "1", "-c:a", "pcm_s24le", scratch)
        scratch.replace(audio.output_path(decoded_original))
    target = audio.probe_audio(decoded_original)["duration"]
    decoded = WORK / "stems" / f"{segment['id']}-converted.wav"
    with audio.staged(decoded) as scratch:
        audio.ffmpeg(
            "-v", "error", "-i", audio.from_relative(raw["audio"]),
            "-ar", "48000", "-ac", "1", "-c:a", "pcm_s24le", scratch,
        )
        scratch.replace(audio.output_path(decoded))
    duration = audio.probe_audio(decoded)["duration"]
    ratio = duration / target
    if not 0.95 <= ratio <= 1.05:
        raise audio.AudioError(f"{segment['id']}: conversion changed duration by over 5%; review before mixing.")
    tempo = ratio if abs(duration - target) > 0.04 else 1.0
    prefix = "anull" if tempo == 1 else f"apad=pad_dur=0.12,atempo={tempo:.12f}"
    path = WORK / "stems" / f"{segment['id']}.wav"
    measured, normalization = audio.normalize_audio(
        decoded, path, channels=1, target=target_lufs, peak=-3, lra=11, prefix=prefix,
    )
    if measured["duration"] > segment["duration"] - 0.02:
        raise audio.AudioError(f"{segment['id']}: complete voice would overlap the next scene; no audio was cut.")
    metadata = {
        "id": segment["id"], "audio": audio.relative(path), "sha256": audio.sha256(path),
        "conversionFingerprint": raw["fingerprint"], "probe": measured,
        "originalDecodedSeconds": target, "convertedDecodedSeconds": duration,
        "tempo": tempo, "normalization": normalization, "speechTrimmed": False,
    }
    audio.atomic_json(path.with_suffix(".json"), metadata)
    return metadata


def original_music_path(plan):
    music = WORK / "original-music.wav"
    proof = audio.read_json(WORK / "original-music.json")
    if proof["source"] != plan or proof["musicStemSha256"] != audio.sha256(music):
        raise audio.AudioError("Original music provenance changed; run prepare again.")
    return music


def mix_stems(plan, stems, music, path):
    inputs, chains, labels = [], [], []
    for index, (segment, stem) in enumerate(zip(plan["segments"], stems, strict=True)):
        inputs += ["-i", audio.from_relative(stem["audio"])]
        chains.append(f"[{index}:a]adelay={segment['delayMs']}:all=1[n{index}]")
        labels.append(f"[n{index}]")
    count = len(stems)
    inputs += ["-i", music]
    chains += [
        f"{''.join(labels)}amix=inputs={count}:normalize=0,apad,atrim=duration={plan['duration']:.3f}[voice]",
        f"[voice][{count}:a]amix=inputs=2:normalize=0,"
        "alimiter=limit=0.794328:level=false:latency=true,"
        f"apad,atrim=duration={plan['duration']:.3f}[out]",
    ]
    with audio.staged(path) as scratch:
        audio.ffmpeg(
            "-v", "error", *inputs, "-filter_complex", ";".join(chains),
            "-map", "[out]", "-ar", "48000", "-ac", "1", "-c:a", "pcm_s24le", scratch,
        )
        measured = audio.probe_audio(scratch, decode=True)
        if abs(measured["duration"] - plan["duration"]) > 1 / audio.SAMPLE_RATE:
            raise audio.AudioError("The replacement soundtrack does not fill the original exact timeline.")
        levels = audio.measure_loudness(scratch)
        if not -18 <= float(levels["input_i"]) <= -14 or float(levels["input_tp"]) > -1.5:
            raise audio.AudioError("Replacement mix loudness/peak needs review before export.")
        scratch.replace(audio.output_path(path))
    metadata = {
        "source": plan, "stems": stems, "musicStemSha256": audio.sha256(music),
        "audioSha256": audio.sha256(path), "probe": measured, "loudness": levels,
        "oldNarrationAudible": False, "newMusicGenerated": False, "pipeline": pipeline_identity(),
    }
    audio.atomic_json(path.with_suffix(".json"), metadata)
    return path


def mix(plan):
    music = original_music_path(plan)
    raw = [converted_voice(segment) for segment in plan["segments"]]
    stems = [
        fitted_voice(segment, recording, plan["loudnessLufs"])
        for segment, recording in zip(plan["segments"], raw, strict=True)
    ]
    return mix_stems(plan, stems, music, WORK / "mix.wav")


def mux_copy(source, soundtrack, destination, duration):
    if destination.resolve() == source.resolve() or destination.is_symlink():
        raise audio.AudioError("The original movie cannot be overwritten or replaced through a symlink.")
    expected = video_identity(source)
    with audio.staged(WORK / "export.mp4") as scratch:
        audio.ffmpeg(
            "-v", "error", "-i", source, "-i", soundtrack,
            "-map", "0:v:0", "-map", "1:a:0", "-map_metadata", "0",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "1",
            "-t", f"{duration:.3f}", "-movflags", "+faststart", scratch,
        )
        if video_identity(scratch) != expected:
            raise audio.AudioError("Video packets or timestamps changed; the export was not published.")
        measured = audio.probe_audio(scratch, decode=True)
        if abs(measured["duration"] - duration) > 1 / audio.SAMPLE_RATE:
            raise audio.AudioError("Encoded audio duration differs from the original movie.")
        levels = audio.measure_loudness(scratch)
        if not -18 <= float(levels["input_i"]) <= -14 or float(levels["input_tp"]) > -1.5:
            raise audio.AudioError("Encoded soundtrack loudness/peak failed; the export was not published.")
        scratch.replace(destination)
    return {
        "video": expected, "duration": duration, "audio": measured, "loudness": levels,
        "sha256": audio.sha256(destination), "bytes": destination.stat().st_size,
    }


def export(plan):
    path = WORK / "mix.wav"
    metadata = audio.read_json(WORK / "mix.json")
    if metadata["source"] != plan or metadata["audioSha256"] != audio.sha256(path):
        raise audio.AudioError("Replacement soundtrack provenance is stale; run mix before export.")
    if metadata.get("pipeline") != pipeline_identity():
        raise audio.AudioError("Audio production code changed; run mix before export.")
    if len(metadata["stems"]) != len(plan["segments"]):
        raise audio.AudioError("The soundtrack has an incomplete narrator list.")
    for segment, stem in zip(plan["segments"], metadata["stems"], strict=True):
        _, inputs, _ = conversion_recipe(segment)
        if stem["id"] != segment["id"] or stem["conversionFingerprint"] != audio.fingerprint(inputs):
            raise audio.AudioError("Selected voices or conversion settings changed; run voices and mix before export.")
    report_path = WORK / "verification.json"
    if FINAL.exists():
        if not report_path.exists() or audio.read_json(report_path).get("sha256") != audio.sha256(FINAL):
            raise audio.AudioError("An unrecognized final-conversational.mp4 already exists; it was not overwritten.")
    report = mux_copy(ORIGINAL, path, FINAL, plan["duration"])
    if audio.sha256(ORIGINAL) != ORIGINAL_SHA256:
        raise audio.AudioError("The original movie changed during export.")
    report.update(
        sourceMovieSha256=ORIGINAL_SHA256, pictureUnchanged=True,
        scriptUnchanged=True, originalMusicPreserved=True, model=MODEL, pipeline=metadata["pipeline"],
        mixSha256=metadata["audioSha256"], sourceConfigSha256=plan["sourceConfigSha256"],
        stems=metadata["stems"],
    )
    audio.atomic_json(report_path, report)
    print(f"Final: {FINAL}\n{plan['duration']:.3f}s; all {report['video']['packets']} video packets unchanged.")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "voices", "mix", "export"))
    parser.add_argument("--generate", action="store_true", help="Authorize uncached paid voice conversions only")
    parser.add_argument("--only", nargs="+", help="Original segment IDs for voice conversion")
    args = parser.parse_args()
    audio.require_audio_tools()
    plan = source_plan()
    if args.command == "prepare":
        original_music(plan)
        print(f"Original {plan['duration']:.3f}s picture, script and music verified; no provider request made.")
    elif args.command == "voices":
        proof = audio.read_json(WORK / "original-music.json")
        if proof["source"] != plan:
            raise audio.AudioError("Prepare the original audio before any paid conversion.")
        identities = {audio.voice_identity(VOICES, speaker) for speaker in audio.VOICE_ENVS}
        if len(identities) != 2:
            raise audio.AudioError("Two distinct trained voices are required.")
        selected = set(args.only or [segment["id"] for segment in plan["segments"]])
        if selected - {segment["id"] for segment in plan["segments"]}:
            raise audio.AudioError("Unknown original segment ID.")
        for segment in plan["segments"]:
            if segment["id"] in selected:
                recording = converted_voice(segment, generate=args.generate)
                print(f"{segment['id']}: {recording['probe']['duration']:.3f}s", flush=True)
    elif args.command == "mix":
        mix(plan)
        print(f"Replacement soundtrack: {WORK / 'mix.wav'}")
    else:
        export(plan)


if __name__ == "__main__":
    try:
        main()
    except audio.AudioError as error:
        raise SystemExit(f"Revoice error: {error}") from None
