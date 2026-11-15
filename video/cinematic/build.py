#!/usr/bin/env python3
"""Render the cinematic cut without modifying the original film or recordings."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent.parent
BUILD = ROOT.parent / "build" / "cinematic"
ORIGINAL = ROOT.parent / "build" / "final.mp4"
FINAL = ROOT.parent / "build" / "final-cinematic.mp4"
sys.path.insert(0, str(REPO))
from video.build import captions  # noqa: E402
from video.cinematic.audio import fingerprint  # noqa: E402


def run(*args: str) -> subprocess.CompletedProcess:
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(f"{args[0]} failed ({result.returncode}):\n{result.stderr[-5000:]}")
    return result


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def probe(path: Path) -> dict:
    return json.loads(run(
        "ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)
    ).stdout)


def validate_editorial_plan(film: dict) -> None:
    edit = film.get("edit", {})
    chapters, zooms = edit.get("chapters", []), edit.get("zooms", [])
    if len(chapters) != 3 or {item["id"] for item in chapters} != {"milk", "butter", "boundary"}:
        raise ValueError("The business pitch must keep all three clearly identified scenarios.")
    for chapter in chapters:
        shots = [segment for segment in film["segments"] if segment.get("chapter") == chapter["id"]]
        if (
            not shots or abs(shots[0]["start"] - chapter["start"]) > .002
            or abs(shots[-1]["start"] + shots[-1]["duration"] - chapter["end"]) > .002
            or abs(sum(shot["duration"] for shot in shots) - (chapter["end"] - chapter["start"])) > .002
        ):
            raise ValueError(f"Scenario timing drifted: {chapter['id']}")
    if len(zooms) != 2 or {zoom["id"] for zoom in zooms} != {"approval", "agent-decisions"}:
        raise ValueError("Exactly two demo zooms are allowed: approval and agent decisions.")
    previous_end = 0.0
    for zoom in sorted(zooms, key=lambda item: item["start"]):
        values = [zoom["start"], zoom["end"], zoom["scale"], zoom["ramp"], *zoom["center"]]
        if (
            not all(isinstance(value, (int, float)) and math.isfinite(value) for value in values)
            or len(zoom["center"]) != 2 or not all(0 <= value <= 1 for value in zoom["center"])
            or zoom["start"] < previous_end or zoom["end"] > film["duration"]
            or not 1 < zoom["scale"] <= 2 or zoom["ramp"] <= 0
            or zoom["end"] - zoom["start"] <= 2 * zoom["ramp"]
        ):
            raise ValueError("Invalid, overlapping or unreadably short demo zoom.")
        purpose = "milk" if zoom["id"] == "approval" else "butter"
        shots = [segment for segment in film["segments"]
                 if segment["start"] < zoom["end"] and segment["start"] + segment["duration"] > zoom["start"]]
        if not shots or any(not shot["visual"].get("rec") or shot.get("chapter") != purpose for shot in shots):
            raise ValueError(f"The {zoom['id']} zoom is outside its recorded scenario.")
        previous_end = zoom["end"]
    for segment in film["segments"]:
        visual = segment["visual"]
        if visual.get("rec"):
            hold = visual.get("holdEndSeconds", 0)
            playback = segment["duration"] - hold
            if not math.isfinite(hold) or hold < 0 or playback <= 0:
                raise ValueError("Invalid demo reading hold.")
            if visual["sourceEnd"] - visual["sourceStart"] > playback + .002:
                raise ValueError("The revised demonstration must not accelerate its source recording.")


def validate_timeline(film: dict) -> None:
    if film["fps"] != 60 or (film["width"], film["height"]) != (1920, 1080):
        raise ValueError("The cinematic master must be 1920x1080 at 60fps.")
    if not 0 < film["duration"] <= 119:
        raise ValueError("The complete film must not exceed 119 seconds.")
    cursor = 0.0
    ids = set()
    for segment in film["segments"]:
        if (
            segment["id"] in ids
            or not math.isfinite(segment["start"])
            or not math.isfinite(segment["duration"])
            or abs(segment["start"] - cursor) > .002
            or segment["duration"] <= 0
        ):
            raise ValueError(f"Invalid or discontinuous segment: {segment['id']}")
        ids.add(segment["id"])
        cursor = segment["start"] + segment["duration"]
        last_end = 0.0
        for word in segment["words"]:
            if not 0 <= word["start"] <= word["end"] <= segment["duration"] + .002:
                raise ValueError(f"Word timing outside {segment['id']}")
            if word["start"] < last_end - .05:
                raise ValueError(f"Overlapping word timings in {segment['id']}")
            last_end = word["end"]
        segment["captions"] = captions(segment["words"], segment["speech"])
        if segment["visual"].get("rec"):
            visual = segment["visual"]
            if visual["rec"] not in {"A", "B", "C"} or not 0 <= visual["sourceStart"] < visual["sourceEnd"]:
                raise ValueError("Invalid original-recording window.")
    if abs(cursor - film["duration"]) > .002:
        raise ValueError("Timeline does not cover the complete film.")
    if film["segments"][-1]["duration"] - film["segments"][-1]["speech"] < 1.3 - .002:
        raise ValueError("The final line needs at least 1.3 seconds of clear closing hold.")
    if any(s["visual"].get("scene") == "terminal" for s in film["segments"]):
        terminal = film.get("terminal")
        if not isinstance(terminal, list) or not all(isinstance(line, str) for line in terminal):
            raise ValueError("The original refusal capture is missing.")
        if not all(any(re.search(rf"\b{code}\b", line) for line in terminal) for code in (409, 403)):
            raise ValueError("Both captured refusal responses are required.")
    validate_editorial_plan(film)


def draft_film(config: dict, terminal: list) -> dict:
    total_weight = sum(s["targetSeconds"] for s in config["segments"])
    clock = 0.0
    segments = []
    for source in config["segments"]:
        duration = (source["targetSeconds"] if config.get("timing") == "fixed"
                    else source["targetSeconds"] / total_weight * config["duration"])
        speech = duration - (1.8 if source["id"] == "s21" else .3)
        lead_in = source.get("leadInSeconds", 0)
        tokens = source["text"].split()
        words = [
            {"word": word, "start": lead_in + .08 + i * (speech - lead_in - .08) / len(tokens),
             "end": lead_in + .08 + (i + .85) * (speech - lead_in - .08) / len(tokens)}
            for i, word in enumerate(tokens)
        ]
        segments.append({**source, "start": clock, "duration": duration, "speech": speech, "words": words})
        clock += duration
    return {
        **{key: config[key] for key in ("fps", "width", "height", "duration", "maxSeconds")},
        "draft": True, "segments": segments,
        "terminal": terminal, "edit": config.get("edit", {}),
    }


def load_film(draft: bool = False) -> dict:
    config = json.loads((ROOT / "config.json").read_text())
    if digest(ORIGINAL) != config["originalSha256"]:
        raise ValueError("The original final.mp4 changed; inspect it before reusing its evidence.")
    if draft:
        terminal = json.loads((ROOT.parent / "build" / "terminal.json").read_text())
        film = draft_film(config, terminal)
    else:
        film = json.loads((BUILD / "film.json").read_text())
        plan = json.loads((BUILD / "plan.json").read_text())
        terminal = json.loads((ROOT.parent / "build" / "terminal.json").read_text())
        if (
            plan["configSha256"] != fingerprint(config)
            or plan["filmSha256"] != fingerprint(film)
            or plan["terminalSha256"] != fingerprint(terminal)
        ):
            raise ValueError("The narration plan is stale; rebuild it before rendering.")
    validate_timeline(film)
    return film


def load_page(browser, film: dict):
    page = browser.new_page(viewport={"width": film["width"], "height": film["height"]}, device_scale_factor=1)
    page.set_default_timeout(30000)
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto((ROOT / "film.html").as_uri())
    page.evaluate("(film) => loadFilm(film)", film)
    if errors:
        raise RuntimeError("\n".join(errors))
    return page, errors


def source_signature(film: dict) -> str:
    hash_value = hashlib.sha256(json.dumps(film, sort_keys=True).encode())
    for file in (ROOT / "film.html", ROOT / "motion.js", Path(__file__)):
        hash_value.update(file.read_bytes())
    for label in "ABC":
        folder = ROOT.parent / "build" / "rec" / label
        paths = sorted(folder.glob("*.jpg"))
        if not paths:
            raise FileNotFoundError(f"Original recording {label} is missing.")
        for path in paths:
            hash_value.update(path.name.encode())
            hash_value.update(bytes.fromhex(digest(path)))
    return hash_value.hexdigest()


def preview(film: dict, times: list[float] | None) -> None:
    folder = BUILD / ("preview-draft" if film.get("draft") else "preview")
    folder.mkdir(parents=True, exist_ok=True)
    if not times:
        times = [s["start"] + s["duration"] * fraction for s in film["segments"] for fraction in (.45, .84)]
    for time in times:
        if not 0 <= time < film["duration"]:
            raise ValueError(f"Preview time outside film: {time}")
    frames = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page, errors = load_page(browser, film)
        for index, time in enumerate(times):
            state = page.evaluate("(time) => renderFrame(time)", time)
            path = folder / f"{index:03d}.jpg"
            page.screenshot(path=str(path), type="jpeg", quality=96)
            frames.append({"file": path.name, **state})
        browser.close()
    if errors:
        raise RuntimeError("\n".join(errors))
    (folder / "frames.json").write_text(json.dumps(frames, indent=2) + "\n")
    rows = math.ceil(len(times) / 4)
    run("ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-framerate", "1",
        "-i", str(folder / "%03d.jpg"), "-frames:v", "1",
        "-vf", f"scale=480:270,tile=4x{rows}:nb_frames={len(times)}:padding=4:margin=4:color=0x020b0e",
        str(folder / "overview.jpg"))
    print(f"Preview: {folder / 'overview.jpg'}")


def render_chunk(film: dict, start_frame: int, end_frame: int, folder: Path) -> Path:
    target = folder / f"{start_frame:06d}.mp4"
    expected_frames = end_frame - start_frame
    if target.exists():
        stream = next(s for s in probe(target)["streams"] if s["codec_type"] == "video")
        if int(stream.get("nb_frames", 0)) == expected_frames:
            print(f"Cached {start_frame / film['fps']:5.1f}s", flush=True)
            return target
        raise ValueError(f"Incomplete cached chunk: {target}; remove only this chunk before retrying.")
    partial = target.with_suffix(".partial.mp4")
    log_path = target.with_suffix(".log")
    command = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
        "-f", "image2pipe", "-c:v", "mjpeg", "-framerate", str(film["fps"]), "-i", "pipe:0",
        "-an", "-vf", "scale=in_range=pc:out_range=tv:out_color_matrix=bt709,format=yuv420p",
        "-c:v", "libx264", "-preset", "medium", "-crf", "16", "-threads", "2",
        "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
        "-movflags", "+faststart", str(partial),
    ]
    with log_path.open("w") as log:
        encoder = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=log)
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch()
                page, errors = load_page(browser, film)
                for frame in range(start_frame, end_frame):
                    page.evaluate("(time) => renderFrame(time)", frame / film["fps"])
                    encoder.stdin.write(page.screenshot(type="jpeg", quality=96))
                browser.close()
                if errors:
                    raise RuntimeError("\n".join(errors))
            encoder.stdin.close()
            if encoder.wait(timeout=180):
                raise RuntimeError(log_path.read_text()[-4000:])
        except BaseException:
            if encoder.poll() is None:
                encoder.terminate()
                try:
                    encoder.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    encoder.kill()
                    encoder.wait()
            raise
    partial.replace(target)
    stream = next(s for s in probe(target)["streams"] if s["codec_type"] == "video")
    if int(stream.get("nb_frames", 0)) != expected_frames:
        raise ValueError(f"Rendered chunk has the wrong frame count: {target}")
    print(f"Rendered {start_frame / film['fps']:5.1f}-{end_frame / film['fps']:5.1f}s", flush=True)
    return target


def srt_timestamp(seconds: float) -> str:
    milliseconds = round(seconds * 1000)
    hours, milliseconds = divmod(milliseconds, 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    seconds, milliseconds = divmod(milliseconds, 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"


def write_subtitles(film: dict) -> None:
    lines = []
    count = 1
    for segment in film["segments"]:
        for phrase in segment["captions"]:
            start = segment["start"] + phrase["start"]
            end = min(segment["start"] + phrase["end"], segment["start"] + segment["duration"])
            lines += [str(count), f"{srt_timestamp(start)} --> {srt_timestamp(end)}", phrase["text"], ""]
            count += 1
    FINAL.with_suffix(".srt").write_text("\n".join(lines), encoding="utf-8")


def render(film: dict, workers: int) -> None:
    if film.get("draft"):
        raise ValueError("A draft timing plan cannot be used for the final render.")
    mix_path = BUILD / "mix.wav"
    mix_metadata = json.loads((BUILD / "mix.json").read_text())
    raw_film = json.loads((BUILD / "film.json").read_text())
    if (
        mix_metadata["inputs"]["filmSha256"] != fingerprint(raw_film)
        or mix_metadata["audioSha256"] != digest(mix_path)
    ):
        raise ValueError("The mastered mix does not match this narration timeline.")
    mix_info = probe(mix_path)
    mix_stream = next(s for s in mix_info["streams"] if s["codec_type"] == "audio")
    if mix_stream["channels"] != 2 or abs(float(mix_info["format"]["duration"]) - film["duration"]) > .05:
        raise ValueError("The mastered mix must be stereo and cover the exact film duration.")
    signature = source_signature(film)
    folder = BUILD / "render" / signature[:16]
    folder.mkdir(parents=True, exist_ok=True)
    total_frames = round(film["duration"] * film["fps"])
    chunk_frames = 8 * film["fps"]
    ranges = [(start, min(start + chunk_frames, total_frames)) for start in range(0, total_frames, chunk_frames)]
    chunks = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        tasks = {pool.submit(render_chunk, film, a, b, folder): a for a, b in ranges}
        for future in as_completed(tasks):
            chunks[tasks[future]] = future.result()
    concat = folder / "concat.txt"
    concat.write_text("".join(f"file '{chunks[start].name}'\n" for start, _ in ranges))
    partial = FINAL.with_suffix(".partial.mp4")
    run("ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "concat", "-safe", "1", "-i", str(concat), "-i", str(mix_path),
        "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "256k",
        "-ar", "48000", "-ac", "2", "-t", str(film["duration"]), "-movflags", "+faststart",
        "-metadata", "title=Open to Agents - Business Pitch", str(partial))
    info = probe(partial)
    video = next(s for s in info["streams"] if s["codec_type"] == "video")
    if float(info["format"]["duration"]) > 119 or int(video["nb_frames"]) != total_frames:
        raise ValueError("The exported cut violates its duration or frame-count contract.")
    partial.replace(FINAL)
    write_subtitles(film)
    (BUILD / "render-manifest.json").write_text(json.dumps({
        "sourceSignature": signature, "videoSha256": digest(FINAL), "mixSha256": digest(mix_path),
        "originalSha256": digest(ORIGINAL), "frames": total_frames, "fps": film["fps"],
        "duration": float(info["format"]["duration"]), "file": "../final-cinematic.mp4",
    }, indent=2) + "\n")
    print(f"Final: {FINAL} ({info['format']['duration']}s)")


def verify() -> None:
    film = load_film()
    manifest = json.loads((BUILD / "render-manifest.json").read_text())
    if (
        manifest["videoSha256"] != digest(FINAL)
        or manifest["sourceSignature"] != source_signature(film)
        or manifest["mixSha256"] != digest(BUILD / "mix.wav")
    ):
        raise ValueError("The encoded movie does not match the current edit, source assets and mastered mix.")
    info = probe(FINAL)
    video = next(s for s in info["streams"] if s["codec_type"] == "video")
    audio = next(s for s in info["streams"] if s["codec_type"] == "audio")
    if float(info["format"]["duration"]) > 119:
        raise ValueError("Final exceeds 119 seconds.")
    if (video["width"], video["height"], video["r_frame_rate"]) != (1920, 1080, "60/1"):
        raise ValueError("Final picture format differs from the approved master.")
    if int(video["nb_frames"]) != round(film["duration"] * film["fps"]):
        raise ValueError("The final film is missing frames.")
    if audio["channels"] != 2:
        raise ValueError("The final film is not stereo.")
    report = run(
        "ffmpeg", "-hide_banner", "-nostats", "-i", str(FINAL),
        "-af", "ebur128=peak=true", "-vf", "blackdetect=d=0.3:pix_th=0.015:pic_th=0.999",
        "-f", "null", "-"
    ).stderr
    integrated = float(re.findall(r"^\s*I:\s+(-?[\d.]+) LUFS", report, re.M)[-1])
    peak = float(re.findall(r"^\s*Peak:\s+(-?[\d.]+) dBFS", report, re.M)[-1])
    black = re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", report)
    bad_black = [(float(a), float(b)) for a, b in black if float(a) > .6 and float(b) < film["duration"] - .6]
    result = {
        "duration": float(info["format"]["duration"]), "frames": int(video["nb_frames"]),
        "resolution": [video["width"], video["height"]], "fps": video["r_frame_rate"],
        "audioChannels": audio["channels"], "integratedLUFS": integrated, "truePeakDBTP": peak,
        "interiorBlackIntervals": bad_black, "sha256": digest(FINAL),
        "renderProvenanceVerified": True,
        "architectureSeconds": sum(segment["duration"] for segment in film["segments"]
                                   if segment["visual"].get("scene") == "architecture"),
        "scenarioSeconds": {chapter["id"]: chapter["end"] - chapter["start"]
                            for chapter in film["edit"]["chapters"]},
        "demoZooms": film["edit"]["zooms"],
        "maximumRecordingSpeed": max(
            (segment["visual"]["sourceEnd"] - segment["visual"]["sourceStart"])
            / (segment["duration"] - segment["visual"].get("holdEndSeconds", 0))
            for segment in film["segments"] if segment["visual"].get("rec")
        ),
        "originalUnchanged": digest(ORIGINAL) == json.loads((ROOT / "config.json").read_text())["originalSha256"],
    }
    (BUILD / "verification.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    if not -17 <= integrated <= -15 or peak > -1.5 or bad_black or not result["originalUnchanged"]:
        raise ValueError("Mastering or continuity checks require attention.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    preview_command = commands.add_parser("preview")
    preview_command.add_argument("--draft", action="store_true")
    preview_command.add_argument("--at", type=float, nargs="+")
    render_command = commands.add_parser("render")
    render_command.add_argument("--workers", type=int, choices=(1, 2), default=2)
    commands.add_parser("verify")
    args = parser.parse_args()
    BUILD.mkdir(parents=True, exist_ok=True)
    if args.command == "preview":
        preview(load_film(args.draft), args.at)
    elif args.command == "render":
        render(load_film(), args.workers)
    else:
        verify()


if __name__ == "__main__":
    main()
