#!/usr/bin/env python3
"""Record the REAL app as continuous, narration-timed screen recordings (no stitched screenshots).

The voice lines are generated first; this script then operates the app on a schedule derived from their
lengths, so every click happens while it is being described. Frames come straight from Chrome's screencast
(1920x1080, JPEG q90) and are resampled to a constant frame rate. A visible cursor glides to each target.
Only typing is faster than a human. Recordings: A (chef, big order), B (manager), C (chef, small order).

uv run python video/record.py   (fresh workspace on AIMO_URL, default http://127.0.0.1:8004)
"""

import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
sys.path.insert(0, str(ROOT))
from build import timeline  # noqa: E402

URL = os.environ.get("AIMO_URL", "http://127.0.0.1:8004")
CREDS = Path(os.environ.get("AIMO_CREDENTIALS", REPO / "data/gateway/video-draft/credentials.json"))
OUT = ROOT / "build" / "rec"
DSF = 1.25
MILK = "I need 1,000 litres of lactose-free milk by Monday. Find an option that meets our requirements based on price and availability."
BUTTER = "20 kg butter for Friday"

CURSOR = """
(() => {
  const install = () => {
    if (document.getElementById('demo-cursor')) return;
    const c = document.createElement('div');
    c.id = 'demo-cursor';
    c.innerHTML = '<svg width="34" height="34" viewBox="0 0 24 24"><path d="M4 2l15 10-7 1.5L8.5 21z" fill="#111" stroke="#fff" stroke-width="1.6" stroke-linejoin="round"/></svg>';
    Object.assign(c.style, {position: 'fixed', left: '760px', top: '470px', zIndex: 99999, pointerEvents: 'none',
      transition: 'left .7s cubic-bezier(.45,0,.2,1), top .7s cubic-bezier(.45,0,.2,1)', filter: 'drop-shadow(0 3px 6px rgba(0,0,0,.35))'});
    document.body.appendChild(c);
    const ring = document.createElement('div');
    ring.id = 'demo-ring';
    Object.assign(ring.style, {position: 'fixed', width: '44px', height: '44px', marginLeft: '-22px', marginTop: '-22px', borderRadius: '50%',
      border: '3px solid #C0E021', zIndex: 99998, pointerEvents: 'none', opacity: 0, transform: 'scale(.4)', transition: 'opacity .45s, transform .45s'});
    document.body.appendChild(ring);
  };
  window.__cursorTo = (x, y) => { install(); const c = document.getElementById('demo-cursor'); c.style.left = (x - 6) + 'px'; c.style.top = (y - 4) + 'px'; };
  window.__ripple = (x, y) => { install(); const r = document.getElementById('demo-ring'); r.style.transition = 'none'; r.style.left = x + 'px'; r.style.top = y + 'px';
    r.style.opacity = 1; r.style.transform = 'scale(.4)'; r.offsetWidth; r.style.transition = 'opacity .5s, transform .5s'; r.style.opacity = 0; r.style.transform = 'scale(1.4)'; };
  document.addEventListener('DOMContentLoaded', install);
})();
"""


