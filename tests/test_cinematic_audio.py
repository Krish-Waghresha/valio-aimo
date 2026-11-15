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
    config["timing"] = "weighted"
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


def test_fixed_edit_preserves_chapter_times_and_rejects_spillover():
    segments = [
        {"id": "opening", "targetSeconds": 11},
        {"id": "architecture", "targetSeconds": 28},
        {"id": "evidence", "targetSeconds": 70},
        {"id": "close", "targetSeconds": 9},
    ]
    for durations in ([10, 27, 40, 6], [3, 12, 65, 6]):
        timeline = audio.allocate_timeline(segments, durations, fixed=True)
        assert [segment["start"] for segment in timeline] == [0, 11, 39, 109]
        assert [segment["duration"] for segment in timeline] == [11, 28, 70, 9]
    with pytest.raises(audio.AudioError, match="architecture:.*fixed slot"):
        audio.allocate_timeline(segments, [3, 28, 40, 6], fixed=True)
    segments[-1]["targetSeconds"] = 8
    with pytest.raises(audio.AudioError, match="fill exactly"):
        audio.allocate_timeline(segments, [3, 12, 40, 6], fixed=True)


def test_delivery_tags_do_not_enter_captions_or_move_spoken_timestamps():
    delivery = "[confident, upbeat]"
    text = "Choose butter, [verified]."
    tagged = delivery + " " + text
    alignment = {
        "characters": list(tagged),
        "character_start_times_seconds": [index * .02 for index in range(len(tagged))],
        "character_end_times_seconds": [(index + 1) * .02 for index in range(len(tagged))],
    }
    words = audio.words_from_alignment(alignment, text, delivery=delivery)
    assert [word["word"] for word in words] == ["Choose", "butter,", "[verified]."]
    assert words[0]["start"] == pytest.approx((len(delivery) + 1) * .02)
    assert words[-1]["end"] == pytest.approx(len(tagged) * .02)
    with pytest.raises(audio.AudioError, match="does not match"):
        audio.words_from_alignment(alignment, text, delivery="[shouting]")


def test_v4_punctuation_pause_is_not_a_spoken_word_overrun():
    alignment = {
        "characters": list("agent."),
        "character_start_times_seconds": [3.367, 3.431, 3.495, 3.559, 3.623, 3.687],
        "character_end_times_seconds": [3.431, 3.495, 3.559, 3.623, 3.687, 4.007],
    }
    words = audio.words_from_alignment(alignment, "agent.", exclude_pause_timing=True)
    assert words == [{"word": "agent.", "start": 3.367, "end": 3.687}]
    audio.validate_words(words, 4.0)
    with pytest.raises(audio.AudioError, match="outside"):
        audio.validate_words(words, 3.68)


def test_v4_clock_overhang_gets_bounded_pcm_padding_not_rewritten_words():
    measured = {"duration": 9.28, "codec": "mp3", "sampleRate": 44100}
    words = [{"word": "basket.", "start": 8.845, "end": 9.285}]
    padding = audio.alignment_padding(words, measured, "eleven_v4")
    assert padding == pytest.approx(.005 + 1 / 48000)
    audio.validate_words(words, measured["duration"] + padding)
    assert words[0]["end"] == 9.285
    with pytest.raises(audio.AudioError, match="more than one MP3 frame"):
        audio.alignment_padding([{**words[0], "end": 9.4}], measured, "eleven_v4")
    with pytest.raises(audio.AudioError, match="more than one MP3 frame"):
        audio.alignment_padding(words, measured, "eleven_multilingual_v2")


def test_reading_hold_cannot_accelerate_the_demo(config):
    audio.validate_config(config)
    milk = next(segment for segment in config["segments"] if segment["id"] == "s09")
    milk["visual"]["holdEndSeconds"] = 2
    with pytest.raises(audio.AudioError, match="accelerate the recorded demo"):
        audio.validate_config(config)


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


def test_adjacent_context_and_high_quality_format_are_opt_in(config):
    for index, speaker in enumerate(("krish", "jakub", "krish")):
        config["segments"][index]["speaker"] = speaker
    original, _ = audio.speech_request(config, 1)
    assert "previous_text" not in original["request"] and "next_text" not in original["request"]
    config.update(contextMode="adjacent", outputFormat="mp3_44100_192")
    requested, _ = audio.speech_request(config, 1)
    assert requested["request"]["previous_text"] == config["segments"][0]["text"]
    assert requested["request"]["next_text"] == config["segments"][2]["text"]
    assert requested["outputFormat"] == "mp3_44100_192"
    assert audio.fingerprint(requested) != audio.fingerprint(original)
    config["outputFormat"] = "mp3_44100_192&unexpected=option"
    with pytest.raises(audio.AudioError, match="outputFormat"):
        audio.speech_request(config, 1)


def test_high_quality_format_reaches_the_synthesis_endpoint(config, build, monkeypatch):
    config["segments"] = [{**config["segments"][0], "text": "A brief test."}]
    config["outputFormat"] = "mp3_44100_192"
    payload = tone(build / "fixture.mp3", 2.0).read_bytes()
    text = config["segments"][0]["text"]
    requested = []

    def respond(endpoint, body, key, **kwargs):
        requested.append(endpoint)
        alignment = {
            "characters": list(text),
            "character_start_times_seconds": [index * .05 for index in range(len(text))],
            "character_end_times_seconds": [(index + 1) * .05 for index in range(len(text))],
        }
        return json.dumps({"audio_base64": base64.b64encode(payload).decode(), "alignment": alignment}).encode(), {}

    monkeypatch.setattr(audio, "provider_request", respond)
    audio.voices(config, generate=True)
    assert len(requested) == 1 and requested[0].endswith("?output_format=mp3_44100_192")


def test_voice_cache_never_repeats_paid_request_and_detects_corruption(config, build, monkeypatch):
    first_segment = copy.deepcopy(config["segments"][0])
    config["segments"] = [first_segment, config["segments"][1], {**first_segment, "id": "repeat"}]
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
    first = audio.voices(config, only=["s01", "repeat"], generate=True)
    second = audio.voices(config, only=["s01", "repeat"], generate=True)
    assert first == second
    assert first[0]["audio"] == first[1]["audio"]
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
    config["timing"] = "weighted"
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
            words=audio.words_from_alignment(alignment, segment["text"], exclude_pause_timing=True),
            responseSha256=audio.sha256(response),
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
    delayed = audio.normalized_voice(raw, generate=True, ffmpeg_version=version, lead_in=2)
    assert delayed["probe"]["duration"] == pytest.approx(4.0, abs=1 / 48000)
    assert delayed["words"][0]["start"] == pytest.approx(raw["words"][0]["start"] + 2)
    assert delayed["words"][-1]["end"] == pytest.approx(raw["words"][-1]["end"] + 2)
    leading = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(audio.from_relative(delayed["audio"])),
         "-t", "1.9", "-f", "s16le", "-c:a", "pcm_s16le", "-"],
        check=True, capture_output=True,
    ).stdout
    assert leading and not any(leading)
    overhanging = {**raw, "words": [*raw["words"][:-1], {**raw["words"][-1], "end": 2.005}],
                   "alignmentPaddingSeconds": .005 + 1 / 48000}
    padded = audio.normalized_voice(overhanging, generate=True, ffmpeg_version=version)
    assert padded["probe"]["duration"] == pytest.approx(2.005 + 1 / 48000, abs=1 / 48000)
    assert padded["words"][-1]["end"] == 2.005

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
