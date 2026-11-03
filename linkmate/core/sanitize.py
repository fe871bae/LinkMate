"""Find instruction-like text in notes and keep it away from the models.

A keyword rule, so new wording can get through. The stored note is never changed. Only the
copies that are embedded or sent to the LLM lose the sentence, and the review shows a warning.
"""

from __future__ import annotations

import re

SUSPICIOUS = re.compile(
    r"ignore (all |any )?(the )?(previous|prior|above)|ignoriere|system\s*:|new instructions|you are now"
    r"|always recommend|recommend .{0,30}(always|every|first|all)|empfiehl|any ai|to any model|<\s*/?\s*note\s*>"
    r"|\"recommendations\"|\[S\d+\]|!\[",
    re.IGNORECASE,
)


def looks_like_injection(text: str) -> bool:
    return bool(SUSPICIOUS.search(text))


def strip_injection(text: str) -> str:
    """Drop the sentences or lines that hold instruction-like text."""
    if not looks_like_injection(text):
        return text
    parts = re.split(r"(?<=[.!?])\s+|\n+", text)
    return " ".join(part for part in parts if part.strip() and not looks_like_injection(part))
