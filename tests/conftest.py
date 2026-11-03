"""Fakes that let the whole core run without Ollama."""

from __future__ import annotations

import hashlib
import json
import math
import re

import pytest

from linkmate.config import AnswerConfig, RetrievalConfig
from linkmate.infra.index import ChromaIndex
from linkmate.infra.ollama_client import OllamaStatus
from linkmate.infra.store import ContactStore
from linkmate.services import Services
from linkmate.services.ask import AskService
from linkmate.services.capture import CaptureService
from linkmate.services.contacts import ContactService


def fake_embed(texts: list[str]) -> list[list[float]]:
    """Bag of hashed words: texts that share words get a high cosine similarity."""
    vectors = []
    for text in texts:
        vector = [0.0] * 1024
        for word in re.findall(r"[a-z0-9]+", text.lower()):
            if len(word) > 3 and word not in {"search_query", "search_document", "query", "search", "document"}:
                vector[int(hashlib.md5(word.encode()).hexdigest(), 16) % 1024] += 1.0
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        vectors.append([value / norm for value in vector])
    return vectors


class FakeLLM:
    """Returns scripted answers in order and records the prompts it was given."""

    def __init__(self, answers: list[str] | None = None):
        self.answers = list(answers or [])
        self.prompts: list[str] = []

    def chat_json(self, system: str, user: str, schema: dict, purpose: str = "chat") -> str:
        self.prompts.append(user)
        return self.answers.pop(0)

    def embed(self, texts: list[str]) -> list[list[float]]:
        return fake_embed(texts)

    def status(self) -> OllamaStatus:
        return OllamaStatus(True, "fake-chat", "fake-embed", True, True)


def profile_json(**fields) -> str:
    base = {
        "name": "", "organization": "", "role": "", "location": "", "met_context": "",
        "summary": "", "skills": [], "interests": [], "offers_help": [],
    }
    return json.dumps({**base, **fields})


RETRIEVAL = RetrievalConfig(mode="dense", top_k=20, threshold=0.2, bm25_threshold=0.5, max_candidates=5)
ANSWER = AnswerConfig(max_recommendations=3, notes_per_contact=3, max_note_chars=400)


@pytest.fixture
def llm() -> FakeLLM:
    return FakeLLM()


@pytest.fixture
def store(tmp_path) -> ContactStore:
    return ContactStore(tmp_path / "contacts")


@pytest.fixture
def index(tmp_path) -> ChromaIndex:
    return ChromaIndex(tmp_path / "chroma", fake_embed)


@pytest.fixture
def services(llm, store, index) -> Services:
    return Services(
        capture=CaptureService(llm, store, index),
        ask=AskService(llm, store, index, RETRIEVAL, ANSWER),
        contacts=ContactService(llm, store, index),
    )


