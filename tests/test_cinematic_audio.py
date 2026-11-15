"""Offline checks only: provider access is disabled even when testing --generate."""

import base64
import copy
import importlib.util
import json
import math
import shutil
import subprocess
import sys
import uuid
from array import array
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("cinematic_audio", ROOT / "video" / "cinematic" / "audio.py")
audio = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audio)


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("A test attempted an unmocked provider request")

    monkeypatch.setattr(audio, "provider_request", forbidden)
    monkeypatch.setenv("ELEVENLABS_API_KEY", "offline-test-key")
    monkeypatch.setenv("ELEVENLABS_VOICE_ID", "offline-test-krish")
    monkeypatch.setenv("ELEVENLABS_VOICE_JAKUB", "offline-test-jakub")


@pytest.fixture
def config():
    return copy.deepcopy(audio.read_json(ROOT / "video" / "cinematic" / "config.json"))


@pytest.fixture
def build(monkeypatch):
    # Never use the OS temporary directory or the original film's caches.
    directory = Path("video/build/cinematic") / f"audio-test-{uuid.uuid4().hex}"
    directory.mkdir(parents=True)
    monkeypatch.setattr(audio, "BUILD", directory.resolve())
    try:
        yield directory.resolve()
    finally:
        shutil.rmtree(directory)


def require_ffmpeg():
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("FFmpeg and ffprobe are required for offline audio integration")


def tone(path, duration=2.0, *, stereo=False):
    require_ffmpeg()
    expression = "0.025*sin(2*PI*211*t)|0.035*sin(2*PI*509*t)" if stereo else "0.07*sin(2*PI*997*t)"
    audio.ffmpeg(
        "-v", "error", "-f", "lavfi", "-i", f"aevalsrc={expression}:s=48000:d={duration}",
        "-c:a", "libmp3lame" if path.suffix == ".mp3" else "pcm_s24le", path,
    )
    return path


def raw_meta(path, ident="s21", duration=None):
    measured = audio.probe_audio(path)
    duration = measured["duration"] if duration is None else duration
    inputs = {"test": ident}
    return audio.artifact_metadata(
        path, inputs, measured, id=ident, speaker="krish",
        words=[{"word": "Final", "start": 0.03, "end": 0.7},
               {"word": "terms.", "start": duration - 0.5, "end": duration - 0.01}],
    )


def test_allocation_preserves_speech_and_source_windows(config):
    durations = [2.0] * len(config["segments"])
    durations[-1] = 8.0  # Longer than its design weight: it must never be clipped.
    stems = [
        {"probe": {"duration": duration}, "audio": f"stems/{segment['id']}/example.wav",
         "words": [{"word": "complete", "start": 0.1, "end": duration - 0.01}]}
        for segment, duration in zip(config["segments"], durations, strict=True)
    ]
    original = copy.deepcopy(config)
    terminal = ["Original terminal line"]
    film = audio.make_film(config, stems, terminal, 1.0)
    assert config == original
    assert film["terminal"] == terminal
    assert film["voices"] == {"krish": {"name": "Krish"}, "jakub": {"name": "Jakub"}}
    assert sum(round(segment["duration"] * 60) for segment in film["segments"]) == 7080
    for configured, segment in zip(config["segments"], film["segments"], strict=True):
        assert all(segment[key] == value for key, value in configured.items())
        assert math.isclose(segment["start"] * 60, round(segment["start"] * 60), abs_tol=1e-8)
        assert segment["words"][-1]["end"] < segment["speech"] <= segment["duration"]
    last = film["segments"][-1]
    assert last["start"] + last["speech"] + 1.3 <= 118.0 + 1e-9
    assert math.isclose(last["start"] + last["duration"], 118.0)


