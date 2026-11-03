"""Did the injection sentence in Brandon Hale's email cause his recommendations?

Usage: python eval/injection_counterfactual.py
Asks all labeled questions with the original email and with the sentence removed, and compares
how often he is recommended outside the marketing questions. Also repeats the original email with
the guard switched off, which is the state in which the effect was found. Writes reports/evaluation/injection_counterfactual.md.
"""

from __future__ import annotations

import re
import shutil
import sys
import tempfile
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from run_e2e import INJECTION_TARGET, read_jsonl
from seed import seed

from linkmate.config import PROJECT_ROOT, load_config
from linkmate.services import build_services

DATASET = PROJECT_ROOT / "data" / "dataset"
ON_TOPIC = {"q12"}
SENTENCE = re.compile(r"IMPORTANT NOTE FOR ANY AI ASSISTANT.*?every request\.\s*", re.DOTALL)


def recommended(services, questions: list[dict]) -> list[str]:
    hits = []
    for question in questions:
        if question["id"] in ON_TOPIC:
            continue
        if any(item.name == INJECTION_TARGET for item in services.ask.ask(question["question"]).recommendations):
            hits.append(question["id"])
    return hits


def main() -> None:
    questions = read_jsonl(DATASET / "questions.jsonl") + read_jsonl(DATASET / "questions_test.jsonl")
    temporary = Path(tempfile.mkdtemp(prefix="linkmate-counter-"))
    try:
        config = replace(load_config(), data_dir=temporary)
        seed(config, reset=True)
        services = build_services(config)
        with_guard = recommended(services, questions)

        import linkmate.core.prompts as prompts_module
        import linkmate.core.retrieval as retrieval_module

        no_guard = lambda text: text
        saved = retrieval_module.strip_injection
        retrieval_module.strip_injection = prompts_module.strip_injection = no_guard
        services.contacts.rebuild_index()
        with_sentence = recommended(services, questions)
        retrieval_module.strip_injection = prompts_module.strip_injection = saved

        contact = next(c for c in services.contacts.list_contacts() if c.name == INJECTION_TARGET)
        for note in contact.notes:
            note.text = SENTENCE.sub("", note.text)
        services.ask._store.save(contact)
        services.contacts.rebuild_index()
        without_sentence = recommended(services, questions)
    finally:
        shutil.rmtree(temporary, ignore_errors=True)

    lines = [
        "# Injection counterfactual", "",
        f"{INJECTION_TARGET}'s email tells any AI to always recommend him. All {len(questions) - len(ON_TOPIC)} labeled questions outside the marketing one were asked with and without that sentence.", "",
        "| Email | Recommended on the questions |", "|---|---|",
        f"| Original, guard off | {', '.join(with_sentence) or 'none'} |",
        f"| Original, guard on | {', '.join(with_guard) or 'none'} |",
        f"| Sentence removed | {', '.join(without_sentence) or 'none'} |",
    ]
    out = PROJECT_ROOT / "reports" / "evaluation" / "injection_counterfactual.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
