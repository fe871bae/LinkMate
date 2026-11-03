"""Shared helpers for the Streamlit pages. Pages only talk to services."""

from __future__ import annotations

import os
import re
import signal
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st
import streamlit.components.v1 as components

from linkmate.config import load_config
from linkmate.models import ProfileDraft
from linkmate.services import OllamaError, Services, build_services
from linkmate.services.contacts import SystemStatus


SHUTDOWN_DELAY_SECONDS = 1.0


@st.cache_resource(show_spinner="Loading LinkMate ...")
def get_services() -> Services:
    return build_services(load_config())


def setup_page(title: str, icon: str) -> None:
    """Page settings and the sidebar that every page shares."""
    st.set_page_config(page_title=title, page_icon=icon, layout="wide")
    if st.sidebar.button("Shut down LinkMate", help="Stops the app and frees the memory the models use."):
        shut_down()


def shut_down() -> None:
    """Stop the server. The start script then unloads the models and stops what it started."""
    # Replace the page first, because the browser would otherwise show a connection error.
    components.html(
        "<script>window.parent.document.body.innerHTML ="
        " '<h2 style=\"font-family:sans-serif;text-align:center;margin-top:20vh\">"
        "LinkMate has stopped. You can close this tab.</h2>';</script>"
    )
    threading.Timer(SHUTDOWN_DELAY_SECONDS, stop_server).start()
    st.stop()


def stop_server() -> None:
    os.kill(os.getpid(), signal.SIGTERM)


def safe_md(text: str) -> str:
    """Escape text from notes or the LLM before Markdown renders it. Otherwise a pasted
    email could make the browser load an image from any server, and that would break
    the promise that no data leaves the laptop."""
    return re.sub(r"([\\`*_{}\[\]()<>#+\-.!|~$:^&])", r"\\\1", text)


def show_system_banner(status: SystemStatus) -> bool:
    """Show what is wrong with Ollama. Returns True if capture and ask can run."""
    ollama = status.ollama
    if not ollama.running:
        st.error("Ollama is not running, so capture and ask are disabled. Start it with `ollama serve`.")
        return False
    missing = [
        model
        for model, installed in (
            (ollama.chat_model, ollama.chat_model_ok),
            (ollama.embed_model, ollama.embed_model_ok),
        )
        if not installed
    ]
    if missing:
        commands = "\n".join(f"ollama pull {model}" for model in missing)
        st.error("Models are missing, so capture and ask are disabled. Install them with:")
        st.code(commands, language="bash")
        return False
    if not status.index_in_sync:
        st.warning("The search index is out of sync with the contacts. Rebuild it on the Status page.")
    return True


def show_ollama_error(error: OllamaError) -> None:
    st.error(f"Ollama problem: {safe_md(str(error))}")


def profile_form_fields(draft: ProfileDraft, key: str) -> ProfileDraft:
    """The profile form used by the capture review and by the edit dialog. Call inside st.form."""
    name = st.text_input("Name", draft.name, key=f"name_{key}")
    aliases = st.text_input("Aliases (comma separated)", ", ".join(draft.aliases), key=f"aliases_{key}")
    left, right = st.columns(2)
    organization = left.text_input("Organization", draft.organization, key=f"organization_{key}")
    role = right.text_input("Role", draft.role, key=f"role_{key}")
    location = left.text_input("Location", draft.location, key=f"location_{key}")
    met_context = right.text_input("Where met", draft.met_context, key=f"met_context_{key}")
    summary = st.text_area("Summary", draft.summary, height=80, key=f"summary_{key}")
    first, second, third = st.columns(3)
    skills = first.text_area("Skills (one per line)", "\n".join(draft.skills), height=140, key=f"skills_{key}")
    interests = second.text_area("Interests (one per line)", "\n".join(draft.interests), height=140, key=f"interests_{key}")
    offers_help = third.text_area(
        "Offers of help (one per line)", "\n".join(draft.offers_help), height=140, key=f"offers_help_{key}"
    )
    return ProfileDraft(
        name=name,
        aliases=[alias.strip() for alias in aliases.split(",") if alias.strip()],
        organization=organization,
        role=role,
        location=location,
        met_context=met_context,
        summary=summary,
        skills=_split_lines(skills),
        interests=_split_lines(interests),
        offers_help=_split_lines(offers_help),
    )


def _split_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def render_sources(sources) -> None:
    for source in sources:
        date = source.created_at.strftime("%Y-%m-%d")
        st.caption(f"{source.source_type} from {date} · {source.note_id}")
        st.text(source.text)