def test_extra_frames_follow_design_weights_after_measured_minimums():
    segments = [{"id": "a", "targetSeconds": 1}, {"id": "b", "targetSeconds": 3}]
    durations = [3.0, 7.0]
    allocated = audio.allocate_timeline(segments, durations)
    minimum = audio.minimum_frames(durations, 60)
    extras = [round(segment["duration"] * 60) - floor for segment, floor in zip(allocated, minimum, strict=True)]
    assert abs(extras[1] - extras[0] * 3) <= 3
    assert sum(round(segment["duration"] * 60) for segment in allocated) == 7080


def test_tempo_requires_consent_and_retimes_every_word():
    durations = [5.5] * 21
    with pytest.raises(audio.AudioError, match="Explicitly use plan --allow-tempo"):
        audio.choose_tempo(durations)
    tempo = audio.choose_tempo(durations, allow=True)
    assert 1 < tempo <= 1.10
    predicted = [(duration + audio.TEMPO_PAD) / tempo + audio.TEMPO_MARGIN for duration in durations]
    allocated = audio.allocate_timeline([{"targetSeconds": 1}] * 21, predicted)
    words = [{"word": "Do", "start": 0.2, "end": 1.0}, {"word": "not clip.", "start": 4.9, "end": 5.49}]
    shifted = audio.retime_words(words, tempo)
    for before, after in zip(words, shifted, strict=True):
        assert after["start"] == pytest.approx(before["start"] / tempo)
        assert after["end"] == pytest.approx(before["end"] / tempo)
    assert shifted[-1]["end"] < predicted[-1]
    assert allocated[-1]["speech"] + 1.3 <= allocated[-1]["duration"]
    with pytest.raises(audio.AudioError, match="Shorten the approved narration"):
        audio.choose_tempo([6.5] * 21, allow=True)


def test_millisecond_alignment_rounding_does_not_reject_complete_audio():
    words = [{"word": "one.", "start": 2.647, "end": 3.019}]
    audio.validate_words(words, 3.01859410430839)
    assert words[0]["end"] == 3.019
    with pytest.raises(audio.AudioError, match="outside"):
        audio.validate_words([{**words[0], "end": 3.020}], 3.01859410430839)


def test_fingerprint_tracks_voice_settings_text_and_same_speaker_context(config, monkeypatch):
    config["segments"][1]["speaker"] = "krish"
    baseline, _ = audio.speech_request(config, 0)
    assert baseline["request"]["next_text"] == config["segments"][1]["text"]
    serialized = json.dumps(baseline)
    assert "offline-test-krish" not in serialized
    assert "offline-test-key" not in serialized
    for mutate in (
        lambda changed: changed["segments"][0].update(text="Changed opening."),
        lambda changed: changed["segments"][1].update(text="Changed continuation."),
        lambda changed: changed["voiceSettings"].update(stability=0.6),
        lambda changed: changed.update(model="a-different-model"),
    ):
        changed = copy.deepcopy(config)
        mutate(changed)
        request, _ = audio.speech_request(changed, 0)
        assert audio.fingerprint(request) != audio.fingerprint(baseline)
    monkeypatch.setenv("ELEVENLABS_VOICE_ID", "different-offline-identity")
    changed, _ = audio.speech_request(config, 0)
    assert audio.fingerprint(changed) != audio.fingerprint(baseline)


def test_voice_cache_never_repeats_paid_request_and_detects_corruption(config, build, monkeypatch):
    encoded = base64.b64encode(tone(build / "fixture.mp3", 1.2).read_bytes()).decode()
    calls = []

    def response(endpoint, body, key, **kwargs):
        calls.append(body)
        chars = list(body["text"])
        starts = [index * 0.8 / len(chars) for index in range(len(chars))]
        ends = [(index + 1) * 0.8 / len(chars) for index in range(len(chars))]
        return audio.canonical({
            "audio_base64": encoded,
            "alignment": {"characters": chars, "character_start_times_seconds": starts,
                          "character_end_times_seconds": ends},
        }), {"httpStatus": 200}

    monkeypatch.setattr(audio, "provider_request", response)
    with pytest.raises(audio.AudioError, match="use --generate"):
        audio.voices(config, only=["s01"])
    assert not calls
    first = audio.voices(config, only=["s01"], generate=True)
    second = audio.voices(config, only=["s01"], generate=True)
    assert first == second
    assert len(calls) == 1
    saved = audio.from_relative(first[0]["audio"])
    saved.write_bytes(saved.read_bytes() + b"corrupted")
    with pytest.raises(audio.AudioError, match="checksum"):
        audio.voices(config, only=["s01"], generate=True)
    assert len(calls) == 1


