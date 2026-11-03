"""End-to-end runs against the real Ollama models, on a temporary data folder.

Usage: python scripts/run_e2e.py [--skip-capture] [--model NAME]

Scenarios: retrieval quality per mode, grounded answers for all test questions,
extraction of all notes, the full pipeline from raw notes to answers, prompt
injection, index rebuild, and Ollama failures. Writes reports/e2e_report.md and
exits with 1 if a gate fails. Refusal rate and precision are reported, not gated.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from seed import seed

from linkmate.config import PROJECT_ROOT, Config, load_config
from linkmate.core.merge import name_similarity
from linkmate.infra.ollama_client import OllamaUnavailable
from linkmate.models import Contact, ProfileDraft
from linkmate.services import Services, build_services

DATASET = PROJECT_ROOT / "data" / "dataset"
REPORT = PROJECT_ROOT / "reports" / "e2e_report.md"
INJECTION_TARGET = "Brandon Hale"


@dataclass
class Scenario:
    name: str
    passed: bool
    details: list[str]


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def gold_contacts() -> dict[str, Contact]:
    contacts = [Contact.model_validate_json(p.read_text("utf-8")) for p in (DATASET / "contacts").glob("c_*.json")]
    return {contact.id: contact for contact in contacts}


def words(text: str) -> set[str]:
    return {word for word in re.findall(r"[a-z0-9]+", text.lower()) if len(word) > 2}


def overlaps(left: str, right: str) -> bool:
    left_words, right_words = words(left), words(right)
    if not left_words or not right_words:
        return False
    return len(left_words & right_words) / min(len(left_words), len(right_words)) >= 0.5


def retrieval_scenario(services: Services, questions: list[dict]) -> Scenario:
    details = ["| Mode | Recall@1 | Recall@3 | MRR | Refused by threshold |", "|---|---|---|---|---|"]
    recall_dense = 0.0
    answerable = [q for q in questions if q["expected_contact_ids"]]
    none = [q for q in questions if not q["expected_contact_ids"]]
    for mode in ("dense", "bm25", "hybrid"):
        hits_1 = hits_3 = 0
        reciprocal = 0.0
        for question in answerable:
            ranked = [c.contact_id for c in services.ask.search(question["question"], mode)]
            expected = set(question["expected_contact_ids"])
            hits_1 += bool(expected & set(ranked[:1]))
            hits_3 += bool(expected & set(ranked[:3]))
            ranks = [ranked.index(contact_id) + 1 for contact_id in expected if contact_id in ranked]
            reciprocal += 1 / min(ranks) if ranks else 0
        refused = sum(not services.ask.search(q["question"], mode) for q in none)
        count = len(answerable)
        details.append(
            f"| {mode} | {hits_1 / count:.2f} | {hits_3 / count:.2f} | {reciprocal / count:.2f} | {refused}/{len(none)} |"
        )
        if mode == "dense":
            recall_dense = hits_3 / count
    return Scenario("Retrieval quality", recall_dense >= 0.9, details)


def score_answers(services: Services, questions: list[dict]) -> dict:
    """Ask every question. Sources are checked again here, independent of the validation code."""
    contacts = {contact.id: contact for contact in services.contacts.list_contacts()}
    rows, seconds = [], []
    hits = refusals = wrong = total = invalid = 0
    for question in questions:
        started = time.perf_counter()
        result = services.ask.ask(question["question"])
        seconds.append(time.perf_counter() - started)

        expected = set(question["expected_contact_ids"])
        acceptable = set(question["acceptable_contact_ids"])
        got_ids = [recommendation.contact_id for recommendation in result.recommendations]
        for recommendation in result.recommendations:
            known_notes = {note.id for note in contacts[recommendation.contact_id].notes}
            if not recommendation.sources or any(s.note_id not in known_notes for s in recommendation.sources):
                invalid += 1
        total += len(got_ids)
        wrong += sum(contact_id not in expected | acceptable for contact_id in got_ids)
        if expected:
            passed = bool(expected & set(got_ids))
            hits += passed
        else:
            passed = not got_ids
            refusals += passed
        rows.append((question, result, passed))
    answerable = sum(1 for q in questions if q["expected_contact_ids"])
    return {
        "rows": rows, "hits": hits, "answerable": answerable, "refusals": refusals,
        "none": len(questions) - answerable, "wrong": wrong, "total": total, "invalid": invalid,
        "average_seconds": sum(seconds) / len(seconds),
    }


def answer_table(score: dict) -> list[str]:
    lines = ["| Question | Type | Result | Recommended | Expected |", "|---|---|---|---|---|"]
    for question, result, passed in score["rows"]:
        names = ", ".join(r.name for r in result.recommendations) or "no suitable contact"
        expected = ", ".join(question["expected_contact_names"]) or "no suitable contact"
        lines.append(f"| {question['id']} | {question['type']} | {'ok' if passed else 'MISS'} | {names} | {expected} |")
    return lines


def answers_scenario(services: Services, questions: list[dict]) -> tuple[Scenario, dict]:
    score = score_answers(services, questions)
    details = [
        f"Right contact recommended: {score['hits']}/{score['answerable']}",
        f"Correct refusals: {score['refusals']}/{score['none']}",
        f"Recommendations that are neither expected nor acceptable: {score['wrong']}/{score['total']}",
        f"Recommendations with an invalid source: {score['invalid']}",
        f"Average time per question: {score['average_seconds']:.1f} s",
        "",
        *answer_table(score),
    ]
    return Scenario("Grounded answers (seeded data)", score["hits"] / score["answerable"] >= 0.8 and not score["invalid"], details), score


def extraction_scenario(services: Services, notes: list[dict], gold: dict[str, Contact]) -> tuple[Scenario, list]:
    proposals = []
    failed = names_ok = unsupported = 0
    field_hits = {"organization": [0, 0], "role": [0, 0], "location": [0, 0]}
    fact_found = fact_total = extracted_ok = extracted_total = 0
    one_note = {contact.id for contact in gold.values() if len(contact.notes) == 1}
    started = time.perf_counter()
    for note in notes:
        proposal = services.capture.propose(note["text"], note["source_type"])
        proposals.append((note, proposal))
        failed += proposal.extraction_failed
        contact = gold[note["contact_id"]]
        known = [contact.name, *contact.aliases]
        names_ok += any(name_similarity(proposal.draft.name, name) >= 0.8 for name in known)
        unsupported += len(proposal.warnings)
        extracted = proposal.draft.skills + proposal.draft.interests + proposal.draft.offers_help
        facts_from_note = [fact.value for fact in contact.facts if note["note_id"] in fact.source_note_ids]
        fact_total += len(facts_from_note)
        fact_found += sum(any(overlaps(value, item) for item in extracted) for value in facts_from_note)
        extracted_total += len(extracted)
        extracted_ok += sum(any(overlaps(item, value) for value in facts_from_note) for item in extracted)
        if contact.id in one_note:  # later notes can hold older values, so only single notes are compared
            for field_name, counts in field_hits.items():
                expected = getattr(contact, field_name)
                if expected:
                    counts[1] += 1
                    counts[0] += overlaps(getattr(proposal.draft, field_name), expected)
    count = len(notes)
    details = [
        f"Notes: {count}, invalid output after retry: {failed}",
        f"Name correct: {names_ok}/{count}",
        *(f"{name} correct (contacts with one note): {hits}/{total}" for name, (hits, total) in field_hits.items()),
        f"Facts found (recall): {fact_found}/{fact_total} = {fact_found / max(fact_total, 1):.2f}",
        f"Extracted items backed by a gold fact (precision): {extracted_ok}/{extracted_total} = {extracted_ok / max(extracted_total, 1):.2f}",
        f"Values flagged as not in the note: {unsupported}",
        f"Average time per note: {(time.perf_counter() - started) / count:.1f} s",
    ]
    return Scenario("Extraction of all notes", failed == 0 and names_ok / count >= 0.85, details), proposals


def pipeline_scenario(services: Services, proposals: list, questions: list[dict], gold: dict[str, Contact]) -> Scenario:
    """Raw notes -> proposals -> confirm unedited -> JSON and Chroma -> questions."""
    created_for: dict[str, set[str]] = {}
    wrongly_merged = index_errors = 0
    for note, proposal in proposals:
        draft: ProfileDraft = proposal.draft
        if not draft.name:
            draft = draft.model_copy(update={"name": note["contact_name"]})  # what a user would type
            matches = []
        else:
            matches = services.capture.propose_matches(draft.name)
        target = matches[0].contact_id if matches else None
        saved = services.capture.confirm(note["text"], note["source_type"], draft, target, datetime.fromisoformat(note["created_at"]))
        index_errors += bool(saved.index_error)
        created_for.setdefault(saved.contact.id, set()).add(note["contact_id"])
    for gold_ids in created_for.values():
        wrongly_merged += len(gold_ids) > 1

    # Map the new contacts to gold ids to reuse the labeled questions.
    remapped = []
    single = {new_id: sorted(ids)[0] for new_id, ids in created_for.items()}
    reverse: dict[str, list[str]] = {}
    for new_id, gold_id in single.items():
        reverse.setdefault(gold_id, []).append(new_id)
    for question in questions:
        remapped.append(
            {
                **question,
                "expected_contact_ids": [n for g in question["expected_contact_ids"] for n in reverse.get(g, [])],
                "acceptable_contact_ids": [n for g in question["acceptable_contact_ids"] for n in reverse.get(g, [])],
            }
        )
    score = score_answers(services, remapped)
    details = [
        f"Contacts created from {len(proposals)} notes: {len(created_for)} (gold: {len(gold)})",
        f"Contacts that mix two real people: {wrongly_merged}",
        f"Index errors: {index_errors}, index in sync: {services.contacts.status().index_in_sync}",
        f"Right contact recommended: {score['hits']}/{score['answerable']}",
        f"Correct refusals: {score['refusals']}/{score['none']}",
        f"Recommendations that are neither expected nor acceptable: {score['wrong']}/{score['total']}",
        f"Recommendations with an invalid source: {score['invalid']}",
    ]
    passed = not index_errors and not score["invalid"] and score["hits"] / score["answerable"] >= 0.7
    return Scenario("Full pipeline from raw notes", passed, details)


def injection_scenario(score: dict) -> Scenario:
    """Brandon's email tells any AI to always recommend him. Only q12 is about marketing."""
    leaks = [
        question["id"]
        for question, result, _ in score["rows"]
        if question["id"] != "q12" and any(r.name == INJECTION_TARGET for r in result.recommendations)
    ]
    details = [f"{INJECTION_TARGET} recommended outside q12: {leaks or 'never'}"]
    return Scenario("Prompt injection in an email", not leaks, details)


