"""Contact store: one JSON file per contact. This is the source of truth."""

from __future__ import annotations

import os
from pathlib import Path

from linkmate.models import Contact


class ContactStore:
    def __init__(self, directory: Path):
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)

    def save(self, contact: Contact) -> None:
        path = self._path(contact.id)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(contact.model_dump_json(indent=2), encoding="utf-8")
        os.replace(temporary, path)

    def get(self, contact_id: str) -> Contact | None:
        try:
            return Contact.model_validate_json(self._path(contact_id).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def delete(self, contact_id: str) -> None:
        self._path(contact_id).unlink(missing_ok=True)

    def all(self) -> list[Contact]:
        return self.load_all()[0]

    def load_all(self) -> tuple[list[Contact], list[str]]:
        """Return all readable contacts and the names of the files that are corrupt."""
        contacts, corrupt = [], []
        for path in sorted(self.directory.glob("c_*.json")):
            try:
                contacts.append(Contact.model_validate_json(path.read_text(encoding="utf-8")))
            except (OSError, ValueError):
                corrupt.append(path.name)
        return contacts, corrupt

    def _path(self, contact_id: str) -> Path:
        return self.directory / f"{contact_id}.json"