@pytest.mark.parametrize("command", ["voices", "music"])
def test_timeout_journal_blocks_paid_retry(config, build, monkeypatch, command):
    calls = []
    monkeypatch.setattr(audio, "require_audio_tools", lambda: None)

    def timeout(*args, **kwargs):
        calls.append(True)
        raise audio.AudioError("Provider timed out; completion unknown")

    monkeypatch.setattr(audio, "provider_request", timeout)
    kwargs = {"only": ["s01"]} if command == "voices" else {}
    generate = getattr(audio, command)
    with pytest.raises(audio.AudioError, match="timed out"):
        generate(config, generate=True, **kwargs)
    with pytest.raises(audio.AudioError, match="earlier request|already attempted"):
        generate(config, generate=True, **kwargs)
    assert len(calls) == 1
    journals = list(build.rglob("*attempt.json"))
    assert len(journals) == 1
    assert audio.read_json(journals[0])["state"] == "failed_or_unknown"


def test_music_request_is_single_instrumental_plan_and_mismatch_is_explicit(config, build):
    request = audio.music_request(config)
    sections = request["composition_plan"]["sections"]
    assert sum(section["duration_ms"] for section in sections) == 118_000
    assert all(section["lines"] == [] for section in sections)
    inputs = {"version": audio.VERSION, "provider": "elevenlabs", "operation": "music",
              "outputFormat": audio.OUTPUT_FORMAT, "request": request}
    audio.atomic_json(build / "score" / "request.json", inputs)
    config["music"]["positive_global_styles"].append("A changed composition")
    with pytest.raises(audio.AudioError, match="Refusing to commission a second composition"):
        audio.music(config, generate=True)


def test_alignment_rejects_missing_or_out_of_bounds_final_word():
    with pytest.raises(audio.AudioError, match="inconsistent lengths"):
        audio.words_from_alignment(
            {"characters": ["x", "y"], "character_start_times_seconds": [0], "character_end_times_seconds": [1]}, "xy",
        )
    with pytest.raises(audio.AudioError, match="outside the complete audio"):
        audio.validate_words([{"word": "last", "start": 0.8, "end": 1.1}], 1.0)


def test_plan_cache_rejects_changed_identity_config_and_film(config, build, monkeypatch):
    config["segments"] = config["segments"][:2]
    payload = tone(build / "fixture.mp3", 2.0).read_bytes()
    for index, segment in enumerate(config["segments"]):
        inputs, _ = audio.speech_request(config, index)
        raw, meta_path, _ = audio.voice_paths(segment["id"], audio.fingerprint(inputs))
        characters = list(segment["text"])
        alignment = {
            "characters": characters,
            "character_start_times_seconds": [i / len(characters) for i in range(len(characters))],
            "character_end_times_seconds": [(i + 1) / len(characters) for i in range(len(characters))],
        }
        response = raw.with_suffix(".response.json")
        audio.atomic_bytes(raw, payload)
        audio.atomic_json(response, {"audio_base64": base64.b64encode(payload).decode(), "alignment": alignment})
        meta = audio.artifact_metadata(
            raw, inputs, audio.probe_audio(raw), id=segment["id"], speaker=segment["speaker"],
            words=audio.words_from_alignment(alignment, segment["text"]), responseSha256=audio.sha256(response),
        )
        audio.atomic_json(meta_path, meta)
    terminal = build / "terminal-fixture.json"
    audio.atomic_json(terminal, ["Read-only transcript fixture"])
    monkeypatch.setattr(audio, "TERMINAL", terminal)
    planned = audio.plan(config, generate=True)
    assert audio.plan(config) == planned
    assert audio.load_film(config)[0] == planned
    with monkeypatch.context() as altered:
        altered.setenv("ELEVENLABS_VOICE_ID", "another-offline-identity")
        with pytest.raises(audio.AudioError, match="Voice identity or synthesis inputs changed"):
            audio.load_film(config)
    changed = copy.deepcopy(config)
    changed["segments"][0]["text"] += " New dialogue."
    with pytest.raises(audio.AudioError, match="stale or modified"):
        audio.load_film(changed)
    planned["segments"][-1]["speech"] = 0.1
    audio.atomic_json(build / "film.json", planned)
    with pytest.raises(audio.AudioError, match="stale or modified"):
        audio.load_film(config)


