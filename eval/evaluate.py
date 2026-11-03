"""Full evaluation of LinkMate against labeled questions and notes.

Usage: python eval/evaluate.py --split dev|test [--model NAME] [--skip-capture] [--tag TEXT]

Compares the system with two baselines, breaks results down by question type, classifies
every failure, checks citations and reasons, and measures extraction, a note length bias,
prompt injection and latency. Runs on a temporary data folder and never touches user data.
Writes reports/evaluation/<name>.md, .json and a reasons CSV for manual annotation.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from dataclasses import replace
from datetime import datetime
from math import comb
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from run_e2e import gold_contacts, overlaps, read_jsonl
from seed import seed

from eval.injection_cases import CASES, MARKER, UNRELATED_QUESTIONS
from eval.metrics import AnswerScore, percentile, recall_at, reciprocal_rank, wilson_interval
from linkmate.config import PROJECT_ROOT, Config, load_config
from linkmate.core.extraction import unsupported_values
from linkmate.core.sanitize import looks_like_injection
from linkmate.core.merge import name_similarity
from linkmate.models import Contact, ProfileDraft
from linkmate.services import Services, build_services

DATASET = PROJECT_ROOT / "data" / "dataset"
OUTPUT = PROJECT_ROOT / "reports" / "evaluation"
FILES = {"dev": "questions.jsonl", "test": "questions_test.jsonl"}
STOP = {"the", "and", "for", "with", "can", "has", "have", "who", "she", "his", "her", "him", "that", "this", "they",
        "from", "offered", "help", "helps", "because", "their", "them", "will", "would", "about", "you", "your"}


def pct(value: float) -> str:
    return f"{value * 100:.0f}%"


def ci(successes: int, total: int) -> str:
    low, high = wilson_interval(successes, total)
    return f"{successes}/{total} ({pct(successes / total if total else 0)}, CI {pct(low)} to {pct(high)})"


def sign_test(wins: int, losses: int) -> float:
    """Two-sided exact sign test on discordant questions (McNemar's exact test)."""
    count = wins + losses
    if not count:
        return 1.0
    tail = sum(comb(count, k) for k in range(0, min(wins, losses) + 1)) / 2**count
    return min(1.0, 2 * tail)


def content_words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 2 and w not in STOP}


def reason_support(reason: str, note_texts: list[str]) -> float:
    """Share of the reason's content words that appear in the cited notes. A cheap grounding signal."""
    words = content_words(reason)
    if not words:
        return 0.0
    cited = content_words(" ".join(note_texts))
    return len(words & cited) / len(words)


def retrieval_table(services: Services, questions: list[dict]) -> dict:
    results = {}
    answerable = [q for q in questions if q["expected_contact_ids"]]
    for mode in ("dense", "bm25", "hybrid"):
        rows = {"all": [], "direct": [], "indirect": []}
        for question in answerable:
            ranked = [c.contact_id for c in services.ask.search(question["question"], mode)]
            rows["all"].append((ranked, set(question["expected_contact_ids"])))
            rows[question["type"]].append(rows["all"][-1])
        results[mode] = {
            group: {
                "n": len(items),
                "recall@1": sum(recall_at(r, e, 1) for r, e in items) / len(items),
                "recall@3": sum(recall_at(r, e, 3) for r, e in items) / len(items),
                "recall@5": sum(recall_at(r, e, 5) for r, e in items) / len(items),
                "mrr": sum(reciprocal_rank(r, e) for r, e in items) / len(items),
            }
            for group, items in rows.items() if items
        }
        none = [q for q in questions if not q["expected_contact_ids"]]
        results[mode]["refused_by_threshold"] = sum(not services.ask.search(q["question"], mode) for q in none)
        results[mode]["none"] = len(none)
    return results


