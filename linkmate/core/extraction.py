"""Clean up an extracted profile and flag what the note does not support."""

from __future__ import annotations

import re

from linkmate.models import ProfileDraft

PLACEHOLDERS = {"", "n/a", "na", "none", "null", "unknown", "not stated", "not mentioned", "not specified"}


def _clean_text(value: str) -> str:
    return "" if value.strip().lower() in PLACEHOLDERS else value.strip()


def _clean_list(values: list[str], taken: set[str]) -> list[str]:
    cleaned = []
    for value in values:
        text = _clean_text(value)
        if text and text.lower() not in taken:
            taken.add(text.lower())
            cleaned.append(text)
    return cleaned


def clean_profile(draft: ProfileDraft) -> ProfileDraft:
    """Drop placeholders and keep each fact in one list only (offers beat skills beat interests)."""
    taken: set[str] = set()
    offers_help = _clean_list(draft.offers_help, taken)
    skills = _clean_list(draft.skills, taken)
    interests = _clean_list(draft.interests, taken)
    return draft.model_copy(
        update={
            "name": _clean_text(draft.name),
            "organization": _clean_text(draft.organization),
            "role": _clean_text(draft.role),
            "location": _clean_text(draft.location),
            "met_context": _clean_text(draft.met_context),
            "summary": _clean_text(draft.summary),
            "skills": skills,
            "interests": interests,
            "offers_help": offers_help,
        }
    )


def _words(text: str) -> set[str]:
    return {word for word in re.findall(r"[a-z0-9]+", text.lower()) if len(word) > 2}


def unsupported_values(draft: ProfileDraft, note_text: str) -> list[str]:
    """Values without a single word in the note. They are shown as a warning in the review."""
    note_words = _words(note_text)

    def is_unsupported(value: str) -> bool:
        words = _words(value)
        return bool(words) and not words & note_words

    warnings = []
    if draft.name and not _words(draft.name) <= note_words:
        warnings.append(f"Name '{draft.name}' does not appear in the note.")
    for field_name in ("organization", "role", "location", "met_context"):
        value = getattr(draft, field_name)
        if is_unsupported(value):
            warnings.append(f"{field_name} '{value}' does not appear in the note.")
    for field_name in ("skills", "interests", "offers_help"):
        for value in getattr(draft, field_name):
            if is_unsupported(value):
                warnings.append(f"{field_name} '{value}' does not appear in the note.")
    return warnings
