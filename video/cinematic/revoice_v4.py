#!/usr/bin/env python3
"""Fresh v4 speech for the original locked-picture film; no rewritten dialogue.

Use .env.cinematic for the two trained voices. Only voices --generate can spend.
V4 supports stability and similarity, not style or speaker-boost controls.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from video.cinematic import audio, revoice  # noqa: E402


WORK = audio.BUILD / "original-v4"
FINAL = revoice.VIDEO / "build" / "final-v4.mp4"
SILENCE_DB = -55
MAX_TEMPO = 1.30
FLUSH_SECONDS = 0.12


def make_config(plan):
    return {
        "model": "eleven_v4", "outputFormat": "mp3_44100_192", "contextMode": "adjacent",
        "voiceSettings": {"stability": 0.45, "similarity_boost": 0.75},
        "voices": {
            speaker: {"name": speaker.capitalize(), "env": env}
            for speaker, env in audio.VOICE_ENVS.items()
        },
        "segments": [
            {"id": segment["id"], "speaker": segment["speaker"], "text": segment["text"].replace("[pause]", "...")}
            for segment in plan["segments"]
        ],
    }


def verify_format(recording):
    path = audio.from_relative(recording["audio"])
    if audio.sha256(path) != recording["audioSha256"]:
        raise audio.AudioError("Raw narration no longer matches its immutable synthesis record.")
    result = audio.run_tool([
        "ffprobe", "-v", "error", "-select_streams", "a:0",
        "-show_entries", "stream=codec_name,sample_rate,bit_rate", "-of", "json", str(path),
    ])
    stream = json.loads(result.stdout)["streams"][0]
    if stream.get("codec_name") != "mp3" or stream.get("sample_rate") != "44100" or stream.get("bit_rate") != "192000":
        raise audio.AudioError("Provider audio does not match the requested mp3_44100_192; no fallback was used.")


def pipeline_identity():
    return {**revoice.pipeline_identity(), "v4": audio.sha256(Path(__file__))}


def decode(source, destination, padding=0.0):
    filters = ["aresample=48000"]
    if padding:
        filters.append(f"apad=pad_len={round(padding * audio.SAMPLE_RATE)}")
    with audio.staged(destination) as scratch:
        audio.ffmpeg(
            "-v", "error", "-i", source, "-af", ",".join(filters),
            "-ar", "48000", "-ac", "1", "-c:a", "pcm_s24le", scratch,
        )
        measured = audio.probe_audio(scratch, decode=True)
        scratch.replace(audio.output_path(destination))
    return measured


def silence_intervals(path):
    report = audio.ffmpeg(
        "-v", "info", "-i", path, "-af", f"silencedetect=noise={SILENCE_DB}dB:duration=0.10",
        "-f", "null", "-",
    ).stderr
    intervals, start = [], None
    for kind, value in re.findall(r"silence_(start|end):\s*([\d.eE+-]+)", report):
        seconds = audio.number(float(value), "silence boundary")
        if kind == "start":
            if start is not None:
                raise audio.AudioError("Overlapping silence detector intervals.")
            start = seconds
        else:
            if start is None or seconds <= start:
                raise audio.AudioError("Incomplete silence detector interval.")
            intervals.append((start, seconds))
            start = None
    if start is not None:
        raise audio.AudioError("Silence detection did not finish; no pause edits were made.")
    return intervals


def pause_candidates(words, original_words, quiet, original_quiet, duration):
    if [word["word"] for word in words] != [word["word"].replace("[pause]", "...") for word in original_words]:
        raise audio.AudioError("Fresh narration wording differs from the original; nothing will be fitted.")
    candidates = []
    for start, end in quiet:
        if start < 0.03:
            keep, reason = 0.04, "leading silence"
        elif duration - end < 0.06:
            keep, reason = 0.08, "trailing silence"
        else:
            distance, index = min(
                ((abs(word["start"] - end), index) for index, word in enumerate(words) if index),
                default=(math.inf, 0),
            )
            if distance > 0.20 or start < words[index - 1]["start"]:
                continue
            reference = [
                (abs(right - original_words[index]["start"]), right - left)
                for left, right in original_quiet
                if abs(right - original_words[index]["start"]) <= 0.20
            ]
            keep = max(0.12, min(reference)[1] if reference else 0.0)
            reason = f"pause before word {index + 1}"
        capacity = math.floor((end - start - keep) * audio.SAMPLE_RATE)
        if capacity >= round(0.04 * audio.SAMPLE_RATE):
            candidates.append({
                "quietStart": start, "quietEnd": end, "keepSeconds": keep,
                "capacitySamples": capacity, "reason": reason,
            })
    return candidates


def fitting_plan(samples, target_samples, candidates):
    remaining_capacity = sum(item["capacitySamples"] for item in candidates)
    remaining = min(max(0, samples - target_samples), remaining_capacity)
    cuts = []
    for candidate in candidates:
        capacity = candidate["capacitySamples"]
        take = remaining * capacity // remaining_capacity if remaining_capacity else 0
        if take:
            center = round((candidate["quietStart"] + candidate["quietEnd"]) * audio.SAMPLE_RATE / 2)
            start = center - take // 2
            cuts.append({**candidate, "startSample": start, "endSample": start + take})
        remaining -= take
        remaining_capacity -= capacity
    if remaining:
        raise audio.AudioError("Pause allocation failed; no speech was edited.")
    removed = sum(cut["endSample"] - cut["startSample"] for cut in cuts)
    if samples - removed <= target_samples:
        tempo = 1.0
    else:
        tempo = (samples - removed + round(FLUSH_SECONDS * audio.SAMPLE_RATE)) / (
            target_samples - round(0.02 * audio.SAMPLE_RATE)
        )
    if tempo > MAX_TEMPO:
        raise audio.AudioError(
            f"Even after reducing verified pauses, this line needs {tempo:.3f}x tempo "
            f"(limit {MAX_TEMPO:.2f}x). No speech was clipped or regenerated."
        )
    return cuts, tempo


def cut_pauses(source, destination, cuts):
    if not cuts:
        return source, 0.0
    with wave.open(str(source), "rb") as stream:
        if (stream.getnchannels(), stream.getsampwidth(), stream.getframerate()) != (1, 3, audio.SAMPLE_RATE):
            raise audio.AudioError("Pause editing requires the decoded 48 kHz mono PCM source.")
        samples = stream.getnframes()
        data = memoryview(stream.readframes(samples))
    maximum = 0
    fragments, cursor = [], 0
    for cut in cuts:
        start, end = cut["startSample"], cut["endSample"]
        if not cursor < start < end < samples:
            raise audio.AudioError("Pause cuts overlap or leave the decoded narration.")
        for offset in range(start * 3, end * 3, 3):
            maximum = max(maximum, abs(int.from_bytes(data[offset:offset + 3], "little", signed=True)))
        fragments.append((cursor, start))
        cursor = end
    fragments.append((cursor, samples))
    peak = maximum / 2**23
    if peak > 10 ** (SILENCE_DB / 20) + 1 / 2**23:
        raise audio.AudioError("A proposed pause cut contains audible samples; it was rejected.")
    chains, labels = [], []
    for index, (start, end) in enumerate(fragments):
        filters = [f"atrim=start_sample={start}:end_sample={end}", "asetpts=PTS-STARTPTS"]
        # Both splice edges remain inside verified quiet; tiny fades avoid a discontinuity.
        if index:
            filters.append("afade=t=in:d=0.003")
        if index < len(fragments) - 1:
            filters.append(f"afade=t=out:st={(end - start) / audio.SAMPLE_RATE - 0.003:.9f}:d=0.003")
        chains.append(f"[0:a]{','.join(filters)}[part{index}]")
        labels.append(f"[part{index}]")
    chains.append(f"{''.join(labels)}concat=n={len(labels)}:v=0:a=1[out]")
    with audio.staged(destination) as scratch:
        audio.ffmpeg(
            "-v", "error", "-i", source, "-filter_complex", ";".join(chains),
            "-map", "[out]", "-ar", "48000", "-ac", "1", "-c:a", "pcm_s24le", scratch,
        )
        expected = samples - sum(cut["endSample"] - cut["startSample"] for cut in cuts)
        measured = audio.probe_audio(scratch)
        if round(measured["duration"] * audio.SAMPLE_RATE) != expected:
            raise audio.AudioError("The pause edit changed samples outside its explicit cut list.")
        scratch.replace(audio.output_path(destination))
    return destination, peak


def mapped_time(seconds, cuts, tempo):
    removed = sum(
        max(0.0, min(seconds, cut["endSample"] / audio.SAMPLE_RATE) - cut["startSample"] / audio.SAMPLE_RATE)
        for cut in cuts
    )
    return (seconds - removed) / tempo


def fitted_voice(segment, recording, target_lufs, *, final=False):
    verify_format(recording)
    decoded, original = WORK / "stems" / f"{segment['id']}-decoded.wav", WORK / "stems" / f"{segment['id']}-original.wav"
    measured = decode(
        audio.from_relative(recording["audio"]), decoded, recording.get("alignmentPaddingSeconds", 0),
    )
    source = revoice.VIDEO / "build" / "audio" / f"{segment['id']}.mp3"
    if audio.sha256(source) != segment["sourceSha256"]:
        raise audio.AudioError("Original narration changed after preflight.")
    decode(source, original)
    quiet, original_quiet = silence_intervals(decoded), silence_intervals(original)
    candidates = pause_candidates(recording["words"], segment["words"], quiet, original_quiet, measured["duration"])
    samples = round(measured["duration"] * audio.SAMPLE_RATE)
    target_samples = math.floor((segment["duration"] - (0.65 if final else 0.07)) * audio.SAMPLE_RATE)
    if target_samples <= round(0.02 * audio.SAMPLE_RATE):
        raise audio.AudioError("The original scene leaves no valid narration window.")
    try:
        cuts, tempo = fitting_plan(samples, target_samples, candidates)
    except audio.AudioError as error:
        raise audio.AudioError(f"{segment['id']}: {error}") from None
    paused, removed_peak = cut_pauses(decoded, decoded.with_name(f"{segment['id']}-pauses.wav"), cuts)
    prefix = "anull" if tempo == 1 else f"apad=pad_dur={FLUSH_SECONDS},atempo={tempo:.12f}"
    destination = WORK / "stems" / f"{segment['id']}.wav"
    fitted, normalization = audio.normalize_audio(
        paused, destination, channels=1, target=target_lufs, peak=-3, lra=11, prefix=prefix,
    )
    if fitted["duration"] > target_samples / audio.SAMPLE_RATE + 0.02:
        raise audio.AudioError(f"{segment['id']}: complete fitted narration exceeds its original scene.")
    words = [
        {**word, "start": mapped_time(word["start"], cuts, tempo), "end": mapped_time(word["end"], cuts, tempo)}
        for word in recording["words"]
    ]
    audio.validate_words(words, fitted["duration"])
    metadata = {
        "id": segment["id"], "speaker": segment["speaker"],
        "audio": audio.relative(destination), "sha256": audio.sha256(destination), "probe": fitted,
        "synthesisFingerprint": recording["fingerprint"], "rawSha256": recording["audioSha256"],
        "rawSeconds": measured["duration"], "originalSlotSeconds": segment["duration"],
        "words": words, "tempo": tempo, "silenceCuts": cuts, "silenceThresholdDb": SILENCE_DB,
        "maximumRemovedAmplitude": removed_peak, "speechTrimmed": False, "normalization": normalization,
        "maximumWordStartDifference": max(
            abs(new["start"] - old["start"]) for new, old in zip(words, segment["words"], strict=True)
        ),
    }
    audio.atomic_json(destination.with_suffix(".json"), metadata)
    print(
        f"Fitted {segment['id']}: {measured['duration']:.3f}s -> {fitted['duration']:.3f}s; "
        f"{tempo:.4f}x tempo; {len(cuts)} verified pause cuts",
        flush=True,
    )
    return metadata


def mix(plan, config):
    recordings = audio.voices(config)
    music = revoice.original_music_path(plan)
    stems = [
        fitted_voice(segment, recording, plan["loudnessLufs"], final=index == len(recordings) - 1)
        for index, (segment, recording) in enumerate(zip(plan["segments"], recordings, strict=True))
    ]
    path = revoice.mix_stems(plan, stems, music, WORK / "mix.wav")
    metadata = audio.read_json(path.with_suffix(".json"))
    metadata.update(pipeline=pipeline_identity(), config=config)
    audio.atomic_json(path.with_suffix(".json"), metadata)
    return path


def export(plan, config):
    soundtrack = WORK / "mix.wav"
    metadata = audio.read_json(soundtrack.with_suffix(".json"))
    if (
        metadata.get("source") != plan or metadata.get("config") != config
        or metadata.get("pipeline") != pipeline_identity()
        or metadata.get("audioSha256") != audio.sha256(soundtrack)
    ):
        raise audio.AudioError("V4 soundtrack provenance changed; run mix before export.")
    if len(metadata["stems"]) != len(plan["segments"]):
        raise audio.AudioError("V4 soundtrack has an incomplete narrator list.")
    for index, stem in enumerate(metadata["stems"]):
        inputs, _ = audio.speech_request(config, index)
        if stem["id"] != plan["segments"][index]["id"] or stem["synthesisFingerprint"] != audio.fingerprint(inputs):
            raise audio.AudioError("V4 voices or synthesis settings changed; regenerate the matching mix.")
    proof = WORK / "verification.json"
    if FINAL.exists() and (not proof.exists() or audio.read_json(proof).get("sha256") != audio.sha256(FINAL)):
        raise audio.AudioError("An unrecognized final-v4.mp4 exists and will not be overwritten.")
    report = revoice.mux_copy(revoice.ORIGINAL, soundtrack, FINAL, plan["duration"])
    if audio.sha256(revoice.ORIGINAL) != revoice.ORIGINAL_SHA256:
        raise audio.AudioError("Original final.mp4 changed during export.")
    report.update(
        sourceMovieSha256=revoice.ORIGINAL_SHA256, pictureUnchanged=True, scriptUnchanged=True,
        originalMusicPreserved=True, config=config, pipeline=metadata["pipeline"],
        mixSha256=metadata["audioSha256"], stems=metadata["stems"],
        unsupportedRequestedControls=["style", "use_speaker_boost"],
    )
    audio.atomic_json(proof, report)
    print(f"Final: {FINAL}\n{plan['duration']:.3f}s; all {report['video']['packets']} video packets unchanged.")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("voices", "inspect", "fit", "mix", "export"))
    parser.add_argument("--generate", action="store_true", help="Authorize uncached paid narration only")
    parser.add_argument("--only", nargs="+", help="Original segment IDs")
    args = parser.parse_args()
    if args.generate and args.command != "voices":
        raise audio.AudioError("--generate is only valid for the voices command.")
    plan = revoice.source_plan()
    config = make_config(plan)
    audio.atomic_json(WORK / "source.json", plan)
    audio.atomic_json(WORK / "config.json", config)
    if len({audio.voice_identity(config, speaker) for speaker in config["voices"]}) != 2:
        raise audio.AudioError("The two distinct saved voice IDs are required.")
    if args.command in ("mix", "export"):
        if args.only or args.generate:
            raise audio.AudioError("mix/export are complete-film local operations; omit --only and --generate.")
        if args.command == "mix":
            mix(plan, config)
        else:
            export(plan, config)
        return
    recordings = audio.voices(config, only=args.only, generate=args.generate if args.command == "voices" else False)
    slots = {segment["id"]: segment for segment in plan["segments"]}
    for recording in recordings:
        verify_format(recording)
        slot = slots[recording["id"]]
        if args.command == "fit":
            fitted_voice(slot, recording, plan["loudnessLufs"], final=slot["id"] == plan["segments"][-1]["id"])
            continue
        print(
            f"{recording['id']} / {slot['speaker']}: raw {recording['probe']['duration']:.3f}s; "
            f"speech {recording['words'][0]['start']:.3f}-{recording['words'][-1]['end']:.3f}s; "
            f"original slot {slot['duration']:.3f}s; verified 192 kbps",
            flush=True,
        )


if __name__ == "__main__":
    try:
        main()
    except audio.AudioError as error:
        raise SystemExit(f"Original v4 error: {error}") from None
