"""The start script: everything that can be checked without installing anything."""

import socket
import zipfile

import pytest

import start_linkmate as start


def test_environment_path_per_system(monkeypatch, tmp_path):
    monkeypatch.setattr(start, "is_windows", lambda: True)
    assert start.venv_python(tmp_path) == tmp_path / ".venv" / "Scripts" / "python.exe"
    monkeypatch.setattr(start, "is_windows", lambda: False)
    assert start.venv_python(tmp_path) == tmp_path / ".venv" / "bin" / "python"


def test_missing_environment_is_not_ready(tmp_path):
    assert not start.environment_is_ready(tmp_path)


def test_broken_environment_is_not_ready(monkeypatch, tmp_path):
    (tmp_path / "requirements.txt").write_text("streamlit==1.0\n")
    python = start.venv_python(tmp_path)
    python.parent.mkdir(parents=True)
    python.write_text("not a program")
    assert not start.environment_is_ready(tmp_path)


def test_requirements_are_read_as_pins(tmp_path):
    (tmp_path / "requirements.txt").write_text("# comment\nchromadb==1.5.9\n\nstreamlit==1.66.1\n")
    assert start.read_requirements(tmp_path) == {"chromadb": "1.5.9", "streamlit": "1.66.1"}


def test_remove_environment_handles_symlink_and_folder(tmp_path):
    (tmp_path / ".venv.nosync" / "bin").mkdir(parents=True)
    (tmp_path / ".venv").symlink_to(".venv.nosync")
    (tmp_path / "keep.txt").write_text("x")
    start.remove_environment(tmp_path)
    assert [path.name for path in tmp_path.iterdir()] == ["keep.txt"]


def test_model_names_match_with_and_without_latest():
    installed = {"nomic-embed-text:latest", "qwen3:0.6b"}
    assert start.has_model(installed, "nomic-embed-text")
    assert start.has_model(installed, "qwen3:0.6b")
    assert not start.has_model(installed, "qwen3:1.7b")


def test_download_progress_adds_up_all_layers():
    assert start.overall_progress({"a": (50, 100), "b": (0, 300)}) == (50, 400)


def test_custom_ollama_host_is_passed_on(monkeypatch):
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    assert "OLLAMA_HOST" not in start.ollama_environment("http://localhost:11434")
    assert start.ollama_environment("http://localhost:11555")["OLLAMA_HOST"] == "localhost:11555"


def test_install_command_per_system(monkeypatch):
    monkeypatch.setattr(start.shutil, "which", lambda name: "/bin/" + name)
    monkeypatch.setattr(start.platform, "system", lambda: "Windows")
    assert start.ollama_install_command()[0] == "winget"
    monkeypatch.setattr(start.platform, "system", lambda: "Darwin")
    assert start.ollama_install_command() == ["brew", "install", "ollama"]
    monkeypatch.setattr(start.platform, "system", lambda: "Linux")
    assert "install.sh" in start.ollama_install_command()[2]


def test_mac_without_homebrew_has_no_installer(monkeypatch):
    monkeypatch.setattr(start.shutil, "which", lambda name: None)
    monkeypatch.setattr(start.platform, "system", lambda: "Darwin")
    assert start.ollama_install_command() is None


def test_ollama_is_not_installed_without_consent(monkeypatch):
    monkeypatch.setattr(start, "ollama_install_command", lambda: ["brew", "install", "ollama"])
    monkeypatch.setattr(start, "ask", lambda question, assume_yes: False)
    monkeypatch.setattr(start.sys, "stdin", None)

    def forbidden(*args, **kwargs):
        raise AssertionError("must not run an installer")

    monkeypatch.setattr(start.subprocess, "run", forbidden)
    with pytest.raises(start.SetupError) as error:
        start.install_ollama(assume_yes=False)
    assert start.OLLAMA_DOWNLOAD in error.value.hint


def test_too_old_python_gives_a_clear_message(monkeypatch):
    monkeypatch.setattr(start.sys, "version_info", (3, 8, 10))
    with pytest.raises(start.SetupError) as error:
        start.check_python()
    assert "3.10" in str(error.value) and start.PYTHON_DOWNLOAD in error.value.hint


def test_busy_port_is_skipped():
    with socket.socket() as busy:
        busy.bind(("127.0.0.1", 0))
        busy.listen()
        port = busy.getsockname()[1]
        assert start.choose_port(port) != port


def test_package_leaves_out_environment_and_private_data(tmp_path):
    root = tmp_path / "project"
    for name in (
        "start_linkmate.py", "app/Home.py", "data/dataset/contacts/c_1.json",
        "data/contacts/c_private.json", "data/chroma.nosync/chroma.sqlite3", "data/logs/llm_calls.jsonl",
        ".venv.nosync/bin/python", "linkmate/__pycache__/x.pyc", "dist/old.zip", ".DS_Store",
    ):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x")
    (root / ".venv").symlink_to(".venv.nosync")

    target = start.package(root, tmp_path / "out.zip")
    names = set(zipfile.ZipFile(target).namelist())
    assert names == {
        "linkmate/start_linkmate.py", "linkmate/app/Home.py", "linkmate/data/dataset/contacts/c_1.json",
    }
