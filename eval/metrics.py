"""Metrics for retrieval and answers. Pure functions, unit tested without any model."""

from __future__ import annotations

import math
from dataclasses import dataclass


def wilson_interval(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    """95% confidence interval of a proportion. Honest for small samples, unlike +-1.96 sigma."""
    if total == 0:
        return (0.0, 0.0)
    rate = successes / total
    denominator = 1 + z * z / total
    center = (rate + z * z / (2 * total)) / denominator
    margin = z * math.sqrt(rate * (1 - rate) / total + z * z / (4 * total * total)) / denominator
    return (max(0.0, center - margin), min(1.0, center + margin))


def percentile(values: list[float], share: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = share * (len(ordered) - 1)
    low, high = math.floor(position), math.ceil(position)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def reciprocal_rank(ranked: list[str], expected: set[str]) -> float:
    for rank, contact_id in enumerate(ranked, start=1):
        if contact_id in expected:
            return 1.0 / rank
    return 0.0


def recall_at(ranked: list[str], expected: set[str], k: int) -> bool:
    """True if at least one expected contact is among the first k."""
    return bool(expected & set(ranked[:k]))


@dataclass
class AnswerScore:
    """Counts over labeled questions. `acceptable` contacts are not wrong, and do not count as hits."""

    answerable: int = 0
    hits: int = 0  # answerable questions with at least one expected contact recommended
    none: int = 0
    refusals: int = 0  # unanswerable questions answered with "no suitable contact"
    total_recommended: int = 0
    wrong_recommended: int = 0
    invalid_sources: int = 0

    def add(self, recommended: list[str], expected: set[str], acceptable: set[str]) -> bool:
        self.total_recommended += len(recommended)
        self.wrong_recommended += sum(contact_id not in expected | acceptable for contact_id in recommended)
        if expected:
            self.answerable += 1
            passed = bool(expected & set(recommended))
            self.hits += passed
        else:
            self.none += 1
            passed = not recommended
            self.refusals += passed
        return passed

    @property
    def hit_rate(self) -> float:
        return self.hits / self.answerable if self.answerable else 0.0

    @property
    def refusal_rate(self) -> float:
        return self.refusals / self.none if self.none else 0.0

    @property
    def precision(self) -> float:
        """Share of recommendations that are expected or acceptable."""
        if not self.total_recommended:
            return 0.0
        return 1 - self.wrong_recommended / self.total_recommended

    @property
    def balanced(self) -> float:
        """Mean of hit rate and refusal rate, so both error types count the same."""
        return (self.hit_rate + self.refusal_rate) / 2