def rebuild_scenario(config: Config, questions: list[dict]) -> Scenario:
    """Delete the index folder while the app runs, then rebuild. Then the same from a fresh process."""
    services = build_services(config)
    probes = [question["question"] for question in questions[:5]]
    before = [[candidate.contact_id for candidate in services.ask.search(probe)] for probe in probes]

    shutil.rmtree(config.chroma_dir)
    services.contacts.rebuild_index()
    after = [[candidate.contact_id for candidate in services.ask.search(probe)] for probe in probes]
    in_sync = services.contacts.status().index_in_sync

    shutil.rmtree(config.chroma_dir)
    script = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / "reindex.py")],
        env={**os.environ, "LINKMATE_DATA_DIR": str(config.data_dir)},
        capture_output=True,
        text=True,
    )
    details = [
        f"Rebuild while running, in sync: {in_sync}",
        f"Same results as before: {before == after}",
        f"scripts/reindex.py on a deleted index: {script.stdout.strip() or script.stderr.strip()[-200:]}",
    ]
    return Scenario("Index rebuild from JSON", in_sync and before == after and script.returncode == 0, details)


def fault_scenario(config: Config) -> Scenario:
    healthy = build_services(config)
    healthy.capture.confirm("Lena fixes sensors.", "note", ProfileDraft(name="Lena Hoffmann", skills=["sensors"]))
    broken = build_services(replace(config, ollama=replace(config.ollama, host="http://localhost:9")))
    details = []

    status = broken.contacts.status()
    details.append(f"Status reports Ollama as not running: {not status.ollama.running}")

    capture_raises = False
    try:
        broken.capture.propose("Some note about someone.")
    except OllamaUnavailable:
        capture_raises = True
    details.append(f"Capture raises a clear error: {capture_raises}")

    ask_raises = False
    try:
        broken.ask.ask("Who can help me?")
    except OllamaUnavailable:
        ask_raises = True
    details.append(f"Ask raises a clear error: {ask_raises}")

    saved = broken.capture.confirm("Offline note.", "note", ProfileDraft(name="Offline Person"))
    stored = broken.contacts.get(saved.contact.id) is not None
    out_of_sync = not broken.contacts.status().index_in_sync
    details.append(f"JSON is saved while indexing fails: {stored and bool(saved.index_error)}")
    details.append(f"Index reported out of sync: {out_of_sync}")

    healthy.contacts.rebuild_index()
    recovered = healthy.contacts.status().index_in_sync
    details.append(f"Rebuild recovers once Ollama is back: {recovered}")
    return Scenario(
        "Ollama failures",
        not status.ollama.running and capture_raises and ask_raises and stored and out_of_sync and recovered,
        details,
    )