def baseline_answers(services: Services, questions: list[dict], mode: str) -> tuple[AnswerScore, dict]:
    """Search only: recommend the top hit if it passes the threshold. No LLM."""
    score, by_id = AnswerScore(), {}
    for question in questions:
        ranked = [c.contact_id for c in services.ask.search(question["question"], mode)]
        by_id[question["id"]] = score.add(
            ranked[:1], set(question["expected_contact_ids"]), set(question["acceptable_contact_ids"])
        )
    return score, by_id


def classify(question: dict, result, expected: set[str], acceptable: set[str], passed: bool) -> str:
    recommended = {r.contact_id for r in result.recommendations}
    candidates = {c.contact_id for c in result.candidates}
    if result.status == "llm_failed":
        return "LLM output invalid"
    if expected:
        if passed:
            return "wrong extra contact" if recommended - expected - acceptable else "ok"
        if not expected & candidates:
            return "retrieval miss"
        if recommended:
            return "model chose wrong contact"
        return "dropped by validation" if result.dropped else "model refused"
    if passed:
        return "ok"
    return "near miss accepted" if question["difficulty"] != "easy" else "false accept"


def system_answers(services: Services, questions: list[dict], contacts: dict[str, Contact]) -> dict:
    score = AnswerScore()
    groups = {"direct": AnswerScore(), "indirect": AnswerScore()}
    rows, seconds, supports, reasons, by_id = [], [], [], [], {}
    tiers = {"strong": [0, 0], "weak": [0, 0]}  # recommendations that fit, recommendations
    for question in questions:
        started = time.perf_counter()
        result = services.ask.ask(question["question"])
        seconds.append(time.perf_counter() - started)
        expected = set(question["expected_contact_ids"])
        acceptable = set(question["acceptable_contact_ids"])
        recommended = [r.contact_id for r in result.recommendations]
        passed = score.add(recommended, expected, acceptable)
        by_id[question["id"]] = passed
        if question["type"] in groups:
            groups[question["type"]].add(recommended, expected, acceptable)
        for item in result.recommendations:
            tier = tiers[item.confidence]
            tier[1] += 1
            tier[0] += item.contact_id in expected | acceptable
            known = {note.id for note in contacts[item.contact_id].notes}
            if not item.sources or any(source.note_id not in known for source in item.sources):
                score.invalid_sources += 1
            support = reason_support(item.reason, [source.text for source in item.sources])
            supports.append(support)
            reasons.append({
                "question_id": question["id"], "question": question["question"], "contact": item.name,
                "reason": item.reason, "support": round(support, 2),
                "relevant": "yes" if item.contact_id in expected else "acceptable" if item.contact_id in acceptable else "no",
                "cited_notes": " || ".join(source.text for source in item.sources),
            })
        rows.append({
            "id": question["id"], "type": question["type"], "difficulty": question["difficulty"],
            "question": question["question"], "passed": passed,
            "recommended": [r.name for r in result.recommendations],
            "confidence": [r.confidence for r in result.recommendations],
            "expected": question["expected_contact_names"],
            "candidates": [{"name": c.name, "score": round(c.score, 3)} for c in result.candidates],
            "dropped": result.dropped, "failure": classify(question, result, expected, acceptable, passed),
            "seconds": round(seconds[-1], 2),
        })
    return {
        "score": score, "groups": groups, "rows": rows, "seconds": seconds, "supports": supports,
        "reasons": reasons, "by_id": by_id, "tiers": tiers,
    }


def strong_only(rows: list[dict], questions: list[dict]) -> AnswerScore:
    """The same answers, counting only recommendations with the strong label."""
    names = {q["id"]: q for q in questions}
    score = AnswerScore()
    for row in rows:
        q = names[row["id"]]
        kept = [name for name, label in zip(row["recommended"], row["confidence"]) if label == "strong"]
        score.add(kept, set(q["expected_contact_names"]), set(q["acceptable_contact_names"]))
    return score