def test_local_tempo_stereo_graph_and_two_pass_master(build):
    require_ffmpeg()
    version = audio.tool_version()
    raw = raw_meta(tone(build / "source.wav"), duration=2.0)
    stem = audio.normalized_voice(raw, generate=True, ffmpeg_version=version, tempo=1.08)
    assert stem["probe"]["sampleRate"] == 48000
    assert stem["probe"]["channels"] == 1
    assert stem["words"][-1]["end"] == pytest.approx(1.99 / 1.08)
    assert stem["probe"]["duration"] > stem["words"][-1]["end"]
    assert stem["silenceTrim"] is None

    duration = 7.0
    stereo = tone(build / "stereo.wav", duration, stereo=True)
    raw_score = audio.artifact_metadata(stereo, {"test": "music"}, audio.probe_audio(stereo))
    score = audio.normalized_music(raw_score, generate=True, ffmpeg_version=version)
    silent_effects = build / "silent-effects.wav"
    audio.synthesize_effects(silent_effects, duration, [])
    film = {"duration": duration, "segments": [
        {"id": "s04", "start": 0.0, "duration": 3.5, "speech": stem["probe"]["duration"]},
        {"id": "s21", "start": 3.5, "duration": 3.5, "speech": stem["probe"]["duration"]},
    ]}
    graph = audio.mix_graph(film, [{"name": "Test", "start": 0.0, "duration": duration, "gainDb": -3.0}])
    premaster = build / "premaster.wav"
    sources = [audio.from_relative(stem["audio"])] * 2 + [audio.from_relative(score["audio"]), silent_effects]
    arguments = [argument for source in sources for argument in ("-i", str(source))]
    audio.ffmpeg("-v", "error", *arguments, "-filter_complex", graph, "-map", "[mix]",
                 "-ar", 48000, "-ac", 2, "-c:a", "pcm_f32le", premaster)
    master = build / "master.wav"
    _, normalization = audio.normalize_audio(
        premaster, master, channels=2, target=audio.MASTER_LUFS, peak=audio.MASTER_TP, lra=audio.MASTER_LRA,
    )
    measured, loudness = audio.verify_master(master, duration)
    assert measured["duration"] == duration
    assert normalization["secondPass"]["normalization_type"] in ("linear", "dynamic")
    assert abs(float(loudness["input_i"]) + 16) <= 0.35
    assert float(loudness["input_tp"]) <= -1.9
    decoded = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(master), "-f", "f32le", "-c:a", "pcm_f32le", "-"],
        check=True, capture_output=True,
    ).stdout
    samples = array("f")
    samples.frombytes(decoded)
    if sys.byteorder != "little":
        samples.byteswap()
    difference_rms = math.sqrt(sum((left - right) ** 2 for left, right in zip(samples[::2], samples[1::2], strict=True))
                               / (len(samples) // 2))
    assert difference_rms > 0.001  # Centered narration plus silence cannot create this stereo difference.
