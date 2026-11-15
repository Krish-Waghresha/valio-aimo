"""The voice-only edit must never redraw the film or retain the old narration."""

import copy
import io
import math
import shutil
import subprocess
import sys
import uuid
from array import array
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from video.cinematic import revoice, revoice_v4  # noqa: E402


audio = revoice.audio
PROVIDER_REQUEST = audio.provider_request


@pytest.fixture
def work(monkeypatch):
    directory = (Path("video/build/cinematic") / f"revoice-test-{uuid.uuid4().hex}").resolve()
    (directory / "build" / "audio").mkdir(parents=True)
    monkeypatch.setattr(audio, "BUILD", directory)
    monkeypatch.setattr(revoice, "WORK", directory / "output")
    monkeypatch.setattr(revoice, "VIDEO", directory)
    monkeypatch.setattr(revoice_v4, "WORK", directory / "v4")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "offline-test-key")
    monkeypatch.setenv("ELEVENLABS_VOICE_ID", "offline-krish")
    monkeypatch.setenv("ELEVENLABS_VOICE_JAKUB", "offline-jakub")

    def forbidden(*args, **kwargs):
        raise AssertionError("An unmocked paid request was attempted")

    monkeypatch.setattr(audio, "provider_request", forbidden)
    try:
        yield directory
    finally:
        shutil.rmtree(directory)


def require_ffmpeg():
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("FFmpeg and ffprobe are required for offline media tests")


def test_multipart_transport_preserves_audio_bytes(work, monkeypatch):
    source = work / "test.mp3"
    source.write_bytes(b"\x00\xff\x81audio\x00")
    payload, content_type = revoice.multipart({"model_id": "test-model"}, source)
    requests = []

    class Response(io.BytesIO):
        status = 200
        headers = {}

    class Opener:
        def open(self, request, timeout):
            requests.append(request)
            return Response(b"converted-audio")

    monkeypatch.setattr(audio.urllib.request, "build_opener", lambda *args: Opener())
    result, provider = PROVIDER_REQUEST(
        "voice-changer/offline-voice", payload, "offline-key",
        timeout=10, operation="offline test", content_type=content_type,
    )
    assert result == b"converted-audio" and provider["httpStatus"] == 200
    assert requests[0].data == payload and source.read_bytes() in payload
    assert requests[0].get_header("Content-type") == content_type


def test_failed_conversion_cannot_be_paid_twice(work, monkeypatch):
    source = work / "build" / "audio" / "s01.mp3"
    source.write_bytes(b"retained original")
    segment = {"id": "s01", "speaker": "krish", "text": "Same words.", "sourceSha256": audio.sha256(source)}
    calls = []

    def failed(*args, **kwargs):
        calls.append(1)
        raise audio.AudioError("timeout; completion unknown")

    monkeypatch.setattr(audio, "require_audio_tools", lambda: None)
    monkeypatch.setattr(audio, "provider_request", failed)
    with pytest.raises(audio.AudioError, match="completion unknown"):
        revoice.converted_voice(segment, generate=True)
    with pytest.raises(audio.AudioError, match="previous conversion attempt"):
        revoice.converted_voice(segment, generate=True)
    assert calls == [1]
    assert source.read_bytes() == b"retained original"


def test_conversion_cache_binds_the_original_audio_and_target_voice(work, monkeypatch):
    segment = {"id": "s01", "speaker": "krish", "text": "Same words.", "sourceSha256": "source-a"}
    _, first, path = revoice.conversion_recipe(segment)
    changed = copy.deepcopy(segment)
    changed["sourceSha256"] = "source-b"
    assert revoice.conversion_recipe(changed)[2] != path
    monkeypatch.setenv("ELEVENLABS_VOICE_ID", "different-voice")
    assert revoice.conversion_recipe(segment)[2] != path
    assert "offline-krish" not in str(first)


def test_v4_changes_pause_hints_without_rewriting_dialogue_or_losing_adjacent_context(work):
    plan = {"segments": [
        {"id": "s01", "speaker": "krish", "text": "First. [pause] Still the original words."},
        {"id": "s02", "speaker": "jakub", "text": "Second: same wording."},
        {"id": "s03", "speaker": "krish", "text": "Third. [pause] Unchanged."},
    ]}
    before = copy.deepcopy(plan)
    config = revoice_v4.make_config(plan)
    request, _ = audio.speech_request(config, 1)
    assert plan == before
    assert request["request"]["text"] == plan["segments"][1]["text"]
    assert request["request"]["previous_text"] == "First. ... Still the original words."
    assert request["request"]["next_text"] == "Third. ... Unchanged."


