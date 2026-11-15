import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("cinematic_build", ROOT / "video" / "cinematic" / "build.py")
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)


@pytest.fixture
def film():
    config = json.loads((builder.ROOT / "config.json").read_text())
    return builder.draft_film(config, ["409 Approval required", "403 An authenticated human is required"])


def test_draft_covers_exact_duration_and_preserves_recorded_evidence(film):
    builder.validate_timeline(film)
    assert film["draft"] is True
    assert sum(s["duration"] for s in film["segments"]) == pytest.approx(118)
    source = {s["id"]: s["visual"] for s in json.loads((builder.ROOT / "config.json").read_text())["segments"]}
    assert {s["id"]: s["visual"] for s in film["segments"]} == source
    assert film["segments"][-1]["duration"] - film["segments"][-1]["speech"] >= 1.3


@pytest.mark.parametrize("failure", [
    "gap", "speech_clipped", "over_limit", "invalid_source", "nonfinite_start", "missing_refusal", "closing_clipped",
])
def test_timeline_rejects_unusable_deliverables(film, failure):
    if failure == "gap":
        film["segments"][1]["start"] += .2
    elif failure == "speech_clipped":
        film["segments"][0]["words"][-1]["end"] = film["segments"][0]["duration"] + .1
    elif failure == "over_limit":
        film["duration"] = 120
    elif failure == "invalid_source":
        film["segments"][8]["visual"]["sourceEnd"] = -1
    elif failure == "nonfinite_start":
        film["segments"][0]["start"] = float("nan")
    elif failure == "missing_refusal":
        film["terminal"] = ["409 Approval required"]
    else:
        film["segments"][-1]["speech"] = film["segments"][-1]["duration"] - .2
    with pytest.raises(ValueError):
        builder.validate_timeline(film)


def test_subtitle_timestamp_carries_rounded_milliseconds():
    assert builder.srt_timestamp(59.9996) == "00:01:00,000"
    assert builder.srt_timestamp(117.225) == "00:01:57,225"
