"""Thin client for the local Ollama service. Every chat call is logged."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

import requests

from linkmate.models import utc_now


EMBED_BATCH = 64


class OllamaError(Exception):
    pass


class OllamaUnavailable(OllamaError):
    """The Ollama service cannot be reached."""


class ModelMissing(OllamaError):
    """The model has not been downloaded."""

    def __init__(self, model: str):
        super().__init__(f"Model '{model}' is not installed. Run: ollama pull {model}")
        self.model = model


@dataclass(frozen=True)
class OllamaStatus:
    running: bool
    chat_model: str
    embed_model: str
    chat_model_ok: bool = False
    embed_model_ok: bool = False


def _has_model(installed: set[str], wanted: str) -> bool:
    return wanted in installed or f"{wanted}:latest" in installed


class OllamaClient:
    def __init__(
        self,
        host: str,
        chat_model: str,
        embed_model: str,
        temperature: float = 0,
        num_ctx: int = 4096,
        timeout: int = 180,
        log_path: Path | None = None,
    ):
        self.host = host
        self.chat_model = chat_model
        self.embed_model = embed_model
        self.temperature = temperature
        self.num_ctx = num_ctx
        self.timeout = timeout
        self.log_path = log_path

    def chat_json(self, system: str, user: str, schema: dict, purpose: str = "chat") -> str:
        """Ask the chat model for JSON that follows `schema` and return the raw text."""
        body = {
            "model": self.chat_model,
            "stream": False,
            "think": False,
            "format": schema,
            "options": {"temperature": self.temperature, "num_ctx": self.num_ctx},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        started = time.perf_counter()
        data = self._post("/api/chat", body, self.chat_model)
        output = data.get("message", {}).get("content", "")
        self._log(purpose, system, user, output, time.perf_counter() - started)
        return output

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors: list[list[float]] = []
        # Batches keep each request well below the timeout, also for a full reindex.
        for start in range(0, len(texts), EMBED_BATCH):
            batch = texts[start : start + EMBED_BATCH]
            data = self._post("/api/embed", {"model": self.embed_model, "input": batch}, self.embed_model)
            vectors.extend(data["embeddings"])
        return vectors

    def status(self) -> OllamaStatus:
        try:
            response = requests.get(f"{self.host}/api/tags", timeout=3)
            response.raise_for_status()
        except requests.RequestException:
            return OllamaStatus(False, self.chat_model, self.embed_model)
        installed = {model["name"] for model in response.json().get("models", [])}
        return OllamaStatus(
            True,
            self.chat_model,
            self.embed_model,
            _has_model(installed, self.chat_model),
            _has_model(installed, self.embed_model),
        )

    def _post(self, path: str, body: dict, model: str) -> dict:
        try:
            response = requests.post(f"{self.host}{path}", json=body, timeout=self.timeout)
        except requests.ConnectionError as exc:
            raise OllamaUnavailable(f"Ollama is not reachable at {self.host}") from exc
        except requests.Timeout as exc:
            raise OllamaError(f"Ollama did not answer within {self.timeout} s") from exc
        if response.status_code == 404:
            raise ModelMissing(model)
        if not response.ok:
            raise OllamaError(f"Ollama returned {response.status_code}: {response.text[:300]}")
        return response.json()

    def _log(self, purpose: str, system: str, user: str, output: str, seconds: float) -> None:
        if self.log_path is None:
            return
        record = {
            "time": utc_now().isoformat(),
            "purpose": purpose,
            "model": self.chat_model,
            "seconds": round(seconds, 3),
            "system": system,
            "prompt": user,
            "output": output,
        }
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("a", encoding="utf-8") as log:
                log.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError:
            pass  # a full disk must not break the user flow