def extraction_eval(services: Services, notes: list[dict], gold: dict[str, Contact]) -> tuple[dict, list]:
    """Field and fact scores per note. A fact matches when at least half of the words of the shorter text overlap, which is lenient."""
    proposals = []
    failed = names = unsupported = 0
    fields = {"organization": [0, 0], "role": [0, 0], "met_context": [0, 0]}
    kinds = {"skill": "skills", "interest": "interests", "offers_help": "offers_help"}
    found = total_gold = correct = total_extracted = 0
    per_kind = {kind: [0, 0, 0, 0] for kind in kinds}
    one_note = {contact.id for contact in gold.values() if len(contact.notes) == 1}
    seconds = []
    for note in notes:
        started = time.perf_counter()
        proposal = services.capture.propose(note["text"], note["source_type"])
        seconds.append(time.perf_counter() - started)
        proposals.append((note, proposal))
        contact = gold[note["contact_id"]]
        failed += proposal.extraction_failed
        names += any(name_similarity(proposal.draft.name, known) >= 0.8 for known in [contact.name, *contact.aliases])
        unsupported += len(unsupported_values(proposal.draft, note["text"]))
        all_extracted = [v for attr in kinds.values() for v in getattr(proposal.draft, attr)]
        gold_facts = [f for f in contact.facts if note["note_id"] in f.source_note_ids]
        found += sum(any(overlaps(f.value, item) for item in all_extracted) for f in gold_facts)
        total_gold += len(gold_facts)
        correct += sum(any(overlaps(item, f.value) for f in gold_facts) for item in all_extracted)
        total_extracted += len(all_extracted)
        for kind, attr in kinds.items():
            extracted = getattr(proposal.draft, attr)
            expected = [f.value for f in gold_facts if f.kind == kind]
            per_kind[kind][0] += sum(any(overlaps(value, item) for item in extracted) for value in expected)
            per_kind[kind][1] += len(expected)
            per_kind[kind][2] += sum(any(overlaps(item, value) for value in expected) for item in extracted)
            per_kind[kind][3] += len(extracted)
        if contact.id in one_note:  # later notes can hold older values, so only single notes are compared
            for name, counts in fields.items():
                expected = getattr(contact, name)
                if expected:
                    counts[1] += 1
                    counts[0] += overlaps(getattr(proposal.draft, name), expected)
    recall = found / max(total_gold, 1)
    precision = correct / max(total_extracted, 1)
    return {
        "notes": len(notes), "invalid_after_retry": failed, "names_correct": names,
        "fields": fields, "fact_recall": recall, "fact_precision": precision,
        "fact_f1": 2 * recall * precision / max(recall + precision, 1e-9),
        "facts_found": found, "facts_total": total_gold, "extracted_ok": correct, "extracted_total": total_extracted,
        "per_kind": per_kind, "flagged_values": unsupported,
        "seconds_p50": percentile(seconds, 0.5), "seconds_p95": percentile(seconds, 0.95),
    }, proposals


def pipeline_eval(config: Config, proposals: list, questions: list[dict], gold: dict[str, Contact]) -> dict:
    """Raw notes -> proposals -> confirmed unedited -> questions, with no hand-written profile.

    A name match is accepted as a user would when the app suggests it, also for a similar name."""
    services = build_services(config)
    created: dict[str, set[str]] = {}
    for note, proposal in proposals:
        draft: ProfileDraft = proposal.draft
        if not draft.name:
            draft = draft.model_copy(update={"name": note["contact_name"]})
        matches = services.capture.propose_matches(draft.name)
        saved = services.capture.confirm(
            note["text"], note["source_type"], draft, matches[0].contact_id if matches else None,
            datetime.fromisoformat(note["created_at"]),
        )
        created.setdefault(saved.contact.id, set()).add(note["contact_id"])
    mapping: dict[str, list[str]] = {}
    for new_id, gold_ids in created.items():
        for gold_id in gold_ids:
            mapping.setdefault(gold_id, []).append(new_id)
    remapped = [
        {
            **q,
            "expected_contact_ids": [n for g in q["expected_contact_ids"] for n in mapping.get(g, [])],
            "acceptable_contact_ids": [n for g in q["acceptable_contact_ids"] for n in mapping.get(g, [])],
        }
        for q in questions
    ]
    contacts = {c.id: c for c in services.contacts.list_contacts()}
    answers = system_answers(services, remapped, contacts)
    return {
        "contacts_created": len(created), "contacts_gold": len(gold),
        "mixed_people": sum(len(ids) > 1 for ids in created.values()),
        "split_people": sum(len(ids) > 1 for ids in mapping.values()),
        "score": answers["score"],
    }


