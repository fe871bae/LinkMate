"""Data model shared by all layers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field

FactKind = Literal["skill", "interest", "offers_help"]


def new_contact_id() -> str:
    return f"c_{uuid4().hex[:8]}"


def new_note_id() -> str:
    return f"n_{uuid4().hex[:8]}"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Note(BaseModel):
    id: str = Field(default_factory=new_note_id)
    text: str
    source_type: Literal["note", "email"] = "note"
    created_at: datetime = Field(default_factory=utc_now)


class Fact(BaseModel):
    kind: FactKind
    value: str
    source_note_ids: list[str] = Field(default_factory=list)


class Contact(BaseModel):
    id: str = Field(default_factory=new_contact_id)
    name: str
    aliases: list[str] = Field(default_factory=list)
    organization: str = ""
    role: str = ""
    location: str = ""
    met_context: str = ""
    summary: str = ""
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    notes: list[Note] = Field(default_factory=list)
    facts: list[Fact] = Field(default_factory=list)

    def values_of(self, kind: FactKind) -> list[str]:
        return [fact.value for fact in self.facts if fact.kind == kind]

    def label(self) -> str:
        details = ", ".join(part for part in (self.organization, self.role) if part)
        return f"{self.name} ({details})" if details else self.name


class ProfileDraft(BaseModel):
    """A profile proposal: from the LLM, then edited by the user in the review."""

    name: str = ""
    aliases: list[str] = Field(default_factory=list)
    organization: str = ""
    role: str = ""
    location: str = ""
    met_context: str = ""
    summary: str = ""
    skills: list[str] = Field(default_factory=list)
    interests: list[str] = Field(default_factory=list)
    offers_help: list[str] = Field(default_factory=list)


class LLMRecommendation(BaseModel):
    contact: str
    reason: str = ""
    sources: list[str] = Field(default_factory=list)


class LLMAnswer(BaseModel):
    recommendations: list[LLMRecommendation] = Field(default_factory=list)


@dataclass(frozen=True)
class Entry:
    """One searchable document: a contact's profile or one of its notes."""

    id: str
    contact_id: str
    note_id: str  # empty for profile entries
    doc_type: Literal["note", "profile"]
    text: str


@dataclass(frozen=True)
class Hit:
    entry: Entry
    score: float


@dataclass
class Candidate:
    contact_id: str
    score: float
    hits: list[Hit] = field(default_factory=list)


@dataclass(frozen=True)
class SourceNote:
    note_id: str
    text: str
    source_type: str
    created_at: datetime


@dataclass
class Recommendation:
    contact_id: str
    name: str
    organization: str
    role: str
    reason: str
    score: float
    sources: list[SourceNote]
    confidence: str = "weak"  # "strong" or "weak", shown next to the recommendation


@dataclass
class ScoredContact:
    """A search hit shown as-is when the LLM could not explain it."""

    contact_id: str
    name: str
    organization: str
    role: str
    score: float
    sources: list[SourceNote]


AskStatus = Literal["ok", "no_match", "llm_failed"]


@dataclass
class AskResult:
    status: AskStatus
    question: str
    mode: str
    recommendations: list[Recommendation] = field(default_factory=list)
    candidates: list[ScoredContact] = field(default_factory=list)
    dropped: list[str] = field(default_factory=list)
    llm_called: bool = False
    timings: dict[str, float] = field(default_factory=dict)
