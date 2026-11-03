"""Build a draft of the pitch video: slides plus demo recording, with a synthetic voice-over.

Usage: python build_video.py DEMO_DIR OUTPUT.mp4
Needs macOS `say`, ffmpeg and Playwright. DEMO_DIR comes from record_demo.py. The text is
docs/phase3/pitch_script.md, one section per slide. The draft shows timing and content and is
meant to be replaced by the team's own voices.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

PHASE3 = Path(__file__).resolve().parents[1]
FIGURES = PHASE3.parent / "figures"
VOICE = "Samantha"
RATE = "172"
DEMO_SCENES = ["home", "capture", "review", "ask_new_contact", "ask_direct", "ask_indirect", "ask_weak", "ask_none", "contacts"]
BLOBS = {"075b8bded3bfd0eaaaf430c84aaf9f18": "architecture.png", "d2023587ea64c77006c47ab7487a028f": "results_test.png"}
PAGE = """<!doctype html><html><head><meta charset="utf-8">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&display=swap">
<style>*{{box-sizing:border-box;margin:0}}body{{width:1920px;height:1080px;overflow:hidden}}
section{{width:1920px;height:1080px;position:relative}}aside{{display:none}}
table{{border-collapse:collapse;width:100%}}th,td{{padding:.35em .6em;border-bottom:1px solid #cfd5dc;text-align:left;font-weight:400}}th{{font-weight:700}}
ul,ol{{padding-left:1.2em}}</style></head><body>{slide}</body></html>"""


def run(*command) -> None:
    subprocess.run([str(part) for part in command], check=True, capture_output=True)


def duration(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    return float(out.stdout.strip())


def speak(text: str, path: Path) -> None:
    aiff = path.with_suffix(".aiff")
    run("say", "-v", VOICE, "-r", RATE, "-o", aiff, text)
    run("ffmpeg", "-y", "-i", aiff, "-ar", "44100", "-ac", "2", path)


def sections() -> list[str]:
    text = (PHASE3 / "pitch_script.md").read_text("utf-8")
    parts = re.split(r"^## \d+\. .*$", text, flags=re.MULTILINE)[1:]
    return [part.strip() for part in parts]


def render_slides(work: Path) -> list[Path]:
    deck = json.loads((PHASE3 / "slides" / "deck.json").read_text("utf-8"))
    images = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1920, "height": 1080})
        for slide_id in deck["order"]:
            html = (PHASE3 / "slides" / "slides" / f"{slide_id}.html").read_text("utf-8")
            for blob, name in BLOBS.items():
                html = html.replace(f"/_blob/{blob}", (FIGURES / name).as_uri())
            file = work / f"{slide_id}.html"
            file.write_text(PAGE.format(slide=html), "utf-8")
            page.goto(file.as_uri())
            page.wait_for_timeout(500)
            image = work / f"{slide_id}.png"
            page.screenshot(path=str(image))
            images.append(image)
        browser.close()
    return images


def slide_segment(image: Path, audio: Path, out: Path) -> None:
    length = duration(audio) + 0.8
    run("ffmpeg", "-y", "-loop", "1", "-framerate", "15", "-i", image, "-i", audio, "-af", "adelay=300|300,apad",
        "-t", f"{length:.2f}", "-vf", "scale=1920:1080", "-c:v", "libx264", "-tune", "stillimage", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-ar", "44100", "-ac", "2", out)


def demo_segment(demo: Path, bullets: list[str], work: Path, out: Path) -> None:
    video = next(demo.glob("*.webm"))
    log = json.loads((demo / "demo_log.json").read_text("utf-8"))
    scenes = {item["scene"]: item["at"] for item in log if "scene" in item}
    clips, cursor = [], 0.0
    for number, (name, line) in enumerate(zip(DEMO_SCENES, bullets)):
        clip = work / f"demo_{number}.wav"
        speak(line, clip)
        start = max(scenes.get(name, cursor), cursor)
        clips.append((clip, start))
        cursor = start + duration(clip) + 0.3
    inputs, filters = [], []
    for index, (clip, start) in enumerate(clips):
        inputs += ["-i", clip]
        filters.append(f"[{index + 1}:a]adelay={int(start * 1000)}|{int(start * 1000)}[a{index}]")
    mix = "".join(f"[a{i}]" for i in range(len(clips))) + f"amix=inputs={len(clips)}:normalize=0[a]"
    video_length = duration(video)
    hold = max(0.0, cursor - video_length + 0.5)
    run("ffmpeg", "-y", "-i", video, *inputs, "-filter_complex",
        ";".join(filters + [mix, f"[0:v]scale=1920:1080,tpad=stop_mode=clone:stop_duration={hold:.2f},fps=15[v]"]),
        "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "44100", "-ac", "2", out)


def main() -> None:
    demo, output = Path(sys.argv[1]), Path(sys.argv[2]).resolve()
    with tempfile.TemporaryDirectory() as folder:
        work = Path(folder)
        images = render_slides(work)
        texts = sections()
        segments = []
        for number, (image, text) in enumerate(zip(images, texts)):
            if image.stem == "demo":
                title = work / "demo_title.wav"
                speak("Now the demo of the running prototype.", title)
                segment = work / "seg_demo_title.mp4"
                slide_segment(image, title, segment)
                segments.append(segment)
                bullets = [line[2:].strip() for line in text.splitlines() if line.startswith("- ")]
                segment = work / "seg_demo.mp4"
                demo_segment(demo, bullets, work, segment)
                segments.append(segment)
                continue
            audio = work / f"voice_{number}.wav"
            speak(text, audio)
            segment = work / f"seg_{number}.mp4"
            slide_segment(image, audio, segment)
            segments.append(segment)
        listing = work / "list.txt"
        listing.write_text("".join(f"file '{segment}'\n" for segment in segments), "utf-8")
        run("ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", listing, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "15", "-c:a", "aac", output)
        for image in images:
            (output.parent / "slide_images").mkdir(exist_ok=True)
            (output.parent / "slide_images" / image.name).write_bytes(image.read_bytes())
    print(f"{output}: {duration(output) / 60:.1f} min")


if __name__ == "__main__":
    main()
