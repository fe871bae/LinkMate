"""Load config.yaml into typed settings."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class OllamaConfig:
    host: str
    timeout_seconds: int


@dataclass(frozen=True)
class LLMConfig:
    model: str
    temperature: float
    num_ctx: int


@dataclass(frozen=True)
class EmbeddingConfig:
    model: str
    query_prefix: str
    document_prefix: str


@dataclass(frozen=True)
class RetrievalConfig:
    mode: str
    top_k: int
    threshold: float
    bm25_threshold: float
    max_candidates: int


@dataclass(frozen=True)
class AnswerConfig:
    max_recommendations: int
    notes_per_contact: int
    max_note_chars: int
    strong_from: float = 0.67


@dataclass(frozen=True)
class Config:
    ollama: OllamaConfig
    llm: LLMConfig
    embedding: EmbeddingConfig
    retrieval: RetrievalConfig
    answer: AnswerConfig
    data_dir: Path

    @property
    def contacts_dir(self) -> Path:
        return self.data_dir / "contacts"

    @property
    def chroma_dir(self) -> Path:
        # The .nosync suffix keeps the derived index out of iCloud Drive,
        # which can corrupt a live SQLite file while syncing it.
        return self.data_dir / "chroma.nosync"

    @property
    def llm_log_path(self) -> Path:
        return self.data_dir / "logs" / "llm_calls.jsonl"


def load_config(path: Path | str | None = None) -> Config:
    config_path = Path(path) if path else PROJECT_ROOT / "config.yaml"
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    ollama = dict(raw["ollama"])
    ollama["host"] = os.environ.get("LINKMATE_OLLAMA_HOST", ollama["host"]).rstrip("/")

    data_dir = Path(os.environ.get("LINKMATE_DATA_DIR", raw["data_dir"]))
    if not data_dir.is_absolute():
        data_dir = PROJECT_ROOT / data_dir

    return Config(
        ollama=OllamaConfig(**ollama),
        llm=LLMConfig(**raw["llm"]),
        embedding=EmbeddingConfig(**raw["embedding"]),
        retrieval=RetrievalConfig(**raw["retrieval"]),
        answer=AnswerConfig(**raw["answer"]),
        data_dir=data_dir,
    )
