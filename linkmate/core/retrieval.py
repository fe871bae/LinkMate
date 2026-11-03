"""Entries, keyword search, and ranking of search hits per contact."""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict

from linkmate.core.sanitize import strip_injection
from linkmate.models import Candidate, Contact, Entry, Hit

STOP_WORDS = {
    "a", "about", "an", "and", "any", "are", "at", "be", "can", "could", "do", "does", "for", "from",
    "has", "have", "help", "how", "i", "in", "is", "it", "know", "me", "my", "need", "of", "on", "or",
    "someone", "that", "the", "to", "we", "what", "who", "whom", "with", "would", "you",
}


# nomic-embed-text and the small chat model both work best on short passages.
CHUNK_CHARS = 500


def profile_text(contact: Contact) -> str:
    parts = [contact.name]
    headline = " at ".join(part for part in (contact.role, contact.organization) if part)
    if headline:
        parts.append(headline)
    if contact.location:
        parts.append(f"Based in {contact.location}")
    if contact.met_context:
        parts.append(f"Met at {contact.met_context}")
    if contact.summary:
        parts.append(contact.summary)
    for title, kind in (("Skills", "skill"), ("Interests", "interest"), ("Offers help with", "offers_help")):
        values = contact.values_of(kind)
        if values:
            parts.append(f"{title}: {', '.join(values)}")
    return ". ".join(parts)


def chunk_text(text: str, max_chars: int = CHUNK_CHARS) -> list[str]:
    """Split long text at sentence ends, so that an offer late in an email stays findable."""
    if len(text) <= max_chars:
        return [text]
    chunks, current = [], ""
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        while len(sentence) > max_chars:  # one very long sentence without a full stop
            if current:
                chunks.append(current)
                current = ""
            chunks.append(sentence[:max_chars])
            sentence = sentence[max_chars:]
        if current and len(current) + len(sentence) + 1 > max_chars:
            chunks.append(current)
            current = ""
        current = f"{current} {sentence}".strip()
    if current:
        chunks.append(current)
    return chunks


def entries_for_contact(contact: Contact) -> list[Entry]:
    """One entry for the profile and one for each note chunk. Short notes are one chunk."""
    entries = [Entry(f"{contact.id}:profile", contact.id, "", "profile", profile_text(contact))]
    for note in contact.notes:
        for number, chunk in enumerate(chunk_text(strip_injection(note.text))):
            entries.append(Entry(f"{note.id}:{number}", contact.id, note.id, "note", chunk))
    return entries


def tokenize(text: str) -> list[str]:
    return [token for token in re.findall(r"[a-z0-9]+", text.lower()) if token not in STOP_WORDS]


class BM25:
    """Keyword baseline. Small enough to rebuild from the store on every question."""

    def __init__(self, entries: list[Entry], k1: float = 1.5, b: float = 0.75):
        self.entries = entries
        self.k1 = k1
        self.b = b
        self.frequencies = [Counter(tokenize(entry.text)) for entry in entries]
        self.lengths = [sum(counts.values()) for counts in self.frequencies]
        self.average_length = sum(self.lengths) / len(entries) if entries else 0.0
        self.document_frequency: Counter[str] = Counter()
        for counts in self.frequencies:
            self.document_frequency.update(counts.keys())

    def search(self, query: str, top_k: int) -> list[Hit]:
        hits = []
        terms = tokenize(query)
        for entry, counts, length in zip(self.entries, self.frequencies, self.lengths):
            score = sum(self._term_score(term, counts, length) for term in terms)
            if score > 0:
                hits.append(Hit(entry, score))
        hits.sort(key=lambda hit: hit.score, reverse=True)
        return hits[:top_k]

    def _term_score(self, term: str, counts: Counter, length: int) -> float:
        frequency = counts.get(term, 0)
        if frequency == 0:
            return 0.0
        documents = len(self.entries)
        matching = self.document_frequency[term]
        idf = math.log(1 + (documents - matching + 0.5) / (matching + 0.5))
        denominator = frequency + self.k1 * (1 - self.b + self.b * length / self.average_length)
        return idf * frequency * (self.k1 + 1) / denominator


def rank_contacts(hits: list[Hit], threshold: float, max_candidates: int | None = None) -> list[Candidate]:
    """Group hits per contact. A contact counts with its best hit, not the sum,
    so contacts with many or long notes are not favored."""
    grouped: dict[str, list[Hit]] = defaultdict(list)
    for hit in hits:
        grouped[hit.entry.contact_id].append(hit)

    candidates = []
    for contact_id, contact_hits in grouped.items():
        contact_hits.sort(key=lambda hit: hit.score, reverse=True)
        if contact_hits[0].score >= threshold:
            candidates.append(Candidate(contact_id, contact_hits[0].score, contact_hits))
    candidates.sort(key=lambda candidate: candidate.score, reverse=True)
    return candidates[:max_candidates] if max_candidates else candidates


def fuse_hybrid(
    dense_hits: list[Hit],
    bm25_hits: list[Hit],
    dense_threshold: float,
    bm25_threshold: float,
    max_candidates: int,
    rrf_k: int = 60,
) -> list[Candidate]:
    """Keep contacts that pass either threshold and order them by reciprocal rank fusion."""
    dense = rank_contacts(dense_hits, dense_threshold)
    keyword = rank_contacts(bm25_hits, bm25_threshold)

    scores: dict[str, float] = defaultdict(float)
    merged: dict[str, dict[str, Hit]] = defaultdict(dict)
    for ranking in (dense, keyword):
        for rank, candidate in enumerate(ranking, start=1):
            scores[candidate.contact_id] += 1.0 / (rrf_k + rank)
            for hit in candidate.hits:
                merged[candidate.contact_id].setdefault(hit.entry.id, hit)

    fused = [
        Candidate(contact_id, score, list(merged[contact_id].values()))
        for contact_id, score in scores.items()
    ]
    fused.sort(key=lambda candidate: candidate.score, reverse=True)
    return fused[:max_candidates]
