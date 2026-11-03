import json

import pytest

from linkmate.core.merge import draft_from_contact
from linkmate.models import ProfileDraft


def save(services, **fields):
    draft = ProfileDraft(name="Lena Hoffmann", skills=["IMU calibration"], **fields)
    return services.capture.confirm("Lena calibrates IMUs.", "note", draft).contact


def test_edit_changes_fields_and_keeps_note_and_sources(services, store):
    contact = save(services, role="engineer")
    draft = draft_from_contact(contact).model_copy(update={"role": "team lead", "skills": ["IMU calibration", "CAD"]})
    assert services.contacts.update_contact(contact.id, draft) == ""
    saved = store.get(contact.id)
    assert saved.role == "team lead"
    assert saved.notes == contact.notes
    sources = {fact.value: fact.source_note_ids for fact in saved.facts}
    assert sources == {"IMU calibration": [contact.notes[0].id], "CAD": []}


def test_edit_updates_the_index(services, index, monkeypatch):
    contact = save(services)
    calls = []
    monkeypatch.setattr(index, "upsert_contact", lambda c: calls.append(c.role))
    services.contacts.update_contact(contact.id, draft_from_contact(contact).model_copy(update={"role": "lead"}))
    assert calls == ["lead"]


def test_edit_needs_a_name_and_an_existing_contact(services):
    contact = save(services)
    with pytest.raises(ValueError):
        services.contacts.update_contact(contact.id, ProfileDraft(name=" "))
    with pytest.raises(ValueError):
        services.contacts.update_contact("c_missing", ProfileDraft(name="X"))


def test_delete_note_keeps_a_fact_the_user_typed(services, store):
    contact = save(services)
    second = services.capture.confirm("Second note.", "note", ProfileDraft(name="Lena Hoffmann"), contact.id).contact
    services.contacts.update_contact(
        contact.id, draft_from_contact(second).model_copy(update={"skills": ["IMU calibration", "typed by hand"]})
    )
    services.contacts.delete_note(contact.id, contact.notes[0].id)
    assert [fact.value for fact in store.get(contact.id).facts] == ["typed by hand"]


def test_export_holds_contacts_with_notes(services):
    contact = save(services)
    exported = json.loads(services.contacts.export_json())
    assert exported["contacts"][0]["id"] == contact.id
    assert exported["contacts"][0]["notes"][0]["text"] == "Lena calibrates IMUs."