class Recorder:
    def __init__(self, page, name):
        self.page, self.name, self.frames, self.t0 = page, name, [], None
        self.folder = OUT / f"{name}_raw"
        shutil.rmtree(self.folder, ignore_errors=True)
        self.folder.mkdir(parents=True)
        self.cdp = page.context.new_cdp_session(page)
        self.cdp.on("Page.screencastFrame", self._frame)
        self.boxes = {}

    def _frame(self, event):
        stamp = event["metadata"]["timestamp"]
        path = self.folder / f"{len(self.frames):06d}.jpg"
        import base64
        path.write_bytes(base64.b64decode(event["data"]))
        self.frames.append((stamp, path))
        try:
            self.cdp.send("Page.screencastFrameAck", {"sessionId": event["sessionId"]})
        except Exception:
            pass

    def start(self):
        self.cdp.send("Page.startScreencast", {"format": "jpeg", "quality": 90, "maxWidth": 1920, "maxHeight": 1080, "everyNthFrame": 1})
        self.page.wait_for_timeout(300)
        self.t0 = time.time()

    def at(self, seconds):
        """Wait until `seconds` after the recording mark (the narration clock)."""
        remaining = self.t0 + seconds - time.time()
        if remaining > 0:
            self.page.wait_for_timeout(int(remaining * 1000))
        else:
            print(f"  [{self.name}] running {-remaining:.2f}s late at {seconds:.2f}s")

    def box(self, key, selector):
        rect = self.page.evaluate("(s) => { const r = document.querySelector(s).getBoundingClientRect(); return [r.left, r.top, r.width, r.height]; }", selector)
        self.boxes[key] = [round(v * DSF) for v in rect]

    def stop(self, duration, fps):
        self.at(duration + 0.2)
        self.cdp.send("Page.stopScreencast")
        self.page.wait_for_timeout(200)
        out = OUT / self.name
        shutil.rmtree(out, ignore_errors=True)
        out.mkdir(parents=True)
        frames = sorted(self.frames)
        idx = 0
        for n in range(int(duration * fps) + 2):
            t = self.t0 + n / fps
            while idx + 1 < len(frames) and frames[idx + 1][0] <= t:
                idx += 1
            os.link(frames[idx][1], out / f"{n:05d}.jpg")
        print(f"rec {self.name}: {len(frames)} source frames -> {int(duration * fps) + 2} @ {fps}fps")


def glide_click(page, selector, settle=0.75):
    target = page.locator(selector).first
    target.scroll_into_view_if_needed()
    box = target.bounding_box()
    x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    page.evaluate("([x, y]) => __cursorTo(x, y)", [x, y])
    page.wait_for_timeout(int(settle * 1000))
    page.evaluate("([x, y]) => __ripple(x, y)", [x, y])
    target.click()


def smooth_scroll(page, selector, block="center"):
    page.evaluate("([s, b]) => document.querySelector(s).scrollIntoView({behavior: 'smooth', block: b})", [selector, block])


def type_into(page, selector, text, cps=55):
    glide_click(page, selector, 0.6)
    page.locator(selector).press_sequentially(text, delay=int(1000 / cps))


