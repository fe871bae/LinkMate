"""Contact list, deletion, index maintenance and system status."""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from linkmate.core.merge import apply_edit
from linkmate.core.retrieval import entries_for_contact
from linkmate.infra.ollama_client import OllamaStatus
from linkmate.models import Contact, ProfileDraft, utc_now


@dataclass
class SystemStatus:
    ollama: OllamaStatus
    contact_count: int
    corrupt_files: list[str] = field(default_factory=list)
    index_entries: int = 0
    index_missing: int = 0
    index_extra: int = 0
    llm_calls: int = 0
    llm_average_seconds: float = 0.0

    @property
    def index_in_sync(self) -> bool:
        return self.index_missing == 0 and self.index_extra == 0


class ContactService:
    def __init__(self, llm, store, index, llm_log_path=None):
        self._llm = llm
        self._store = store
        self._index = index
        self._llm_log_path = llm_log_path

    def list_contacts(self) -> list[Contact]:
        return sorted(self._store.all(), key=lambda contact: contact.name.lower())

    def get(self, contact_id: str) -> Contact | None:
        return self._store.get(contact_id)

    def delete_contact(self, contact_id: str) -> str:
        self._store.delete(contact_id)
        try:
            self._index.delete_contact(contact_id)
        except Exception as exc:
            return str(exc)
        return ""

    def delete_note(self, contact_id: str, note_id: str) -> str:
        """Remove a note and the facts that only this note supported."""
        contact = self._store.get(contact_id)
        if contact is None:
            raise ValueError(f"Contact {contact_id} does not exist.")
        if len(contact.notes) == 1:
            raise ValueError("This is the last note. Delete the contact instead.")
        contact.notes = [note for note in contact.notes if note.id != note_id]
        kept = []
        for fact in contact.facts:
            # A fact without any source was typed by the user in an edit and stays.
            if note_id in fact.source_note_ids and len(fact.source_note_ids) == 1:
                continue
            fact.source_note_ids = [source for source in fact.source_note_ids if source != note_id]
            kept.append(fact)
        contact.facts = kept
        contact.updated_at = utc_now()
        self._store.save(contact)
        try:
            self._index.upsert_contact(contact)
        except Exception as exc:
            return str(exc)
        return ""

    def update_contact(self, contact_id: str, draft: ProfileDraft) -> str:
        """Save a profile the user edited. Notes stay as written, only profile fields and facts change."""
        contact = self._store.get(contact_id)
        if contact is None:
            raise ValueError(f"Contact {contact_id} does not exist.")
        if not draft.name.strip():
            raise ValueError("A contact needs a name.")
        updated = apply_edit(contact, draft)
        self._store.save(updated)
        try:
            self._index.upsert_contact(updated)
        except Exception as exc:
            return str(exc)
        return ""

    def export_json(self) -> str:
        """All contacts with their notes, so the data can leave with the user."""
        contacts = [contact.model_dump(mode="json") for contact in self.list_contacts()]
        return json.dumps({"exported_at": utc_now().isoformat(), "contacts": contacts}, indent=2, ensure_ascii=False)

    def rebuild_index(self) -> None:
        self._index.rebuild(self._store.all())

    def clear_llm_log(self) -> None:
        """The log holds note texts, so deleting a contact does not remove them from it."""
        if self._llm_log_path is not None:
            self._llm_log_path.unlink(missing_ok=True)

    def status(self) -> SystemStatus:
        contacts, corrupt = self._store.load_all()
        expected = {entry.id for contact in contacts for entry in entries_for_contact(contact)}
        try:
            indexed = self._index.entry_ids()
        except Exception:  # a damaged index shows up as out of sync, with a rebuild button
            indexed = set()
        calls, average = self._llm_stats()
        return SystemStatus(
            ollama=self._llm.status(),
            contact_count=len(contacts),
            corrupt_files=corrupt,
            index_entries=len(indexed),
            index_missing=len(expected - indexed),
            index_extra=len(indexed - expected),
            llm_calls=calls,
            llm_average_seconds=average,
        )

    def _llm_stats(self) -> tuple[int, float]:
        if self._llm_log_path is None or not self._llm_log_path.exists():
            return 0, 0.0
        seconds = []
        with self._llm_log_path.open(encoding="utf-8") as log:
            for line in log:
                try:
                    seconds.append(json.loads(line)["seconds"])
                except (ValueError, KeyError):
                    continue
        return len(seconds), sum(seconds) / len(seconds) if seconds else 0.0