def test_v4_preserves_reference_pauses_and_ignores_quiet_inside_a_word():
    words = [
        {"word": "One.", "start": 0.0, "end": 0.3},
        {"word": "Second.", "start": 0.9, "end": 1.9},
    ]
    original = [{**words[0]}, {**words[1], "start": 1.25}]
    assert revoice_v4.pause_candidates(
        words, original, [(0.3, 0.9), (1.1, 1.4)], [(0.45, 1.25)], 2.0,
    ) == []
    with pytest.raises(audio.AudioError, match="wording differs"):
        revoice_v4.pause_candidates(words[:-1], original, [], [], 2.0)


def test_v4_rejects_a_fit_that_would_rush_the_performance():
    with pytest.raises(audio.AudioError, match="No speech was clipped or regenerated"):
        revoice_v4.fitting_plan(5 * audio.SAMPLE_RATE, 3 * audio.SAMPLE_RATE, [])


def test_v4_uses_actual_trailing_silence_when_provider_word_timing_is_late():
    words = [{"word": "Ending.", "start": 0.9, "end": 1.0}]
    candidates = revoice_v4.pause_candidates(words, words, [(0.7, 1.0)], [], 1.0)
    assert len(candidates) == 1
    assert candidates[0]["reason"] == "trailing silence"
    assert candidates[0]["capacitySamples"] < round(0.3 * audio.SAMPLE_RATE)


def test_v4_cuts_only_quiet_samples_and_preserves_both_spoken_phrases(work):
    require_ffmpeg()
    source, output = work / "pauses.wav", work / "edited.wav"
    audio.ffmpeg(
        "-v", "error", "-f", "lavfi", "-i",
        r"aevalsrc=if(between(t\,0.2\,0.5)+between(t\,0.95\,1.25)\,0.2*sin(2*PI*661*t)\,0):s=48000:d=1.6",
        "-c:a", "pcm_s24le", source,
    )
    words = [
        {"word": "First.", "start": 0.2, "end": 0.5},
        {"word": "Second.", "start": 0.95, "end": 1.25},
    ]
    original_words = [{**words[0]}, {**words[1], "start": 0.67, "end": 0.97}]
    candidates = revoice_v4.pause_candidates(
        words, original_words, revoice_v4.silence_intervals(source), [(0.5, 0.67)], 1.6,
    )
    cuts, tempo = revoice_v4.fitting_plan(round(1.6 * audio.SAMPLE_RATE), round(1.2 * audio.SAMPLE_RATE), candidates)
    source_hash = audio.sha256(source)
    path, maximum = revoice_v4.cut_pauses(source, output, cuts)
    assert path == output and maximum == 0 and tempo == 1
    assert audio.probe_audio(output)["duration"] == pytest.approx(1.2, abs=1 / audio.SAMPLE_RATE)

    def voiced_samples(path):
        import wave

        with wave.open(str(path), "rb") as stream:
            data = stream.readframes(stream.getnframes())
        return [data[i:i + 3] for i in range(0, len(data), 3) if data[i:i + 3] != b"\0\0\0"]

    assert voiced_samples(output) == voiced_samples(source)
    assert audio.sha256(source) == source_hash
    assert revoice_v4.mapped_time(words[1]["start"], cuts, tempo) < words[1]["start"]
    with pytest.raises(audio.AudioError, match="audible samples"):
        revoice_v4.cut_pauses(source, work / "rejected.wav", [
            {"startSample": round(0.25 * audio.SAMPLE_RATE), "endSample": round(0.4 * audio.SAMPLE_RATE)},
        ])
    assert not (work / "rejected.wav").exists()


def test_v4_fitting_keeps_pitch_and_the_ending_in_a_shorter_original_scene(work):
    require_ffmpeg()
    source, raw_path = work / "build" / "audio" / "s01.mp3", work / "fresh.mp3"
    for path, duration, tail in ((source, 2.1, 0.1), (raw_path, 2.8, 0.25)):
        audio.ffmpeg(
            "-v", "error", "-f", "lavfi", "-i", f"sine=frequency=661:sample_rate=44100:duration={duration}",
            "-af", f"apad=pad_dur={tail}", "-c:a", "libmp3lame", "-b:a", "192k", path,
        )
    segment = {
        "id": "s01", "speaker": "krish", "duration": 2.5, "sourceSha256": audio.sha256(source),
        "words": [{"word": "Held.", "start": 0.0, "end": 2.1}],
    }
    raw = {
        "audio": audio.relative(raw_path), "audioSha256": audio.sha256(raw_path),
        "fingerprint": "offline-fresh-v4", "words": [{"word": "Held.", "start": 0.0, "end": 2.8}],
    }
    fitted = revoice_v4.fitted_voice(segment, raw, -16)
    assert 1.2 < fitted["tempo"] < 1.3
    assert fitted["probe"]["duration"] < segment["duration"] - 0.05
    assert audio.sha256(source) == segment["sourceSha256"] and audio.sha256(raw_path) == raw["audioSha256"]
    pcm = subprocess.check_output([
        "ffmpeg", "-v", "error", "-i", str(audio.from_relative(fitted["audio"])),
        "-ar", "48000", "-ac", "1", "-c:a", "pcm_s16le", "-f", "s16le", "-",
    ])
    ending = array("h", pcm)[round(2.1 * audio.SAMPLE_RATE):round(2.2 * audio.SAMPLE_RATE)]
    assert max(abs(sample) for sample in ending) > 1000
    crossing_count = sum(left <= 0 < right for left, right in zip(ending, ending[1:]))
    assert crossing_count / (len(ending) / audio.SAMPLE_RATE) == pytest.approx(661, abs=10)