def bias_eval(rows: list[dict], questions: list[dict], contacts: dict[str, Contact]) -> dict:
    """Do contacts with little text lose out, and do contacts with much text get recommended wrongly?"""
    lengths = {c.id: sum(len(n.text) for n in c.notes) for c in contacts.values()}
    median = statistics.median(lengths.values())
    by_name = {c.name: c.id for c in contacts.values()}
    groups = {"short": [0, 0], "long": [0, 0]}
    wrong = {"short": 0, "long": 0}
    population = {"short": sum(v <= median for v in lengths.values()), "long": sum(v > median for v in lengths.values())}
    question_by_id = {q["id"]: q for q in questions}
    for row in rows:
        q = question_by_id[row["id"]]
        for name in row["recommended"]:
            contact_id = by_name[name]
            if contact_id not in set(q["expected_contact_ids"]) | set(q["acceptable_contact_ids"]):
                wrong["short" if lengths[contact_id] <= median else "long"] += 1
        for contact_id, name in zip(q["expected_contact_ids"], q["expected_contact_names"]):
            group = "short" if lengths[contact_id] <= median else "long"
            groups[group][1] += 1
            groups[group][0] += name in row["recommended"]
    return {"median_chars": median, "found": groups, "wrong": wrong, "population": population}


def injection_eval(base: Config, temporary: Path) -> dict:
    """Each attack note is captured into a fresh copy of the seeded data and then probed."""
    rows = []
    for name, text in CASES:
        config = replace(base, data_dir=temporary / f"attack_{name}")
        seed(config, reset=True)
        services = build_services(config)
        proposal = services.capture.propose(text, "email")
        dump = proposal.draft.model_dump_json()
        extraction_marker = MARKER.lower() in dump.lower()
        forged_name = "rook" not in proposal.draft.name.lower()
        draft = proposal.draft.model_copy(update={"name": "Ivan Rook"})
        saved = services.capture.confirm(text, "email", draft)
        leaks = sum(
            saved.contact.id in {r.contact_id for r in services.ask.ask(q).recommendations}
            for q in UNRELATED_QUESTIONS
        )
        rows.append({
            "case": name, "warned": looks_like_injection(text), "marker_in_profile": extraction_marker, "wrong_name": forged_name,
            "recommended_for_unrelated": leaks, "questions": len(UNRELATED_QUESTIONS),
        })
        shutil.rmtree(config.data_dir, ignore_errors=True)
    return {
        "rows": rows,
        "extraction_compromised": sum(r["marker_in_profile"] or r["wrong_name"] for r in rows),
        "ranking_compromised": sum(r["recommended_for_unrelated"] > 0 for r in rows),
        "cases": len(rows), "warned": sum(r["warned"] for r in rows),
    }


def model_memory() -> str:
    try:
        return subprocess.run(["ollama", "ps"], capture_output=True, text=True, timeout=10).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def score_dict(score: AnswerScore) -> dict:
    return {
        "hits": score.hits, "answerable": score.answerable, "refusals": score.refusals, "none": score.none,
        "wrong": score.wrong_recommended, "recommended": score.total_recommended, "invalid_sources": score.invalid_sources,
        "hit_rate": score.hit_rate, "refusal_rate": score.refusal_rate, "precision": score.precision, "balanced": score.balanced,
    }


