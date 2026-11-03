"""Rebuild the Chroma index from the JSON contact store."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from linkmate.config import load_config
from linkmate.services import build_services


def main() -> None:
    services = build_services(load_config())
    services.contacts.rebuild_index()
    status = services.contacts.status()
    print(f"Indexed {status.index_entries} entries for {status.contact_count} contacts.")


if __name__ == "__main__":
    main()
