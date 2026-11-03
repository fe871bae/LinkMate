"""The UI and scripts only talk to these services."""

from __future__ import annotations

from dataclasses import dataclass

from linkmate.config import Config
from linkmate.infra.index import ChromaIndex
from linkmate.infra.ollama_client import OllamaClient, OllamaError
from linkmate.infra.store import ContactStore
from linkmate.services.ask import AskService
from linkmate.services.capture import CaptureService
from linkmate.services.contacts import ContactService

__all__ = ["OllamaError", "Services", "build_services"]


@dataclass
class Services:
    capture: CaptureService
    ask: AskService
    contacts: ContactService


def build_services(config: Config) -> Services:
    client = OllamaClient(
        host=config.ollama.host,
        chat_model=config.llm.model,
        embed_model=config.embedding.model,
        temperature=config.llm.temperature,
        num_ctx=config.llm.num_ctx,
        timeout=config.ollama.timeout_seconds,
        log_path=config.llm_log_path,
    )
    store = ContactStore(config.contacts_dir)
    index = ChromaIndex(
        config.chroma_dir, client.embed, config.embedding.query_prefix, config.embedding.document_prefix
    )
    return Services(
        capture=CaptureService(client, store, index),
        ask=AskService(client, store, index, config.retrieval, config.answer),
        contacts=ContactService(client, store, index, config.llm_log_path),
    )
