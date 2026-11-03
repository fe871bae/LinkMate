"""Flow B: question -> search -> threshold -> grounded LLM answer -> validation."""

from __future__ import annotations

import time

from linkmate.config import AnswerConfig, RetrievalConfig
from linkmate.core.prompts import ANSWER_SCHEMA, ANSWER_SYSTEM, build_answer_prompt, select_notes
from linkmate.core.retrieval import BM25, entries_for_contact, fuse_hybrid, rank_contacts
from linkmate.core.validation import InvalidLLMOutput, ValidationResult, validate_answer
from linkmate.infra.ollama_client import ModelMissing, OllamaError, OllamaUnavailable
from linkmate.models import AskResult, Candidate, Contact, Recommendation, ScoredContact, SourceNote

MODES = ("dense", "bm25", "hybrid")


def _source(note) -> SourceNote:
    return SourceNote(note.id, note.text, note.source_type, note.created_at)


class AskService:
    def __init__(self, llm, store, index, retrieval: RetrievalConfig, answer: AnswerConfig):
        self._llm = llm
        self._store = store
        self._index = index
        self._retrieval = retrieval
        self._answer = answer

    @property
    def default_mode(self) -> str:
        return self._retrieval.mode

    def search(self, question: str, mode: str | None = None) -> list[Candidate]:
        """Ranked candidates above the threshold. Calls no chat model."""
        mode = mode or self._retrieval.mode
        cfg = self._retrieval
        if mode == "dense":
            return rank_contacts(self._index.query(question, cfg.top_k), cfg.threshold, cfg.max_candidates)
        if mode == "bm25":
            return rank_contacts(self._bm25_hits(question), cfg.bm25_threshold, cfg.max_candidates)
        if mode == "hybrid":
            return fuse_hybrid(
                self._index.query(question, cfg.top_k),
                self._bm25_hits(question),
                cfg.threshold,
                cfg.bm25_threshold,
                cfg.max_candidates,
            )
        raise ValueError(f"Unknown retrieval mode: {mode}")

    def ask(self, question: str, mode: str | None = None) -> AskResult:
        if not question.strip():
            raise ValueError("The question is empty.")
        mode = mode or self._retrieval.mode
        result = AskResult(status="no_match", question=question, mode=mode)

        started = time.perf_counter()
        candidates = self.search(question, mode)
        result.timings["search"] = time.perf_counter() - started

        contacts = {contact.id: contact for contact in self._store.all()}
        candidates = [c for c in candidates if c.contact_id in contacts and contacts[c.contact_id].notes]
        if not candidates:
            return result  # no good hits: no LLM call, no invented matches

        result.candidates = [self._scored(candidate, contacts) for candidate in candidates]
        prompt, labels = build_answer_prompt(
            question, candidates, contacts, self._answer.notes_per_contact, self._answer.max_note_chars
        )

        started = time.perf_counter()
        result.llm_called = True
        validated = self._call_llm(prompt, labels)
        result.timings["llm"] = time.perf_counter() - started

        if validated is None:
            result.status = "llm_failed"
            return result

        scores = {candidate.contact_id: candidate.score for candidate in candidates}
        recommendations = [self._recommendation(item, contacts, scores, mode) for item in validated.verified]
        recommendations.sort(key=lambda item: item.score, reverse=True)
        result.recommendations = recommendations
        result.dropped = validated.dropped
        result.status = "ok" if recommendations else "no_match"
        return result

    def _call_llm(self, prompt, labels) -> ValidationResult | None:
        for _ in range(2):  # one retry on invalid JSON
            try:
                raw = self._llm.chat_json(ANSWER_SYSTEM, prompt, ANSWER_SCHEMA, purpose="answer")
                return validate_answer(raw, labels, self._answer.max_recommendations)
            except (OllamaUnavailable, ModelMissing):
                raise
            except (InvalidLLMOutput, OllamaError):
                continue
        return None

    def _bm25_hits(self, question: str):
        entries = [entry for contact in self._store.all() for entry in entries_for_contact(contact)]
        return BM25(entries).search(question, self._retrieval.top_k)

    def _scored(self, candidate: Candidate, contacts: dict[str, Contact]) -> ScoredContact:
        contact = contacts[candidate.contact_id]
        notes = select_notes(candidate, contact, self._answer.notes_per_contact)
        return ScoredContact(
            contact.id, contact.name, contact.organization, contact.role, candidate.score,
            [_source(note) for note in notes],
        )

    def _confidence(self, score: float, mode: str) -> str:
        # Only cosine scores can be compared with this limit.
        return "strong" if mode == "dense" and score >= self._answer.strong_from else "weak"

    def _recommendation(self, item, contacts: dict[str, Contact], scores: dict[str, float], mode: str) -> Recommendation:
        contact = contacts[item.contact_id]
        notes = {note.id: note for note in contact.notes}
        return Recommendation(
            contact.id, contact.name, contact.organization, contact.role, item.reason,
            scores[item.contact_id], [_source(notes[note_id]) for note_id in item.note_ids],
            self._confidence(scores[item.contact_id], mode),
        )
