#!/usr/bin/env python3
"""Verify /latest's autoplay behavior in Chrome. Unlike the other scripts
in checks/, this drives a real browser and has real (dev-only) deps:
    pip install playwright && playwright install chromium
ffmpeg must also be on PATH (same requirement as tts.py itself).

This exists because the obvious fix -- autoplay muted, then unmute -- is
NOT enough on its own, and that took real trial and error to nail down:

1. Chrome only ever exempts elements with an actual video track from
   needing a user gesture before muted playback can start. A bare
   <audio> (or a <video> pointed at audio-only content) never gets this
   exemption, in any tested configuration -- which is why tts.py caches
   an MP4 with a minimal video track, and ArticleAudioPlayer.jsx plays it
   through a (visually hidden) <video>, not an <audio>, element.

2. Even with a video track, Chrome does not just let a silent unmute
   through: if a visitor has never interacted with the origin before, it
   actively re-pauses the element the moment script sets muted = false,
   logging "Unmuting failed and the element was paused instead because
   the user didn't interact with the document before." There is no way
   around this from a fresh visit with zero clicks -- it's deliberate,
   documented anti-autoplay-spam policy, not a bug to be worked around
   further. What we CAN guarantee, and what this checks:
     a. a first-time ("cold") visitor always gets a working player --
        never a UI that claims "playing" while audio is actually silently
        paused (see ArticleAudioPlayer.jsx's onPause handler).
     b. once a visitor has engaged with the site enough to cross Chrome's
        Media Engagement Index threshold for this origin, /latest really
        does autoplay audibly with zero further interaction. A fresh
        profile can't be given real MEI history, so this is simulated via
        --autoplay-policy=no-user-gesture-required, standing in for "a
        visitor Chrome already trusts to autoplay on this site".
"""
import os
import subprocess
import sys
import tempfile
import time
import urllib.request

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

PORT = 8632
BASE_URL = f"http://127.0.0.1:{PORT}"


def _make_fixture_cache(cache_dir, nid, lang):
    """A tiny synthetic MP4 (video track + tone) standing in for a real
    tts.py-generated file, so this test needs neither network access nor
    edge-tts -- only ffmpeg, which is already a hard dependency of the
    feature being tested."""
    os.makedirs(cache_dir, exist_ok=True)
    path = os.path.join(cache_dir, f"{nid}_{lang}.mp4")
    subprocess.run(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", "color=c=black:s=2x2:r=1",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=5",
            "-c:v", "libx264", "-tune", "stillimage", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "64k",
            "-shortest", "-movflags", "+faststart",
            path,
        ],
        check=True,
    )
    return path


def _wait_for_server(url, timeout=10):
    deadline = time.time() + timeout
    last_error = None
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=1)
            return
        except Exception as e:
            last_error = e
            time.sleep(0.2)
    raise RuntimeError(f"server did not start in time: {last_error}")


def _run_browser_checks():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        # 1. Cold visitor: default policy, brand new browser context.
        browser = p.chromium.launch()
        context = browser.new_context()
        page = context.new_page()
        page.goto(f"{BASE_URL}/#/latest")
        page.wait_for_timeout(3000)
        state = page.evaluate(
            """() => {
                const v = document.querySelector('video');
                const btn = document.querySelector('.audio-player-autoplay-fallback');
                return {
                    found: !!v,
                    paused: v && v.paused,
                    muted: v && v.muted,
                    currentTime: v && v.currentTime,
                    hasFallbackButton: !!btn,
                };
            }"""
        )
        browser.close()
        assert state["found"], "no <video> element rendered on /latest"
        played_for_real = state["paused"] is False and state["muted"] is False
        assert played_for_real or state["hasFallbackButton"], (
            f"cold visitor got neither real audible autoplay nor a fallback play button: {state}"
        )
        print(
            "OK: cold visitor gets a working player ("
            + ("played automatically" if played_for_real else "showed fallback play button")
            + ")"
        )

        # 2. Engaged visitor (simulated): must autoplay audibly, zero clicks.
        browser = p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
        context = browser.new_context()
        page = context.new_page()
        page.goto(f"{BASE_URL}/#/latest")
        page.wait_for_timeout(2000)
        state = page.evaluate(
            """() => {
                const v = document.querySelector('video');
                return {paused: v.paused, muted: v.muted, currentTime: v.currentTime};
            }"""
        )
        browser.close()
        assert state["paused"] is False, f"engaged visitor: expected playback, got {state}"
        assert state["muted"] is False, f"engaged visitor: expected audible playback, got {state}"
        assert state["currentTime"] > 0, f"engaged visitor: expected progress, got {state}"
        print("OK: an engaged visitor gets fully automatic, audible playback on /latest")


def main():
    import db

    subprocess.run(["npm", "run", "build"], cwd=os.path.join(REPO_ROOT, "frontend"), check=True)

    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "articles.db")
        conn = db.connect(db_path)
        db.upsert_article(conn, "1", "Test Article", "2026-01-01", "http://x/1", "Test body.", [])
        conn.commit()
        conn.close()

        cache_dir = os.path.join(tmp, "tts_cache")
        _make_fixture_cache(cache_dir, "1", "cmn")

        server_code = f"""
import db
db.DB_PATH = {db_path!r}
import tts
tts.CACHE_DIR = {cache_dir!r}
import server
server.DB_PATH = db.DB_PATH
import uvicorn
uvicorn.run(server.app, host="127.0.0.1", port={PORT})
"""
        server_proc = subprocess.Popen([sys.executable, "-c", server_code], cwd=REPO_ROOT)
        try:
            _wait_for_server(f"{BASE_URL}/api/years")
            _run_browser_checks()
        finally:
            server_proc.terminate()
            server_proc.wait(timeout=5)


if __name__ == "__main__":
    main()
