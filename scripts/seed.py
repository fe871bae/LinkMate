"""Load the synthetic dataset into the contact store and rebuild the index.

Usage: python scripts/seed.py [--reset]
--reset removes all contacts in the store first, including ones you captured.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from linkmate.config import PROJECT_ROOT, Config, load_config
from linkmate.infra.store import ContactStore
from linkmate.models import Contact
from linkmate.services import build_services

DATASET_DIR = PROJECT_ROOT / "data" / "dataset" / "contacts"


def seed(config: Config, reset: bool = False) -> int:
    store = ContactStore(config.contacts_dir)
    if reset:
        for contact in store.all():
            store.delete(contact.id)
    paths = sorted(DATASET_DIR.glob("c_*.json"))
    for path in paths:
        store.save(Contact.model_validate_json(path.read_text(encoding="utf-8")))
    build_services(config).contacts.rebuild_index()
    return len(paths)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reset", action="store_true", help="remove existing contacts first")
    args = parser.parse_args()
    count = seed(load_config(), reset=args.reset)
    print(f"Seeded {count} contacts and rebuilt the index.")


if __name__ == "__main__":
    main()
