#!/usr/bin/env python3
"""Set up and start LinkMate with one command, on macOS, Windows and Linux.

Usage: python start_linkmate.py [--yes] [--no-browser] [--port N] [--package]

Every start checks what is missing, sets it up, starts the app and opens the
browser. When the app stops, the models are unloaded from memory, and Ollama is
stopped if this script started it.

This file only uses the standard library and simple syntax, because it runs
before the project's environment exists, possibly on an old Python version.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MIN_PYTHON = (3, 10)
PYTHON_DOWNLOAD = "https://www.python.org/downloads/"
OLLAMA_DOWNLOAD = "https://ollama.com/download"
DEFAULT_PORT = 8501
STEPS = 6
FIRST_START_DOWNLOAD = "about 1.6 GB"

PACKAGE_SKIP_DIRS = {".venv", ".venv.nosync", "__pycache__", ".pytest_cache", "dist", ".git", ".git.nosync"}
PACKAGE_SKIP_PATHS = {"data/contacts", "data/chroma.nosync", "data/logs"}

# Ollama on localhost must not go through a proxy, also on company laptops.
LOCAL = urllib.request.build_opener(urllib.request.ProxyHandler({}))


class SetupError(Exception):
    def __init__(self, message, hint=""):
        super().__init__(message)
        self.hint = hint


def step(number, text):
    print("[{}/{}] {}".format(number, STEPS, text), flush=True)


def done(text):
    print("      ok: {}".format(text), flush=True)


def is_windows():
    return platform.system() == "Windows"


def is_mac():
    return platform.system() == "Darwin"


def pause():
    if sys.stdin is not None and sys.stdin.isatty():
        try:
            input("\nPress Enter to close this window.")
        except EOFError:
            pass


def ask(question, assume_yes):
    if assume_yes:
        return True
    if sys.stdin is None or not sys.stdin.isatty():
        return False
    try:
        return input(question + " [Y/n] ").strip().lower() in ("", "y", "yes", "j", "ja")
    except EOFError:
        return False


# --- Python and the virtual environment ---------------------------------------


def check_python():
    version = sys.version_info[:3]
    if version[:2] < MIN_PYTHON:
        raise SetupError(
            "Python {}.{} or newer is needed, this is {}.{}.".format(*MIN_PYTHON, *version[:2]),
            "Install a current version from {} and start LinkMate again.".format(PYTHON_DOWNLOAD),
        )
    return "{}.{}.{}".format(*version)


def venv_python(root=ROOT):
    if is_windows():
        return root / ".venv" / "Scripts" / "python.exe"
    return root / ".venv" / "bin" / "python"


def read_requirements(root=ROOT):
    pins = {}
    for line in (root / "requirements.txt").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "==" in line:
            name, version = line.split("==", 1)
            pins[name.strip()] = version.strip()
    return pins


def environment_is_ready(root=ROOT):
    python = venv_python(root)
    if not python.exists():
        return False
    check = (
        "import importlib.metadata as m, sys\n"
        "pins = {!r}\n"
        "sys.exit(any(m.version(name) != version for name, version in pins.items()))\n"
    ).format(read_requirements(root))
    try:
        return subprocess.run([str(python), "-c", check], capture_output=True, timeout=120).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False  # e.g. an environment copied from another computer


def remove_environment(root=ROOT):
    for name in (".venv", ".venv.nosync"):
        path = root / name
        if path.is_symlink() or path.is_file():
            path.unlink()
        elif path.exists():
            shutil.rmtree(path)


def create_environment(root=ROOT):
    remove_environment(root)
    # On a Mac the project often lives in iCloud Drive, which skips .nosync folders.
    folder = root / (".venv.nosync" if is_mac() else ".venv")
    result = subprocess.run([sys.executable, "-m", "venv", str(folder)], capture_output=True, text=True)
    if result.returncode != 0:
        raise SetupError(
            "Could not create the Python environment:\n" + result.stderr.strip()[-400:],
            "On Debian or Ubuntu, install it with: sudo apt install python3-venv",
        )
    if is_mac():
        (root / ".venv").symlink_to(folder.name)

    command = [str(venv_python(root)), "-m", "pip", "install", "--disable-pip-version-check", "-r", "requirements.txt"]
    process = subprocess.Popen(
        command, cwd=str(root), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace"
    )
    log = []
    count = 0
    for line in process.stdout:
        log.append(line)
        if line.startswith("Collecting "):
            count += 1
            package = re.split(r"[<>=!~\[(]", line.split()[1])[0]
            print("\r      downloading package {}: {:<40}".format(count, package[:40]), end="", flush=True)
        elif line.startswith("Installing collected packages"):
            print("\r      installing {} packages ...{:<40}".format(count, ""), end="", flush=True)
    print(flush=True)
    if process.wait() != 0:
        raise SetupError(
            "Could not install the Python packages:\n" + "".join(log[-8:]).strip(),
            "Check the internet connection and start LinkMate again.",
        )


def read_settings(root=ROOT):
    code = (
        "import json\n"
        "from linkmate.config import load_config\n"
        "c = load_config()\n"
        "print(json.dumps({'host': c.ollama.host, 'models': [c.llm.model, c.embedding.model],"
        " 'contacts': str(c.contacts_dir), 'chroma': str(c.chroma_dir), 'logs': str(c.llm_log_path.parent)}))\n"
    )
    result = subprocess.run([str(venv_python(root)), "-c", code], cwd=str(root), capture_output=True, text=True)
    if result.returncode != 0:
        raise SetupError("Could not read config.yaml:\n" + result.stderr.strip()[-400:])
    return json.loads(result.stdout)


# --- Ollama ---------------------------------------------------------------------


def api_get(host, path, timeout=3):
    with LOCAL.open(host + path, timeout=timeout) as response:
        return json.load(response)


def ollama_is_running(host):
    try:
        api_get(host, "/api/tags")
        return True
    except (OSError, ValueError):
        return False


def find_ollama():
    found = shutil.which("ollama")
    if found:
        return found
    candidates = [
        Path("/opt/homebrew/bin/ollama"),
        Path("/usr/local/bin/ollama"),
        Path("/Applications/Ollama.app/Contents/Resources/ollama"),
    ]
    if os.environ.get("LOCALAPPDATA"):
        candidates.append(Path(os.environ["LOCALAPPDATA"]) / "Programs" / "Ollama" / "ollama.exe")
    for path in candidates:
        if path.exists():
            return str(path)
    return None


def ollama_install_command():
    """The installer for this system, or None if it has to be done by hand."""
    if is_windows() and shutil.which("winget"):
        return ["winget", "install", "--id", "Ollama.Ollama", "-e", "--accept-source-agreements",
                "--accept-package-agreements"]
    if is_mac() and shutil.which("brew"):
        return ["brew", "install", "ollama"]
    if platform.system() == "Linux" and shutil.which("curl"):
        return ["sh", "-c", "curl -fsSL https://ollama.com/install.sh | sh"]
    return None


def install_ollama(assume_yes):
    command = ollama_install_command()
    if command:
        shown = " ".join(command[2:] if command[0] == "sh" else command)
        print("      Ollama runs the AI models on this computer and is not installed yet.")
        if ask("      Install Ollama now with: {}?".format(shown), assume_yes):
            subprocess.run(command)
            found = find_ollama()
            if found:
                return found
            print("      The automatic installation did not work.")

    print("      Please install Ollama from {}".format(OLLAMA_DOWNLOAD))
    if sys.stdin is None or not sys.stdin.isatty():
        raise SetupError("Ollama is not installed.", "Install it from {} and start LinkMate again.".format(OLLAMA_DOWNLOAD))
    webbrowser.open(OLLAMA_DOWNLOAD)
    for _ in range(3):
        try:
            input("      Press Enter when it is installed ...")
        except EOFError:
            break
        found = find_ollama()
        if found:
            return found
        print("      Ollama was not found yet.")
    raise SetupError("Ollama is not installed.", "Install it from {} and start LinkMate again.".format(OLLAMA_DOWNLOAD))


def ollama_environment(host):
    """Point the ollama command at the host from config.yaml, if it is not the default."""
    environment = dict(os.environ)
    parsed = urllib.parse.urlparse(host)
    if parsed.port and parsed.port != 11434:
        environment["OLLAMA_HOST"] = "{}:{}".format(parsed.hostname, parsed.port)
    return environment


def start_ollama(ollama, host):
    """Start Ollama if needed. Returns the process if this script started it."""
    if ollama_is_running(host):
        return None
    process = subprocess.Popen(
        [ollama, "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=ollama_environment(host)
    )
    for _ in range(30):
        if ollama_is_running(host):
            return process
        time.sleep(1)
    process.terminate()
    raise SetupError("Ollama did not start.", "Try to start it by hand with: ollama serve")


def has_model(installed, wanted):
    return wanted in installed or wanted + ":latest" in installed


def overall_progress(layers):
    total = sum(layer[1] for layer in layers.values())
    completed = sum(layer[0] for layer in layers.values())
    return completed, total


def pull_model(host, model):
    body = json.dumps({"model": model, "stream": True}).encode("utf-8")
    request = urllib.request.Request(host + "/api/pull", data=body, headers={"Content-Type": "application/json"})
    layers = {}
    try:
        with LOCAL.open(request, timeout=600) as response:
            for line in response:
                event = json.loads(line)
                if "error" in event:
                    raise SetupError("Could not download {}: {}".format(model, event["error"]))
                if event.get("total"):
                    layers[event.get("digest", "")] = (event.get("completed", 0), event["total"])
                    completed, total = overall_progress(layers)
                    print(
                        "\r      {}: {:3d}% of {} MB   ".format(model, completed * 100 // total, total // 1000000),
                        end="",
                        flush=True,
                    )
                elif event.get("status") == "success" and layers:
                    print("\r      {}: 100% of {} MB   ".format(model, overall_progress(layers)[1] // 1000000), end="", flush=True)
    except (OSError, ValueError) as error:
        raise SetupError(
            "Could not download {}: {}".format(model, error), "Check the internet connection and try again."
        )
    print(flush=True)


def ensure_models(host, models):
    installed = {model["name"] for model in api_get(host, "/api/tags", timeout=10).get("models", [])}
    missing = [model for model in models if not has_model(installed, model)]
    for model in missing:
        pull_model(host, model)
    return missing


def unload_models(ollama, host, models):
    for model in models:
        subprocess.run(
            [ollama, "stop", model],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=ollama_environment(host),
        )


# --- Data ---------------------------------------------------------------------


def run_script(script, root=ROOT):
    result = subprocess.run(
        [str(venv_python(root)), str(Path("scripts") / script)], cwd=str(root), capture_output=True, text=True
    )
    if result.returncode != 0:
        raise SetupError("{} failed:\n{}".format(script, result.stderr.strip()[-600:]))


def ensure_data(settings, root=ROOT):
    contacts = Path(settings["contacts"])
    if not contacts.exists():
        run_script("seed.py", root)
        return "loaded the synthetic test contacts"
    if any(contacts.glob("c_*.json")) and not (Path(settings["chroma"]) / "chroma.sqlite3").exists():
        run_script("reindex.py", root)
        return "rebuilt the search index"
    return "{} contacts".format(len(list(contacts.glob("c_*.json"))))


# --- The app --------------------------------------------------------------------


def app_is_up(port):
    try:
        with LOCAL.open("http://localhost:{}/_stcore/health".format(port), timeout=2) as response:
            return response.status == 200
    except (OSError, ValueError):
        return False


def port_is_free(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        return probe.connect_ex(("127.0.0.1", port)) != 0


def choose_port(preferred):
    for port in range(preferred, preferred + 10):
        if port_is_free(port):
            return port
    raise SetupError("Ports {} to {} are all in use.".format(preferred, preferred + 9))


def run_app(port, open_browser, logs, root=ROOT):
    """Start the server and wait until it stops, through the button in the app or Ctrl+C."""
    url = "http://localhost:{}".format(port)
    logs.mkdir(parents=True, exist_ok=True)
    log_path = logs / "app.log"
    environment = dict(os.environ)
    environment["NO_PROXY"] = "localhost,127.0.0.1"
    with log_path.open("w", encoding="utf-8") as log:
        app = subprocess.Popen(
            [str(venv_python(root)), "-m", "streamlit", "run", str(Path("app") / "Home.py"), "--server.port", str(port), "--server.address", "localhost", "--browser.gatherUsageStats", "false"],
            cwd=str(root),
            stdout=log,
            stderr=subprocess.STDOUT,
            env=environment,
        )
        try:
            for _ in range(60):
                if app_is_up(port):
                    break
                if app.poll() is not None:
                    tail = log_path.read_text(encoding="utf-8", errors="replace")[-600:]
                    raise SetupError("The app did not start:\n" + tail)
                time.sleep(1)
            else:
                raise SetupError("The app did not answer within a minute.", "See {}".format(log_path))

            done("LinkMate is running at {}".format(url))
            print("\nTo stop it, click 'Shut down LinkMate' in the app, or press Ctrl+C here.\n", flush=True)
            if open_browser:
                webbrowser.open(url)
            app.wait()
        except KeyboardInterrupt:
            pass
        finally:
            if app.poll() is None:
                app.terminate()
                try:
                    app.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    app.kill()


# --- Package for a colleague -----------------------------------------------------


def package_is_skipped(relative):
    parts = relative.parts
    if any(part in PACKAGE_SKIP_DIRS for part in parts) or relative.name == ".DS_Store":
        return True
    posix = relative.as_posix()
    return any(posix == path or posix.startswith(path + "/") for path in PACKAGE_SKIP_PATHS)


def package(root=ROOT, target=None):
    """Zip the project without environments, private contacts, the index and logs."""
    target = target or root / "dist" / "linkmate.zip"
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(str(target), "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(root.rglob("*")):
            relative = path.relative_to(root)
            if path.is_file() and not path.is_symlink() and not package_is_skipped(relative):
                archive.write(str(path), str(Path("linkmate") / relative))
    return target


# --- Start ----------------------------------------------------------------------


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Set up and start LinkMate.")
    parser.add_argument("--yes", action="store_true", help="install Ollama without asking")
    parser.add_argument("--no-browser", action="store_true", help="do not open the browser")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="preferred port of the app")
    parser.add_argument("--package", action="store_true", help="only create dist/linkmate.zip for a colleague")
    return parser.parse_args(argv)


def stop_on_signal(*_):
    raise KeyboardInterrupt


def start(args):
    if app_is_up(args.port):
        url = "http://localhost:{}".format(args.port)
        print("LinkMate is already running at {}".format(url))
        if not args.no_browser:
            webbrowser.open(url)
        return

    print("LinkMate: checking the setup. The first start downloads {}.\n".format(FIRST_START_DOWNLOAD), flush=True)

    step(1, "Python")
    done(check_python())

    step(2, "Python environment and packages")
    if environment_is_ready():
        done("ready")
    else:
        create_environment()
        if not environment_is_ready():
            raise SetupError("The Python environment is still incomplete after the installation.")
        done("installed")
    settings = read_settings()
    host, models = settings["host"], settings["models"]

    step(3, "Ollama")
    ollama = find_ollama() or install_ollama(args.yes)
    ollama_process = start_ollama(ollama, host)
    done("started" if ollama_process else "running")

    try:
        step(4, "AI models")
        missing = ensure_models(host, models)
        done("downloaded {}".format(", ".join(missing)) if missing else ", ".join(models))

        step(5, "Contacts and search index")
        done(ensure_data(settings))

        step(6, "Starting the app")
        run_app(choose_port(args.port), not args.no_browser, Path(settings["logs"]))
    finally:
        print("Shutting down: unloading the models ...", flush=True)
        unload_models(ollama, host, models)
        if ollama_process is not None:
            ollama_process.terminate()
            try:
                ollama_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                ollama_process.kill()
    print("LinkMate has stopped.", flush=True)


def main(argv=None):
    args = parse_args(argv)
    signal.signal(signal.SIGINT, stop_on_signal)
    signal.signal(signal.SIGTERM, stop_on_signal)
    if hasattr(signal, "SIGHUP"):
        signal.signal(signal.SIGHUP, stop_on_signal)
    try:
        if args.package:
            print("Created {}".format(package()))
        else:
            start(args)
        return 0
    except KeyboardInterrupt:
        print("\nStopped.")
        return 0
    except SetupError as error:
        print("\nLinkMate could not start: {}".format(error))
        if error.hint:
            print(error.hint)
        pause()
        return 1


if __name__ == "__main__":
    sys.exit(main())