def test_export_rejects_a_mix_made_for_previous_voice_ids(work, monkeypatch):
    segment = {"id": "s01", "speaker": "krish", "text": "Same words.", "sourceSha256": "source-a"}
    _, inputs, _ = revoice.conversion_recipe(segment)
    plan = {"segments": [segment]}
    path = revoice.WORK / "mix.wav"
    audio.atomic_bytes(path, b"not decoded: voice validation must reject first")
    audio.atomic_json(revoice.WORK / "mix.json", {
        "source": plan, "audioSha256": audio.sha256(path), "pipeline": revoice.pipeline_identity(),
        "stems": [{"id": "s01", "conversionFingerprint": audio.fingerprint(inputs)}],
    })
    monkeypatch.setenv("ELEVENLABS_VOICE_ID", "newly-selected-voice")
    with pytest.raises(audio.AudioError, match="Selected voices"):
        revoice.export(plan)


def test_small_timing_correction_keeps_the_complete_stem_inside_the_original_slot(work):
    require_ffmpeg()
    source = work / "build" / "audio" / "s01.mp3"
    converted = work / "converted.mp3"
    for path, duration in ((source, 2.0), (converted, 2.08)):
        audio.ffmpeg(
            "-v", "error", "-f", "lavfi", "-i", f"sine=frequency=661:sample_rate=48000:duration={duration}",
            "-c:a", "libmp3lame", path,
        )
    segment = {"id": "s01", "speaker": "krish", "duration": 2.2}
    raw = {"audio": audio.relative(converted), "fingerprint": "converted-fixture"}
    source_hash, converted_hash = audio.sha256(source), audio.sha256(converted)
    fitted = revoice.fitted_voice(segment, raw, -16)
    assert fitted["tempo"] == pytest.approx(1.04)
    assert 2.0 <= fitted["probe"]["duration"] <= 2.18
    assert audio.sha256(source) == source_hash and audio.sha256(converted) == converted_hash
    audio.ffmpeg(
        "-v", "error", "-f", "lavfi", "-i", "sine=frequency=661:sample_rate=48000:duration=2.25",
        "-c:a", "libmp3lame", converted,
    )
    with pytest.raises(audio.AudioError, match="over 5%"):
        revoice.fitted_voice(segment, raw, -16)


def test_mux_preserves_every_video_packet_and_replaces_not_overlays_audio(work):
    require_ffmpeg()
    source, track, output = work / "source.mp4", work / "new.wav", work / "new.mp4"
    audio.ffmpeg(
        "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=160x90:rate=30:duration=1",
        "-f", "lavfi", "-i", "sine=frequency=997:sample_rate=48000:duration=1",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-t", "1", source,
    )
    unnormalized = work / "tone.wav"
    audio.ffmpeg(
        "-v", "error", "-f", "lavfi", "-i", "sine=frequency=661:sample_rate=48000:duration=1",
        "-c:a", "pcm_s24le", unnormalized,
    )
    audio.normalize_audio(unnormalized, track, channels=1, target=-16, peak=-3, lra=11)
    original_hash = audio.sha256(source)
    result = revoice.mux_copy(source, track, output, 1.0)
    assert result["video"] == revoice.video_identity(source)
    assert result["video"]["packets"] == 30
    assert audio.sha256(source) == original_hash
    decoded = subprocess.check_output([
        "ffmpeg", "-v", "error", "-i", str(output), "-map", "0:a:0", "-ar", "48000", "-ac", "1",
        "-c:a", "pcm_s16le", "-f", "s16le", "-",
    ])
    samples = array("h", decoded)[4800:43200]

    def energy(frequency):
        real = sum(sample * math.cos(2 * math.pi * frequency * i / 48000) for i, sample in enumerate(samples))
        imag = sum(sample * math.sin(2 * math.pi * frequency * i / 48000) for i, sample in enumerate(samples))
        return math.hypot(real, imag)

    assert energy(661) > 30 * energy(997)
    with pytest.raises(audio.AudioError, match="cannot be overwritten"):
        revoice.mux_copy(source, track, source, 1.0)
