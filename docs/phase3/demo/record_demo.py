"""Record the prototype demo as a real input-to-output run against the running app.

Usage: python record_demo.py OUTPUT_DIR
Needs Playwright with Chromium. Starts LinkMate on a temporary seeded data folder, so
real contacts are never touched. All answers come from the local models, nothing is mocked.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[3]
PYTHON = ROOT / ".venv" / "bin" / "python"
PORT = 8599
START = 0.0
URL = f"http://localhost:{PORT}"
NOTE = (
    "Met Mara Lindt at the Granite climbing gym open day. She is a route setter and physio student "
    "in Long Beach. Said she can teach me to lead climb and check my technique on Sundays."
)


def wait_for_app() -> None:
    for _ in range(60):
        try:
            urllib.request.urlopen(f"{URL}/_stcore/health", timeout=2)
            return
        except OSError:
            time.sleep(1)
    raise RuntimeError("The app did not start.")


def scene(log: list, name: str) -> None:
    log.append({"scene": name, "at": round(time.time() - START, 1)})


def show_result(page, seconds: float) -> None:
    """Scroll through the answer at reading speed, for the voice-over."""
    page.mouse.move(800, 500)
    page.wait_for_timeout(int(seconds * 400))
    page.mouse.wheel(0, 420)
    page.wait_for_timeout(int(seconds * 600))
    page.mouse.wheel(0, -420)
    page.wait_for_timeout(300)


def ask(page, question: str, out: Path, shot: str, log: list, seconds: float) -> None:
    scene(log, shot)
    box = page.get_by_label("What do you need?")
    box.click()
    box.fill("")
    box.type(question, delay=28)
    page.wait_for_timeout(400)
    started = time.time()
    page.get_by_role("button", name="Ask", exact=True).click()
    try:
        page.wait_for_selector("text=Searching and asking", state="visible", timeout=3000)
    except PlaywrightTimeout:
        pass  # the answer came before the spinner could be seen
    page.wait_for_selector("text=Searching and asking", state="hidden", timeout=120000)
    page.wait_for_selector("text=Behind the answer", timeout=30000)
    page.wait_for_timeout(600)
    log.append({"question": question, "seconds": round(time.time() - started, 1), "text": page.locator("[data-testid=stMain]").first.inner_text()[:1500]})
    page.screenshot(path=str(out / f"{shot}.png"))
    show_result(page, seconds)


def main() -> None:
    out = Path(sys.argv[1]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    data = Path(tempfile.mkdtemp(prefix="linkmate-demo-"))
    env = {**os.environ, "LINKMATE_DATA_DIR": str(data)}
    subprocess.run([PYTHON, ROOT / "scripts" / "seed.py", "--reset"], env=env, check=True, cwd=ROOT)
    server = subprocess.Popen(
        [PYTHON, "-m", "streamlit", "run", "app/Home.py", "--server.port", str(PORT), "--server.headless", "true"],
        env=env, cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    log: list = []
    try:
        wait_for_app()
        with sync_playwright() as p:
            browser = p.chromium.launch()
            context = browser.new_context(
                viewport={"width": 1280, "height": 720}, record_video_dir=str(out), record_video_size={"width": 1280, "height": 720}
            )
            page = context.new_page()
            global START
            START = time.time()
            scene(log, "home")
            page.goto(URL)
            page.wait_for_selector("text=What do you want to do?", timeout=60000)
            page.wait_for_timeout(7000)
            page.screenshot(path=str(out / "home.png"))

            scene(log, "capture")
            page.goto(f"{URL}/Capture")
            page.wait_for_selector("text=Note or pasted email", timeout=30000)
            page.wait_for_timeout(1000)
            box = page.get_by_label("Note or pasted email")
            box.click()
            box.type(NOTE, delay=30)
            page.wait_for_timeout(600)
            page.get_by_role("button", name="Extract profile").click()
            page.wait_for_selector("text=Confirm and save", timeout=120000)
            page.wait_for_timeout(800)
            scene(log, "review")
            page.get_by_text("Review", exact=True).first.scroll_into_view_if_needed()
            page.mouse.move(800, 500)
            page.mouse.wheel(0, 460)
            page.wait_for_timeout(5000)
            page.screenshot(path=str(out / "review.png"))
            page.mouse.wheel(0, 360)
            page.wait_for_timeout(6000)
            page.get_by_role("button", name="Confirm and save").click()
            page.wait_for_selector("text=Saved", timeout=60000)
            page.wait_for_timeout(2500)
            page.screenshot(path=str(out / "saved.png"))

            page.goto(f"{URL}/Ask")
            page.wait_for_selector("text=What do you need?", timeout=30000)
            page.wait_for_timeout(800)
            for question, shot, seconds in (
                ("Who could teach me lead climbing?", "ask_new_contact", 9),
                ("Who could help me calibrate an IMU sensor for my project?", "ask_direct", 6),
                ("My knee started hurting after my long runs. Who could I ask?", "ask_indirect", 8),
                ("Who could photograph a wedding in Munich next spring?", "ask_weak", 11),
                ("Who can recommend a good veterinarian for my dog?", "ask_none", 3),
            ):
                ask(page, question, out, shot, log, seconds)

            scene(log, "contacts")
            page.goto(f"{URL}/Contacts")
            page.wait_for_selector("text=Filter by name or organization", timeout=30000)
            page.wait_for_timeout(800)
            page.get_by_label("Filter by name or organization").fill("Lindt")
            page.keyboard.press("Enter")
            page.wait_for_timeout(1500)
            page.get_by_text("Mara Lindt", exact=False).first.click()
            page.wait_for_timeout(6000)
            page.screenshot(path=str(out / "contact.png"))
            scene(log, "status")
            page.goto(f"{URL}/Status")
            page.wait_for_selector("text=Search index", timeout=30000)
            page.wait_for_timeout(6000)
            page.screenshot(path=str(out / "status.png"))
            context.close()
            browser.close()
    finally:
        server.terminate()
        server.wait(timeout=20)
        shutil.rmtree(data, ignore_errors=True)
    (out / "demo_log.json").write_text(json.dumps(log, indent=1, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
