#!/usr/bin/env python3
"""Build the final film: one continuous timeline rendered frame by frame, loudness-matched voices, ducked music.

uv run python video/build.py            # full render -> video/build/final.mp4
uv run python video/build.py --preview  # every 10th frame only, fast contact-sheet check
"""

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
BUILD = ROOT / "build"


def run(*args):
    return subprocess.run(args, check=True, capture_output=True, text=True)


def probe(path):
    return float(run("ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)).stdout)


def loudness(path):
    report = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(path), "-af", "ebur128", "-f", "null", "-"], capture_output=True, text=True).stderr
    return float([line for line in report.splitlines() if line.strip().startswith("I:")][-1].split()[1])


def captions(words, speech_end, shortest=3, longest=7):
    """Readable caption phrases: 3-7 words, broken at punctuation when possible, never a lonely word."""
    groups, current = [], []
    for word in words:
        current.append(word)
        punct = re.search(r"[.,:;?!]$", word["word"])
        if len(current) >= longest or (punct and len(current) >= shortest):
            groups.append(current)
            current = []
    if current:
        if groups and len(current) < shortest and len(groups[-1]) + len(current) <= longest + 2:
            groups[-1] += current
        else:
            groups.append(current)
    out = []
    for i, group in enumerate(groups):
        end = groups[i + 1][0]["start"] if i + 1 < len(groups) else speech_end + 0.3
        out.append({"text": " ".join(w["word"] for w in group), "start": round(group[0]["start"], 3), "end": round(end, 3)})
    return out


def timeline(config):
    segments, clock, rec_clock = [], 0.0, {}
    for index, segment in enumerate(config["segments"]):
        meta = json.loads((BUILD / "audio" / f"{segment['id']}.json").read_text())
        duration = max(meta["duration"] + config["gap"], segment.get("minSeconds", 0)) + segment.get("hold", 0)
        previous = config["segments"][index - 1]["visual"] if index else {}
        visual = segment["visual"]
        continuous = bool(index) and ((visual.get("rec") and visual.get("rec") == previous.get("rec"))
                                      or (visual.get("scene") and visual.get("scene") == previous.get("scene")))
        rec = visual.get("rec")
        offset = rec_clock.get(rec, 0.0) if rec else None
        if rec:
            rec_clock[rec] = offset + duration
        segments.append({**segment, "index": index, "start": round(clock, 3), "duration": round(duration, 3), "speech": meta["duration"],
                         "fadeIn": bool(index) and not continuous, "recOffset": None if offset is None else round(offset, 3),
                         "words": meta["words"], "captions": captions(meta["words"], meta["duration"]) if segment.get("caption") else []})
        clock += duration
    return segments, round(clock, 3)


def main(preview=False):
    config = json.loads((ROOT / "config.json").read_text())
    segments, total = timeline(config)
    for s in segments:
        kind = s["visual"].get("scene") or s["visual"].get("shot") or "rec " + s["visual"].get("rec", "")
        print(f"{s['start']:6.2f} {s['duration']:5.2f}s {s['id']} {s['speaker']:<5} {kind}")
    print(f"TOTAL {total:.2f}s")
    if total > config["maxSeconds"]:
        sys.exit(f"Over the {config['maxSeconds']}s limit — shorten lines in config.json")
    film = {"segments": segments, "crossfade": config["crossfade"], "voices": config["voices"], "fps": config["fps"],
            "recs": json.loads((BUILD / "rec" / "index.json").read_text()), "terminal": json.loads((BUILD / "terminal.json").read_text())}
    fps = config["fps"]
    frames_dir = BUILD / "film"
    shutil.rmtree(frames_dir, ignore_errors=True)
    frames_dir.mkdir(parents=True)
    count = int(total * fps)
    step = 10 if preview else 1
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1920, "height": 1080})
        page.goto((ROOT / "film.html").resolve().as_uri())
        page.evaluate("(f) => loadFilm(f)", film)
        for n, frame in enumerate(range(0, count, step)):
            page.evaluate("async (t) => await renderFrame(t)", frame / fps)
            page.screenshot(path=str(frames_dir / f"{n:05d}.jpg"), type="jpeg", quality=93)
            if frame % (fps * 10) == 0:
                print(f"  rendered {frame / fps:5.1f}s", flush=True)
        browser.close()
    if preview:
        run("ffmpeg", "-loglevel", "error", "-y", "-framerate", "1", "-i", str(frames_dir / "%05d.jpg"), "-vf", "scale=384:-1,tile=8x"
            f"{(count // step) // 8 + 1}", "-frames:v", "1", str(BUILD / "preview.jpg"))
        print(f"preview {BUILD / 'preview.jpg'}")
        return

    # Audio: every line normalised to the same loudness, placed at its start time; music ducked under the voices.
    inputs, chains, labels = [], [], []
    for i, s in enumerate(segments):
        audio = BUILD / "audio" / f"{s['id']}.mp3"
        gain = config["loudnessLufs"] - loudness(audio)
        inputs += ["-i", str(audio)]
        chains.append(f"[{i}:a]aresample=48000,volume={gain:.2f}dB,adelay={int(s['start'] * 1000)}:all=1[v{i}]")
        labels.append(f"[v{i}]")
    voice_mix = f"{''.join(labels)}amix=inputs={len(labels)}:normalize=0,apad,atrim=duration={total:.3f}[voice]"
    music = BUILD / "music.mp3"
    music_idx = len(segments)
    inputs += ["-i", str(music)]
    mix = (f"[{music_idx}:a]aresample=48000,volume={config['music']['volumeDb']}dB,atrim=duration={total:.3f},"
           f"afade=t=in:d=0.6,afade=t=out:st={total - 2.5:.2f}:d=2.5[m];[voice]asplit=2[vo][key];"
           f"[m][key]sidechaincompress=threshold=0.03:ratio=4:attack=25:release=350[duck];"
           f"[vo][duck]amix=inputs=2:normalize=0,alimiter=limit=0.95[a]")
    wav = BUILD / "mix.wav"
    run("ffmpeg", "-loglevel", "error", "-y", *inputs, "-filter_complex", ";".join(chains + [voice_mix, mix]), "-map", "[a]", "-ar", "48000", str(wav))
    final = BUILD / "final.mp4"
    run("ffmpeg", "-loglevel", "error", "-y", "-framerate", str(fps), "-i", str(frames_dir / "%05d.jpg"), "-i", str(wav),
        "-vf", f"fade=t=in:d=0.35,fade=t=out:st={total - 0.6:.2f}:d=0.6", "-c:v", "libx264", "-preset", "slow", "-crf", "16",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-c:a", "aac", "-b:a", "192k", "-shortest", str(final))
    seconds = probe(final)
    print(f"\nFINAL {final}  {seconds:.2f}s  {'OK (≤ 2:00)' if seconds <= 120 else 'TOO LONG'}")


if __name__ == "__main__":
    main("--preview" in sys.argv)
