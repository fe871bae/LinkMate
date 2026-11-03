"""Match a name against existing contacts and merge a new note deterministically."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher

from linkmate.models import Contact, Fact, FactKind, Note, ProfileDraft, utc_now

TITLES = {"prof", "professor", "dr", "mr", "mrs", "ms"}
MATCH_CUTOFF = 0.8
# Fields that change over time: the newest value wins. Where you met someone does
# not change, so met_context is only filled if it was empty.
SCALAR_FIELDS = ("organization", "role", "location", "summary")
LIST_FIELDS: tuple[tuple[str, FactKind], ...] = (
    ("skills", "skill"),
    ("interests", "interest"),
    ("offers_help", "offers_help"),
)


@dataclass(frozen=True)
class ContactMatch:
    contact_id: str
    name: str
    organization: str
    score: float


@dataclass(frozen=True)
class FieldChange:
    field: str
    old: str
    new: str


def _name_tokens(name: str) -> list[str]:
    decomposed = unicodedata.normalize("NFKD", name)
    plain = "".join(char for char in decomposed if not unicodedata.combining(char))
    return [token for token in re.findall(r"[\w']+", plain.casefold()) if token not in TITLES]


def name_similarity(left: str, right: str) -> float:
    left_tokens, right_tokens = _name_tokens(left), _name_tokens(right)
    if not left_tokens or not right_tokens:
        return 0.0
    if left_tokens == right_tokens:
        return 1.0
    ratio = SequenceMatcher(None, " ".join(sorted(left_tokens)), " ".join(sorted(right_tokens))).ratio()
    # "Daniel" or "Prof. Okafor" against a full name: likely, but the user decides.
    if set(left_tokens) <= set(right_tokens) or set(right_tokens) <= set(left_tokens):
        return max(ratio, 0.9)
    return ratio


def find_matches(name: str, contacts: list[Contact], cutoff: float = MATCH_CUTOFF) -> list[ContactMatch]:
    matches = []
    for contact in contacts:
        score = max(name_similarity(name, known) for known in [contact.name, *contact.aliases])
        if score >= cutoff:
            matches.append(ContactMatch(contact.id, contact.name, contact.organization, score))
    return sorted(matches, key=lambda match: match.score, reverse=True)


def add_fact(contact: Contact, kind: FactKind, value: str, note_id: str) -> None:
    """Add a fact or link the note to the same fact. The code sets the source, never the LLM."""
    for fact in contact.facts:
        if fact.kind == kind and fact.value.lower() == value.lower():
            if note_id not in fact.source_note_ids:
                fact.source_note_ids.append(note_id)
            return
    contact.facts.append(Fact(kind=kind, value=value, source_note_ids=[note_id]))


def preview_changes(contact: Contact, draft: ProfileDraft) -> list[FieldChange]:
    """Which existing values the newest note would replace."""
    changes = []
    for field_name in SCALAR_FIELDS:
        old, new = getattr(contact, field_name), getattr(draft, field_name).strip()
        if old and new and old.lower() != new.lower():
            changes.append(FieldChange(field_name, old, new))
    return changes


def create_contact(draft: ProfileDraft, note: Note) -> Contact:
    contact = Contact(
        name=draft.name.strip(),
        aliases=list(draft.aliases),
        organization=draft.organization.strip(),
        role=draft.role.strip(),
        location=draft.location.strip(),
        met_context=draft.met_context.strip(),
        summary=draft.summary.strip(),
        notes=[note],
    )
    _add_lists(contact, draft, note.id)
    return contact


def merge_into(contact: Contact, draft: ProfileDraft, note: Note) -> tuple[Contact, list[FieldChange]]:
    """Lists are combined without duplicates. For changed fields the newest value wins."""
    merged = contact.model_copy(deep=True)
    changes = preview_changes(merged, draft)
    for field_name in SCALAR_FIELDS:
        new = getattr(draft, field_name).strip()
        if new:
            setattr(merged, field_name, new)

    new_name = draft.name.strip()
    known_names = {merged.name.lower(), *(alias.lower() for alias in merged.aliases)}
    if new_name and new_name.lower() not in known_names:
        merged.aliases.append(new_name)
    for alias in draft.aliases:
        if alias.lower() not in {merged.name.lower(), *(known.lower() for known in merged.aliases)}:
            merged.aliases.append(alias)

    if not merged.met_context:
        merged.met_context = draft.met_context.strip()

    merged.notes.append(note)
    _add_lists(merged, draft, note.id)
    merged.updated_at = utc_now()
    return merged, changes


def draft_from_contact(contact: Contact) -> ProfileDraft:
    return ProfileDraft(
        name=contact.name,
        aliases=list(contact.aliases),
        organization=contact.organization,
        role=contact.role,
        location=contact.location,
        met_context=contact.met_context,
        summary=contact.summary,
        skills=contact.values_of("skill"),
        interests=contact.values_of("interest"),
        offers_help=contact.values_of("offers_help"),
    )


def apply_edit(contact: Contact, draft: ProfileDraft) -> Contact:
    """Apply a user's edit. Kept facts keep their sources, new facts have none, removed facts go."""
    edited = contact.model_copy(deep=True)
    edited.name = draft.name.strip()
    edited.aliases = [alias.strip() for alias in draft.aliases if alias.strip()]
    for field_name in (*SCALAR_FIELDS, "met_context"):
        setattr(edited, field_name, getattr(draft, field_name).strip())

    sources = {(fact.kind, fact.value.lower()): fact.source_note_ids for fact in contact.facts}
    edited.facts = []
    for field_name, kind in LIST_FIELDS:
        for value in getattr(draft, field_name):
            text = value.strip()
            if text and not any(f.kind == kind and f.value.lower() == text.lower() for f in edited.facts):
                edited.facts.append(Fact(kind=kind, value=text, source_note_ids=list(sources.get((kind, text.lower()), []))))
    edited.updated_at = utc_now()
    return edited


def _add_lists(contact: Contact, draft: ProfileDraft, note_id: str) -> None:
    for field_name, kind in LIST_FIELDS:
        for value in getattr(draft, field_name):
            if value.strip():
                add_fact(contact, kind, value.strip(), note_id)
