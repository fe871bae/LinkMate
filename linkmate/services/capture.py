"""Flow A: note -> LLM proposal -> user review -> save -> index."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from linkmate.core.extraction import clean_profile, unsupported_values
from linkmate.core.merge import ContactMatch, FieldChange, additive_draft, create_contact, find_matches, merge_into, preview_changes
from linkmate.core.sanitize import looks_like_injection, strip_injection
from linkmate.core.prompts import EXTRACTION_SYSTEM, PROFILE_SCHEMA, extraction_user_prompt
from linkmate.core.validation import InvalidLLMOutput, parse_profile
from linkmate.models import Contact, Note, ProfileDraft


@dataclass
class Proposal:
    note_text: str
    source_type: str
    draft: ProfileDraft
    matches: list[ContactMatch] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    extraction_failed: bool = False


@dataclass
class SaveResult:
    contact: Contact
    changes: list[FieldChange] = field(default_factory=list)
    index_error: str = ""


class CaptureService:
    def __init__(self, llm, store, index):
        self._llm = llm
        self._store = store
        self._index = index

    def propose(self, note_text: str, source_type: str = "note") -> Proposal:
        if not note_text.strip():
            raise ValueError("The note is empty.")
        draft = self._extract(note_text)
        if draft is None:
            return Proposal(note_text, source_type, ProfileDraft(), extraction_failed=True)
        matches = self.propose_matches(draft.name) if draft.name else []
        warnings = unsupported_values(draft, note_text)
        if looks_like_injection(note_text):
            warnings.insert(0, "This text contains instructions aimed at an AI. Check the proposed profile carefully.")
        return Proposal(note_text, source_type, draft, matches, warnings)

    def propose_matches(self, name: str) -> list[ContactMatch]:
        return find_matches(name, self._store.all())

    def preview(self, contact_id: str, draft: ProfileDraft) -> list[FieldChange]:
        contact = self._store.get(contact_id)
        return preview_changes(contact, draft) if contact else []

    def additive_review(self, contact_id: str, draft: ProfileDraft) -> tuple[Contact, ProfileDraft] | None:
        """The contact and the form values for adding a note to it. Nothing known gets lost."""
        contact = self._store.get(contact_id)
        return (contact, additive_draft(contact, draft)) if contact else None

    def confirm(
        self,
        note_text: str,
        source_type: str,
        draft: ProfileDraft,
        contact_id: str | None = None,
        created_at: datetime | None = None,
    ) -> SaveResult:
        """Save what the user confirmed. Only this method writes contacts for flow A."""
        if not draft.name.strip():
            raise ValueError("A contact needs a name.")
        note = Note(text=note_text, source_type=source_type)
        if created_at:
            note.created_at = created_at

        existing = self._store.get(contact_id) if contact_id else None
        if contact_id and existing is None:
            raise ValueError(f"Contact {contact_id} does not exist.")
        if existing:
            contact, changes = merge_into(existing, draft, note)
        else:
            contact, changes = create_contact(draft, note), []

        self._store.save(contact)
        return SaveResult(contact, changes, self._index_contact(contact))

    def _extract(self, note_text: str) -> ProfileDraft | None:
        user_prompt = extraction_user_prompt(strip_injection(note_text))
        for _ in range(2):  # one retry on invalid JSON
            raw = self._llm.chat_json(EXTRACTION_SYSTEM, user_prompt, PROFILE_SCHEMA, purpose="extract")
            try:
                return clean_profile(parse_profile(raw))
            except InvalidLLMOutput:
                continue
        return None

    def _index_contact(self, contact: Contact) -> str:
        # The JSON is saved at this point. If indexing fails, the status page shows it.
        try:
            self._index.upsert_contact(contact)
        except Exception as exc:
            return str(exc)
        return ""