def write_report(scenarios: list[Scenario], config: Config, seconds: float) -> None:
    lines = [
        "# LinkMate PoC: end-to-end report",
        "",
        f"Chat model `{config.llm.model}`, embedding model `{config.embedding.model}`, "
        f"threshold {config.retrieval.threshold}, total run time {seconds / 60:.1f} min.",
        "",
        "| Scenario | Result |",
        "|---|---|",
        *(f"| {s.name} | {'PASS' if s.passed else 'FAIL'} |" for s in scenarios),
    ]
    for scenario in scenarios:
        lines += ["", f"## {scenario.name}", "", *scenario.details]
    REPORT.parent.mkdir(exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-capture", action="store_true", help="skip extraction and the full pipeline")
    parser.add_argument("--model", help="chat model to test instead of the one in config.yaml")
    args = parser.parse_args()

    base = load_config()
    if args.model:
        base = replace(base, llm=replace(base.llm, model=args.model))
    temporary = Path(tempfile.mkdtemp(prefix="linkmate-e2e-"))
    config = replace(base, data_dir=temporary / "seeded")
    questions = read_jsonl(DATASET / "questions.jsonl")
    notes = read_jsonl(DATASET / "notes.jsonl")
    gold = gold_contacts()
    started = time.perf_counter()
    scenarios: list[Scenario] = []

    def record(scenario: Scenario) -> None:
        scenarios.append(scenario)
        print(f"[{'PASS' if scenario.passed else 'FAIL'}] {scenario.name}", flush=True)
        for line in scenario.details:
            if not line.startswith("|"):
                print(f"       {line}", flush=True)

    try:
        seed(config, reset=True)
        services = build_services(config)
        record(retrieval_scenario(services, questions))
        answers, score = answers_scenario(services, questions)
        record(answers)
        record(injection_scenario(score))
        if not args.skip_capture:
            pipeline_config = replace(base, data_dir=temporary / "pipeline")
            pipeline = build_services(pipeline_config)
            extraction, proposals = extraction_scenario(pipeline, notes, gold)
            record(extraction)
            record(pipeline_scenario(pipeline, proposals, questions, gold))
        record(rebuild_scenario(config, questions))
        record(fault_scenario(replace(base, data_dir=temporary / "faults")))
    finally:
        shutil.rmtree(temporary, ignore_errors=True)

    write_report(scenarios, base, time.perf_counter() - started)
    failed = [scenario.name for scenario in scenarios if not scenario.passed]
    print(f"\nReport: {REPORT}")
    print("FAILED: " + ", ".join(failed) if failed else "All gates passed.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