def main():
    config = json.loads((ROOT / "config.json").read_text())
    segments, total = timeline(config)
    fps = config["fps"]

    def window(rec):
        group = [s for s in segments if s["visual"].get("rec") == rec]
        first = group[0]["start"]
        return {s["id"]: (round(s["start"] - first, 3), s["duration"]) for s in group}, round(sum(s["duration"] for s in group), 3)

    credentials = json.loads(CREDS.read_text())["credentials"]
    shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir(parents=True)
    meta = {}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()

        def login(who):
            context = browser.new_context(viewport={"width": 1536, "height": 864}, device_scale_factor=DSF)
            context.add_init_script(CURSOR)
            page = context.new_page()
            page.goto(URL)
            page.get_by_label("Login token", exact=True).fill(credentials[who])
            page.get_by_role("button", name="Sign in", exact=True).click()
            page.wait_for_selector("main h1")
            page.wait_for_timeout(500)
            return page

        # ---------- A: chef, big order (s09–s13) ----------
        chef = login("chef")
        win, length = window("A")
        rec = Recorder(chef, "A")
        rec.start()
        s9, d9 = win["s09"]
        rec.at(s9 + 0.8)
        type_into(chef, "#ask", MILK)
        rec.at(s9 + d9 - 1.6)
        glide_click(chef, "button[type=submit]:has-text('Continue')")
        s10, d10 = win["s10"]
        expect(chef.get_by_text("Here's what I understood")).to_be_visible(timeout=15000)
        rec.at(s10 + 0.2)
        smooth_scroll(chef, ".understood")
        rec.at(s10 + 1.7)
        glide_click(chef, "#dietaryConfirmed", 0.6)
        rec.at(s10 + d10 - 0.95)
        glide_click(chef, "[data-action=find]", 0.7)
        s12, d12 = win["s12"]
        chef.wait_for_selector(".xcard", timeout=60000)
        rec.at(s12 + 0.15)
        smooth_scroll(chef, ".xcard")
        rec.at(s12 + 1.1)
        rec.box("s12", ".xoptions")
        rec.at(s12 + d12 - 2.3)
        glide_click(chef, ".xoption.recommended", 0.8)
        s13, d13 = win["s13"]
        rec.at(s13 + 0.3)
        chef.evaluate("scrollTo({top: 0, behavior: 'smooth'})")
        expect(chef.get_by_text("Waiting for approval").first).to_be_visible(timeout=60000)
        rec.stop(length, fps)
        meta["A"] = {"length": length, "zoomBoxes": rec.boxes}
        job_id = re.search(r"#job/([^/]+)", chef.url).group(1)

        # real refusal output for scenario 3 (agent tries to cheat), captured while the order waits for approval
        result = subprocess.run([sys.executable, str(REPO / "scripts/agent_console.py"), "guardrails"], capture_output=True, text=True,
                                env={**os.environ, "AIMO_URL": URL, "AIMO_CREDENTIALS": str(CREDS)}, cwd=REPO)
        lines = [re.sub(r"\x1b\[[0-9;]*m", "", line) for line in result.stdout.splitlines() if line.strip()]
        (ROOT / "build" / "terminal.json").write_text(json.dumps(lines, indent=1))
        print("terminal:", " | ".join(lines[2:5]))

        # ---------- B: manager (s14) ----------
        manager = login("manager")
        manager.goto(URL + f"/#job/{job_id}/basket")
        manager.wait_for_selector(".decision")
        manager.wait_for_timeout(600)
        win, length = window("B")
        rec = Recorder(manager, "B")
        rec.start()
        s14, d14 = win["s14"]
        rec.at(s14 + 0.9)
        glide_click(manager, "button:has-text('Approve & place order')", 0.8)
        rec.at(s14 + 2.4)
        rec.box("s14", ".decision")
        glide_click(manager, "button:has-text('Yes, continue')", 0.7)
        expect(manager.locator(".decision").get_by_text("Order number")).to_be_visible(timeout=60000)
        rec.at(s14 + d14 - 2.6)
        smooth_scroll(manager, ".agent-log", "center")
        rec.stop(length, fps)
        meta["B"] = {"length": length, "zoomBoxes": rec.boxes}

        # ---------- C: chef, small order (s15–s16) ----------
        chef.goto(URL + "/#requests")
        chef.wait_for_selector("#ask")
        chef.evaluate("scrollTo(0, 0)")
        chef.wait_for_timeout(600)
        win, length = window("C")
        rec = Recorder(chef, "C")
        rec.start()
        s15, d15 = win["s15"]
        rec.at(s15 + 0.4)
        type_into(chef, "#ask", BUTTER, cps=40)
        glide_click(chef, "button[type=submit]:has-text('Continue')", 0.55)
        expect(chef.get_by_text("Here's what I understood")).to_be_visible(timeout=15000)
        smooth_scroll(chef, ".understood")
        chef.wait_for_timeout(500)
        glide_click(chef, "#dietaryConfirmed", 0.5)
        glide_click(chef, "[data-action=find]", 0.55)
        expect(chef.locator(".decision").get_by_text("Order number")).to_be_visible(timeout=60000)
        rec.stop(length, fps)
        meta["C"] = {"length": length, "zoomBoxes": rec.boxes}
        browser.close()
    (OUT / "index.json").write_text(json.dumps(meta, indent=1))


if __name__ == "__main__":
    main()