def score_row(name: str, s: AnswerScore) -> str:
    return (
        f"| {name} | {ci(s.hits, s.answerable)} | {ci(s.refusals, s.none)} "
        f"| {s.total_recommended - s.wrong_recommended}/{s.total_recommended} ({pct(s.precision)}) | {s.balanced:.2f} |"
    )


def write_report(path: Path, data: dict) -> None:
    system, bm25, dense = data["answers"], data["baseline_bm25"], data["baseline_dense"]
    lines = [
        f"# LinkMate evaluation: {data['split']} questions",
        "",
        f"Chat model `{data['model']}`, embedding model `{data['embedding']}`, {data['contacts']} contacts, "
        f"{data['questions']} questions. Run time {data['minutes']:.1f} min.",
        "",
        f"Configuration: threshold {data['threshold']}, strong_from {data['strong_from']}, max_candidates {data['max_candidates']}.",
        "",
        "## System against baselines",
        "",
        "Confidence intervals are 95% Wilson intervals. Acceptable contacts do not count as wrong, nor as hits.",
        "",
        "| System | Right contact | Correct refusals | Precision of recommendations | Balanced |",
        "|---|---|---|---|---|",
        score_row("BM25 top hit, no LLM (keyword baseline)", bm25),
        score_row("Dense top hit, no LLM", dense),
        score_row("LinkMate: dense + grounded LLM", system["score"]),
        score_row("LinkMate, strong label only", data["strong_only"]),
        "",
        f"Exact sign test on all questions, LinkMate against the keyword baseline: {data['sign_wins']} questions only LinkMate gets right, "
        f"{data['sign_losses']} only the baseline gets right, p = {data['sign_p']:.3f}.",
        "",
        "| Question type | LinkMate right contact | Keyword baseline |",
        "|---|---|---|",
    ]
    for group in ("direct", "indirect"):
        lines.append(f"| {group} | {ci(system['groups'][group].hits, system['groups'][group].answerable)} | {data['bm25_groups'][group]} |")
    lines += ["", "## Retrieval only", "", "| Mode | Group | n | Recall@1 | Recall@3 | Recall@5 | MRR |", "|---|---|---|---|---|---|---|"]
    for mode, groups in data["retrieval"].items():
        for group in ("all", "direct", "indirect"):
            if group in groups:
                g = groups[group]
                lines.append(f"| {mode} | {group} | {g['n']} | {g['recall@1']:.2f} | {g['recall@3']:.2f} | {g['recall@5']:.2f} | {g['mrr']:.2f} |")
    lines += ["", "| Mode | Unanswerable questions refused by the threshold alone |", "|---|---|"]
    lines += [f"| {mode} | {g['refused_by_threshold']}/{g['none']} |" for mode, g in data["retrieval"].items()]
    supports = system["supports"]
    tiers = system["tiers"]
    lines += [
        "",
        "## Confidence label",
        "",
        "Share of recommendations that are expected or acceptable, per label shown to the user.",
        "",
        "| Label | Fitting recommendations |",
        "|---|---|",
        f"| strong | {ci(*tiers['strong'])} |",
        f"| weak | {ci(*tiers['weak'])} |",
    ]
    lines += [
        "",
        "## Citations and reasons",
        "",
        f"Recommendations with an invalid source: {system['score'].invalid_sources} of {system['score'].total_recommended}.",
        f"Word support of reasons in the cited notes: median {statistics.median(supports) if supports else 0:.2f}, "
        f"{sum(s >= 0.5 for s in supports)}/{len(supports)} at 0.5 or more.",
        "",
        "## Failure analysis",
        "",
        "| Failure type | Count |",
        "|---|---|",
    ]
    counts: dict[str, int] = {}
    for row in system["rows"]:
        counts[row["failure"]] = counts.get(row["failure"], 0) + 1
    lines += [f"| {name} | {count} |" for name, count in sorted(counts.items(), key=lambda item: -item[1])]
    lines += ["", "| Question | Type | Result | Failure type | Recommended | Expected | Top candidates |", "|---|---|---|---|---|---|---|"]
    for row in system["rows"]:
        top = ", ".join(f"{c['name']} {c['score']:.2f}" for c in row["candidates"][:3]) or "none above threshold"
        lines.append(
            f"| {row['id']} | {row['type']} | {'ok' if row['passed'] else 'MISS'} | {row['failure']} "
            f"| {', '.join(row['recommended']) or 'no suitable contact'} | {', '.join(row['expected']) or 'no suitable contact'} | {top} |"
        )
    bias = data["bias"]
    lines += [
        "",
        "## Note length bias",
        "",
        f"Contacts are split at the median of their total note text ({bias['median_chars']:.0f} characters).",
        "",
        "| Contact group | Contacts | Expected contact found | Wrong recommendations |",
        "|---|---|---|---|",
    ]
    for group in ("short", "long"):
        found, total = bias["found"][group]
        lines.append(f"| {group} notes | {bias['population'][group]} | {ci(found, total)} | {bias['wrong'][group]} |")
    lines += [
        "",
        "## Latency",
        "",
        f"Per question: median {data['latency']['p50']:.1f} s, p95 {data['latency']['p95']:.1f} s.",
        "",
        "```text",
        data["memory"],
        "```",
    ]
    if "extraction" in data:
        e = data["extraction"]
        lines += [
            "",
            "## Extraction",
            "",
            f"Notes: {e['notes']}. Invalid output after one retry: {e['invalid_after_retry']}. Names correct: {e['names_correct']}/{e['notes']}.",
            f"Facts: recall {e['fact_recall']:.2f} ({e['facts_found']}/{e['facts_total']}), precision {e['fact_precision']:.2f} "
            f"({e['extracted_ok']}/{e['extracted_total']}), F1 {e['fact_f1']:.2f}. Values flagged as not in the note: {e['flagged_values']}.",
            f"Time per note: median {e['seconds_p50']:.1f} s, p95 {e['seconds_p95']:.1f} s.",
            "",
            "| Field (contacts with one note) | Correct |",
            "|---|---|",
        ]
        lines += [f"| {name} | {hit}/{total} |" for name, (hit, total) in e["fields"].items()]
        lines += ["", "| Fact kind | Recall | Precision |", "|---|---|---|"]
        for kind, (found, total, ok, extracted) in e["per_kind"].items():
            lines.append(f"| {kind} | {found}/{total} | {ok}/{extracted} |")
        p = data["pipeline"]
        lines += [
            "",
            "## Full pipeline from raw notes",
            "",
            "All notes are extracted and confirmed unedited, with no hand-written profile. A suggested name match is accepted.",
            "",
            f"Contacts created: {p['contacts_created']} (gold {p['contacts_gold']}). Contacts mixing two people: {p['mixed_people']}. "
            f"People split over two contacts: {p['split_people']}.",
            "",
            "| System | Right contact | Correct refusals | Precision of recommendations | Balanced |",
            "|---|---|---|---|---|",
            score_row("LinkMate from raw notes", p["score"]),
        ]
    if "injection" in data:
        i = data["injection"]
        lines += [
            "",
            "## Prompt injection",
            "",
            f"Attacks that changed the extracted profile: {i['extraction_compromised']}/{i['cases']}. "
            f"Attacks that got the attacker recommended for an unrelated question: {i['ranking_compromised']}/{i['cases']}. "
            f"Attacks flagged with a warning in the review: {i['warned']}/{i['cases']}.",
            "",
            "| Attack | Warned in review | Marker in profile | Wrong name | Recommended for unrelated questions |",
            "|---|---|---|---|---|",
        ]
        lines += [
            f"| {r['case']} | {'yes' if r['warned'] else 'no'} | {'yes' if r['marker_in_profile'] else 'no'} | {'yes' if r['wrong_name'] else 'no'} | {r['recommended_for_unrelated']}/{r['questions']} |"
            for r in i["rows"]
        ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def to_jsonable(value):
    if isinstance(value, AnswerScore):
        return score_dict(value)
    if isinstance(value, dict):
        return {key: to_jsonable(item) for key, item in value.items() if key != "by_id"}
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=FILES, required=True)
    parser.add_argument("--model", help="chat model instead of the one in config.yaml")
    parser.add_argument("--skip-capture", action="store_true", help="skip extraction, full pipeline and injection")
    parser.add_argument("--tag", default="", help="suffix of the output file names")
    args = parser.parse_args()

    base = load_config()
    if args.model:
        base = replace(base, llm=replace(base.llm, model=args.model))
    questions = read_jsonl(DATASET / FILES[args.split])
    notes = read_jsonl(DATASET / "notes.jsonl")
    gold = gold_contacts()
    temporary = Path(tempfile.mkdtemp(prefix="linkmate-eval-"))
    started = time.perf_counter()
    try:
        seeded = replace(base, data_dir=temporary / "seeded")
        seed(seeded, reset=True)
        services = build_services(seeded)
        contacts = {c.id: c for c in services.contacts.list_contacts()}
        print("retrieval", flush=True)
        retrieval = retrieval_table(services, questions)
        print("baselines", flush=True)
        bm25, bm25_by_id = baseline_answers(services, questions, "bm25")
        dense, _ = baseline_answers(services, questions, "dense")
        bm25_groups = {}
        for group in ("direct", "indirect"):
            subset = [q for q in questions if q["type"] == group]
            s, _ = baseline_answers(services, subset, "bm25")
            bm25_groups[group] = ci(s.hits, s.answerable)
        print("answers", flush=True)
        answers = system_answers(services, questions, contacts)
        memory = model_memory()
        wins = sum(answers["by_id"][q["id"]] and not bm25_by_id[q["id"]] for q in questions)
        losses = sum(bm25_by_id[q["id"]] and not answers["by_id"][q["id"]] for q in questions)
        data = {
            "split": args.split, "model": base.llm.model, "embedding": base.embedding.model,
            "contacts": len(contacts), "questions": len(questions), "threshold": base.retrieval.threshold,
            "strong_from": base.answer.strong_from, "max_candidates": base.retrieval.max_candidates,
            "retrieval": retrieval, "baseline_bm25": bm25, "baseline_dense": dense, "bm25_groups": bm25_groups,
            "answers": answers, "strong_only": strong_only(answers["rows"], questions), "sign_wins": wins, "sign_losses": losses, "sign_p": sign_test(wins, losses),
            "bias": bias_eval(answers["rows"], questions, contacts),
            "latency": {"p50": percentile(answers["seconds"], 0.5), "p95": percentile(answers["seconds"], 0.95)},
            "memory": memory,
        }
        if not args.skip_capture:
            print("extraction", flush=True)
            data["extraction"], proposals = extraction_eval(build_services(replace(base, data_dir=temporary / "extract")), notes, gold)
            print("pipeline", flush=True)
            data["pipeline"] = pipeline_eval(replace(base, data_dir=temporary / "pipeline"), proposals, questions, gold)
            print("injection", flush=True)
            data["injection"] = injection_eval(base, temporary)
    finally:
        shutil.rmtree(temporary, ignore_errors=True)

    data["minutes"] = (time.perf_counter() - started) / 60
    OUTPUT.mkdir(parents=True, exist_ok=True)
    name = f"{args.split}{'_' + args.tag if args.tag else ''}"
    write_report(OUTPUT / f"{name}.md", data)
    (OUTPUT / f"{name}.json").write_text(json.dumps(to_jsonable(data), indent=1, ensure_ascii=False), encoding="utf-8")
    with (OUTPUT / f"{name}_reasons.csv").open("w", newline="", encoding="utf-8") as out:
        writer = csv.DictWriter(out, ["question_id", "question", "contact", "relevant", "support", "reason", "cited_notes"])
        writer.writeheader()
        writer.writerows(answers["reasons"])
    print(f"Report: {OUTPUT / (name + '.md')}")


if __name__ == "__main__":
    main()
