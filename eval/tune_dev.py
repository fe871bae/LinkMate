"""Sweep the search threshold on the development questions only.

Usage: python eval/tune_dev.py
Writes reports/tuning_dev.md. The held-out questions are never read here.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from seed import seed

from eval.metrics import AnswerScore
from linkmate.config import PROJECT_ROOT, load_config
from linkmate.services import build_services

QUESTIONS = PROJECT_ROOT / "data" / "dataset" / "questions.jsonl"
THRESHOLDS = (0.50, 0.55, 0.57, 0.59, 0.61, 0.63, 0.65, 0.67, 0.70)


def main() -> None:
    temporary = Path(tempfile.mkdtemp(prefix="linkmate-tune-"))
    base = replace(load_config(), data_dir=temporary)
    questions = [json.loads(line) for line in QUESTIONS.read_text("utf-8").splitlines()]
    rows = []
    try:
        seed(base, reset=True)
        for threshold in THRESHOLDS:
            services = build_services(replace(base, retrieval=replace(base.retrieval, threshold=threshold)))
            score = AnswerScore()
            for question in questions:
                result = services.ask.ask(question["question"], "dense")
                score.add(
                    [r.contact_id for r in result.recommendations],
                    set(question["expected_contact_ids"]),
                    set(question["acceptable_contact_ids"]),
                )
            rows.append((threshold, score))
            print(threshold, score.hits, score.refusals, score.wrong_recommended, score.total_recommended, flush=True)
    finally:
        shutil.rmtree(temporary, ignore_errors=True)

    lines = [
        "# Threshold sweep on the development questions",
        "",
        "`threshold` is the minimum cosine score of a candidate.",
        "",
        "| threshold | right contact | correct refusals | wrong / recommended | balanced |",
        "|---|---|---|---|---|",
    ]
    for threshold, s in rows:
        lines.append(
            f"| {threshold} | {s.hits}/{s.answerable} | {s.refusals}/{s.none} "
            f"| {s.wrong_recommended}/{s.total_recommended} | {s.balanced:.3f} |"
        )
    lines += [
        "",
        "Chosen setting: threshold 0.59 and `strong_from` 0.67. A threshold of 0.67 alone would give 6/6 correct",
        "refusals and no wrong recommendation, but would hide 6 more right contacts. Showing contacts from 0.59",
        "with a weak label keeps them findable, and the user can see which matches to check.",
        "",
        "## Rejected experiments",
        "",
        "Strict prompt in the zone below a score limit (threshold 0.55, limit 0.0 means no strict prompt).",
        "Its examples made the small model recommend more people, not fewer, so it was removed.",
        "",
        "| limit | right contact | correct refusals | wrong / recommended |",
        "|---|---|---|---|",
        "| 0.0 | 23/24 | 1/6 | 6/29 |",
        "| 0.62 | 23/24 | 1/6 | 8/31 |",
        "| 0.65 | 21/24 | 1/6 | 14/36 |",
        "| 0.68 | 21/24 | 1/6 | 20/42 |",
        "",
        "A second LLM pass that fills in need, offer and a same-thing flag per recommendation answered",
        "`same: false` for 20 of 22 right contacts and `same: true` for one wrong one (Tom Weber, airplane),",
        "so it was rejected too. Score alone cannot separate near misses either: fitting contacts score",
        "0.59 to 0.80, unfitting ones 0.59 to 0.67.",
    ]
    (PROJECT_ROOT / "reports" / "tuning_dev.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
