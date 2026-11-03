"""How LinkMate behaves with many contacts: add fictional distractors and measure.

Usage: python eval/scale.py [--sizes 0 500 2000 5000]

Distractors are generated people from fields no labeled question is about. Measures index
time, disk use, search and full question latency, and whether retrieval quality on the
development questions survives. Writes reports/evaluation/scale.md and .json.
"""

from __future__ import annotations

import argparse
import json
import random
import shutil
import sys
import tempfile
import time
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from run_e2e import read_jsonl
from seed import seed

from eval.metrics import percentile, recall_at, reciprocal_rank
from linkmate.config import PROJECT_ROOT, load_config
from linkmate.infra.store import ContactStore
from linkmate.models import Contact, Fact, Note
from linkmate.services import build_services

FIRST = "Alma Bruno Cora Dario Edda Fritz Greta Hamid Ida Jens Kaja Lars Mona Nils Olga Pavel Quinn Rosa Sven Tess Ulla Viktor Wanda Xander Yara Zeno".split()
LAST = "Abbott Baum Calder Dorn Eklund Frey Gomez Holt Ivers Janek Kerr Lund Maas Noor Ortiz Pohl Quist Reiss Sato Thorne Unger Vance Wolff Yilmaz Zeller".split()
FIELDS = [
    ("tram driver", "drives the harbor line", "tram schedules"),
    ("beekeeper", "keeps bees and sells honey", "honey harvesting"),
    ("ferry captain", "steers the island ferry", "harbor navigation"),
    ("tailor", "alters suits", "suit alterations"),
    ("glassblower", "makes glass vases", "glass blowing"),
    ("florist", "arranges flowers for shops", "flower arranging"),
    ("stonemason", "restores old walls", "stone masonry"),
    ("chimney sweep", "cleans chimneys", "chimney cleaning"),
    ("clockmaker", "repairs antique clocks", "clock repair"),
    ("farrier", "shoes horses", "horseshoeing"),
    ("bookbinder", "rebinds old books", "bookbinding"),
    ("roofer", "lays clay tiles", "roof tiling"),
]
CITIES = ["Bakersfield", "Fresno", "Tucson", "Reno", "Boise", "Eugene", "Provo", "Santa Fe"]


def distractor(number: int, rng: random.Random) -> Contact:
    title, activity, skill = rng.choice(FIELDS)
    name = f"{FIRST[number % len(FIRST)]} {LAST[number // len(FIRST) % len(LAST)]} {number}"
    city = rng.choice(CITIES)
    note = Note(id=f"n_d{number:06d}", text=f"{name} is a {title} in {city}, {activity}. Met at a street fair. Said to ask any time about {skill}.")
    return Contact(
        id=f"c_d{number:06d}", name=name, role=title, location=city, met_context="street fair", notes=[note],
        facts=[Fact(kind="skill", value=skill, source_note_ids=[note.id])],
    )


def folder_size(path: Path) -> int:
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def measure(size: int, questions: list[dict], base) -> dict:
    temporary = Path(tempfile.mkdtemp(prefix="linkmate-scale-"))
    config = replace(base, data_dir=temporary)
    rng = random.Random(451)
    try:
        seed(config, reset=True)
        store = ContactStore(config.contacts_dir)
        for number in range(size):
            store.save(distractor(number, rng))
        services = build_services(config)
        started = time.perf_counter()
        services.contacts.rebuild_index()
        index_seconds = time.perf_counter() - started

        answerable = [q for q in questions if q["expected_contact_ids"]]
        search_seconds, ranks = [], []
        for question in answerable:
            started = time.perf_counter()
            ranked = [c.contact_id for c in services.ask.search(question["question"], "dense")]
            search_seconds.append(time.perf_counter() - started)
            ranks.append((ranked, set(question["expected_contact_ids"])))

        started = time.perf_counter()
        loaded = len(store.all())
        load_seconds = time.perf_counter() - started

        ask_seconds, hits = [], 0
        for question in answerable[:12]:
            started = time.perf_counter()
            result = services.ask.ask(question["question"])
            ask_seconds.append(time.perf_counter() - started)
            hits += bool(set(question["expected_contact_ids"]) & {r.contact_id for r in result.recommendations})
        return {
            "distractors": size, "contacts": loaded,
            "entries": services.contacts.status().index_entries,
            "index_minutes": index_seconds / 60,
            "index_mb": folder_size(config.chroma_dir) / 1e6,
            "store_mb": folder_size(config.contacts_dir) / 1e6,
            "load_seconds": load_seconds,
            "search_p50": percentile(search_seconds, 0.5), "search_p95": percentile(search_seconds, 0.95),
            "ask_p50": percentile(ask_seconds, 0.5), "ask_p95": percentile(ask_seconds, 0.95),
            "recall@3": sum(recall_at(r, e, 3) for r, e in ranks) / len(ranks),
            "mrr": sum(reciprocal_rank(r, e) for r, e in ranks) / len(ranks),
            "hits_sample": f"{hits}/12",
        }
    finally:
        shutil.rmtree(temporary, ignore_errors=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes", type=int, nargs="+", default=[0, 500, 2000, 5000])
    parser.add_argument("--top-k", type=int, help="index entries fetched per question instead of the configured value")
    parser.add_argument("--tag", default="", help="suffix of the output file names")
    args = parser.parse_args()
    base = load_config()
    if args.top_k:
        base = replace(base, retrieval=replace(base.retrieval, top_k=args.top_k))
    questions = read_jsonl(PROJECT_ROOT / "data" / "dataset" / "questions.jsonl")
    rows = []
    for size in args.sizes:
        print("size", size, flush=True)
        rows.append(measure(size, questions, base))
        print(rows[-1], flush=True)
    out = PROJECT_ROOT / "reports" / "evaluation"
    out.mkdir(parents=True, exist_ok=True)
    name = f"scale{'_' + args.tag if args.tag else ''}"
    (out / f"{name}.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    lines = [
        "# LinkMate scalability", "",
        "The 55 labeled contacts plus generated distractors, measured on the development machine.", "",
        "| Contacts | Index entries | Full index (min) | Index size (MB) | JSON store (MB) | Load all contacts (s) | Search p50 / p95 (s) | Full question p50 / p95 (s) | Recall@3 | MRR | Right contact in a 12 question sample |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['contacts']} | {r['entries']} | {r['index_minutes']:.2f} | {r['index_mb']:.0f} | {r['store_mb']:.1f} | {r['load_seconds']:.2f} "
            f"| {r['search_p50']:.3f} / {r['search_p95']:.3f} | {r['ask_p50']:.2f} / {r['ask_p95']:.2f} | {r['recall@3']:.2f} | {r['mrr']:.2f} | {r['hits_sample']} |"
        )
    (out / f"{name}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
