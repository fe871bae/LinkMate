"""Search index on Chroma. Derived from the store, can be rebuilt at any time."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Callable

import chromadb
from chromadb.api.shared_system_client import SharedSystemClient
from chromadb.config import Settings

from linkmate.core.retrieval import entries_for_contact
from linkmate.models import Contact, Entry, Hit

COLLECTION = "linkmate"
ADD_BATCH = 2000

Embedder = Callable[[list[str]], list[list[float]]]


class ChromaIndex:
    def __init__(self, path: Path, embed: Embedder, query_prefix: str = "", document_prefix: str = ""):
        self._path = path
        self._embed = embed
        self._query_prefix = query_prefix
        self._document_prefix = document_prefix
        try:
            self._connect()
        except Exception:
            # The index is derived data. Start empty, the status page then offers a rebuild.
            self._reset_folder()
            self._connect()

    def upsert_contact(self, contact: Contact) -> None:
        # Embed first: if Ollama fails, the old entries stay untouched.
        batch = self._embed_entries(entries_for_contact(contact))
        self.delete_contact(contact.id)
        self._add(batch)

    def delete_contact(self, contact_id: str) -> None:
        self._collection.delete(where={"contact_id": contact_id})

    def rebuild(self, contacts: list[Contact]) -> None:
        entries = [entry for contact in contacts for entry in entries_for_contact(contact)]
        batch = self._embed_entries(entries)
        # Start from an empty folder, so a rebuild also repairs a damaged or deleted index.
        self._reset_folder()
        self._connect()
        # On Windows an open database cannot be deleted, so it may still hold old entries.
        leftovers = self.entry_ids()
        if leftovers:
            self._collection.delete(ids=list(leftovers))
        self._add(batch)

    def query(self, question: str, top_k: int) -> list[Hit]:
        count = self._collection.count()
        if count == 0:
            return []
        vector = self._embed([f"{self._query_prefix}{question}"])[0]
        result = self._collection.query(
            query_embeddings=[vector],
            n_results=min(top_k, count),
            include=["documents", "metadatas", "distances"],
        )
        hits = []
        for entry_id, text, metadata, distance in zip(
            result["ids"][0], result["documents"][0], result["metadatas"][0], result["distances"][0]
        ):
            entry = Entry(entry_id, metadata["contact_id"], metadata["note_id"], metadata["doc_type"], text)
            hits.append(Hit(entry, 1.0 - distance))
        return hits

    def entry_ids(self) -> set[str]:
        return set(self._collection.get(include=[])["ids"])

    def _reset_folder(self) -> None:
        # Chroma caches open databases per path, so that cache has to go first.
        SharedSystemClient.clear_system_cache()
        shutil.rmtree(self._path, ignore_errors=True)

    def _connect(self) -> None:
        self._path.mkdir(parents=True, exist_ok=True)
        # Telemetry off: no data leaves the laptop. embedding_function=None makes
        # sure Chroma never downloads its default model behind our back.
        self._client = chromadb.PersistentClient(path=str(self._path), settings=Settings(anonymized_telemetry=False))
        self._collection = self._client.get_or_create_collection(
            COLLECTION, metadata={"hnsw:space": "cosine"}, embedding_function=None
        )

    def _embed_entries(self, entries: list[Entry]) -> list[tuple[Entry, list[float]]]:
        vectors = self._embed([f"{self._document_prefix}{entry.text}" for entry in entries])
        return list(zip(entries, vectors))

    def _add(self, batch: list[tuple[Entry, list[float]]]) -> None:
        # Chroma limits the size of one add call.
        for start in range(0, len(batch), ADD_BATCH):
            part = batch[start : start + ADD_BATCH]
            self._collection.add(
                ids=[entry.id for entry, _ in part],
                embeddings=[vector for _, vector in part],
                documents=[entry.text for entry, _ in part],
                metadatas=[
                    {"contact_id": entry.contact_id, "note_id": entry.note_id, "doc_type": entry.doc_type}
                    for entry, _ in part
                ],
            )
