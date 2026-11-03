"""Check the LLM's output in code. Without a valid source there is no recommendation."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from pydantic import ValidationError

from linkmate.core.prompts import LabelMap
from linkmate.models import LLMAnswer, ProfileDraft


class InvalidLLMOutput(Exception):
    pass


@dataclass
class VerifiedRecommendation:
    contact_id: str
    reason: str
    note_ids: list[str]


@dataclass
class ValidationResult:
    verified: list[VerifiedRecommendation] = field(default_factory=list)
    dropped: list[str] = field(default_factory=list)


def parse_profile(raw: str) -> ProfileDraft:
    try:
        return ProfileDraft.model_validate_json(raw)
    except ValidationError as exc:
        raise InvalidLLMOutput(str(exc)) from exc


def _normalize_label(raw: str, prefix: str) -> str:
    # Small models write "[S1]" or "C1 Lena Hoffmann". Only the label counts.
    match = re.search(rf"\b{prefix}(\d+)\b", raw)
    return f"{prefix}{match.group(1)}" if match else raw.strip()


def validate_answer(raw: str, labels: LabelMap, max_recommendations: int) -> ValidationResult:
    try:
        answer = LLMAnswer.model_validate_json(raw)
    except ValidationError as exc:
        raise InvalidLLMOutput(str(exc)) from exc

    result = ValidationResult()
    seen: set[str] = set()
    for item in answer.recommendations:
        contact_label = _normalize_label(item.contact, "C")
        contact_id = labels.contacts.get(contact_label)
        if contact_id is None:
            result.dropped.append(f"{item.contact}: not one of the candidates")
            continue
        if contact_id in seen:
            continue
        if not item.reason.strip():
            result.dropped.append(f"{contact_label}: no reason")
            continue
        source_labels = [_normalize_label(source, "S") for source in item.sources]
        if not source_labels:
            result.dropped.append(f"{contact_label}: no source")
            continue
        if any(labels.sources.get(label, ("", ""))[0] != contact_id for label in source_labels):
            result.dropped.append(f"{contact_label}: source does not belong to this contact")
            continue
        note_ids = list(dict.fromkeys(labels.sources[label][1] for label in source_labels))
        result.verified.append(VerifiedRecommendation(contact_id, item.reason.strip(), note_ids))
        seen.add(contact_id)
    result.verified = result.verified[:max_recommendations]
    return result
