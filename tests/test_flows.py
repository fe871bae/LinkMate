"""The whole core with a fake LLM, a fake embedder and a real Chroma and JSON store."""

import json
import shutil
from dataclasses import replace

import pytest
from conftest import profile_json

from linkmate.infra.ollama_client import OllamaUnavailable
from linkmate.models import ProfileDraft

NOTE = "Lena Hoffmann calibrates IMU sensors at Kessler and offered help with sensor calibration."


def save_lena(services, llm):
    llm.answers.append(profile_json(name="Lena Hoffmann", organization="Kessler", skills=["IMU calibration"]))
    proposal = services.capture.propose(NOTE)
    return services.capture.confirm(proposal.note_text, proposal.source_type, proposal.draft)


def recommend(label="C1", source="S1"):
    return json.dumps({"recommendations": [{"contact": label, "reason": "Calibrates IMUs.", "sources": [source]}]})


def test_propose_writes_nothing(services, llm, store):
    llm.answers.append(profile_json(name="Lena Hoffmann"))
    services.capture.propose(NOTE)
    assert store.all() == []


def test_capture_then_ask_returns_the_contact_with_its_source(services, llm):
    saved = save_lena(services, llm).contact
    assert saved.facts[0].source_note_ids == [saved.notes[0].id]

    llm.answers.append(recommend())
    result = services.ask.ask("Who can calibrate IMU sensors?")
    assert result.status == "ok"
    assert result.recommendations[0].name == "Lena Hoffmann"
    assert result.recommendations[0].sources[0].text == NOTE


def test_no_hit_answers_without_calling_the_llm(services, llm):
    save_lena(services, llm)
    llm.prompts.clear()
    result = services.ask.ask("Who owns a pizza oven?")
    assert result.status == "no_match" and not result.llm_called and not llm.prompts


def test_invalid_source_turns_into_no_suitable_contact(services, llm):
    save_lena(services, llm)
    llm.answers.append(recommend(source="S99"))
    result = services.ask.ask("Who can calibrate IMU sensors?")
    assert result.status == "no_match" and result.dropped


def test_invalid_json_is_retried_once(services, llm):
    save_lena(services, llm)
    llm.answers += ["broken", recommend()]
    assert services.ask.ask("Who can calibrate IMU sensors?").status == "ok"


def test_invalid_json_twice_shows_search_hits_without_explanation(services, llm):
    save_lena(services, llm)
    llm.answers += ["broken", "still broken"]
    result = services.ask.ask("Who can calibrate IMU sensors?")
    assert result.status == "llm_failed" and result.candidates[0].name == "Lena Hoffmann"


def test_extraction_failure_gives_an_empty_form(services, llm):
    llm.answers += ["broken", "still broken"]
    proposal = services.capture.propose(NOTE)
    assert proposal.extraction_failed and proposal.draft == ProfileDraft()


def test_second_note_is_matched_and_merged(services, llm, store):
    first = save_lena(services, llm).contact
    llm.answers.append(profile_json(name="Lena Hoffmann", role="Team lead"))
    proposal = services.capture.propose("Lena Hoffmann is now team lead.")
    assert proposal.matches[0].contact_id == first.id

    saved = services.capture.confirm(proposal.note_text, "note", proposal.draft, first.id)
    assert len(store.all()) == 1 and len(saved.contact.notes) == 2 and saved.contact.role == "Team lead"
    assert services.contacts.status().index_in_sync


def test_saved_note_text_is_never_changed(services, llm):
    assert save_lena(services, llm).contact.notes[0].text == NOTE


def test_json_stays_saved_when_indexing_fails(services, llm, store, monkeypatch):
    def fail(_):
        raise OllamaUnavailable("down")

    monkeypatch.setattr(services.capture._index, "upsert_contact", fail)
    result = save_lena(services, llm)
    assert result.index_error and len(store.all()) == 1
    assert not services.contacts.status().index_in_sync


def test_rebuild_restores_the_index(services, llm, store, index):
    save_lena(services, llm)
    index.delete_contact(store.all()[0].id)
    assert not services.contacts.status().index_in_sync
    services.contacts.rebuild_index()
    assert services.contacts.status().index_in_sync


def test_rebuild_works_after_the_index_folder_was_deleted(services, llm, index, tmp_path):
    save_lena(services, llm)
    shutil.rmtree(tmp_path / "chroma")
    services.contacts.rebuild_index()
    assert services.contacts.status().index_in_sync
    assert services.contacts.status().index_entries == 2


def test_delete_contact_removes_it_from_store_and_index(services, llm, store):
    contact = save_lena(services, llm).contact
    services.contacts.delete_contact(contact.id)
    status = services.contacts.status()
    assert store.all() == [] and status.index_entries == 0 and status.index_in_sync


def test_delete_note_removes_facts_only_it_supported(services, llm):
    first = save_lena(services, llm).contact
    llm.answers.append(profile_json(name="Lena Hoffmann", skills=["bouldering"]))
    proposal = services.capture.propose("Lena Hoffmann loves bouldering.")
    second = services.capture.confirm(proposal.note_text, "note", proposal.draft, first.id).contact

    services.contacts.delete_note(first.id, second.notes[1].id)
    remaining = services.contacts.get(first.id)
    assert [fact.value for fact in remaining.facts] == ["IMU calibration"]
    assert services.contacts.status().index_in_sync


def test_last_note_cannot_be_deleted(services, llm):
    contact = save_lena(services, llm).contact
    with pytest.raises(ValueError):
        services.contacts.delete_note(contact.id, contact.notes[0].id)


def test_corrupt_contact_file_is_skipped_and_listed(services, llm, store):
    save_lena(services, llm)
    (store.directory / "c_broken.json").write_text("{not json")
    status = services.contacts.status()
    assert status.contact_count == 1 and status.corrupt_files == ["c_broken.json"]


def test_score_decides_between_strong_and_weak_match(services, llm):
    save_lena(services, llm)
    services.ask._answer = replace(services.ask._answer, strong_from=-2.0)
    llm.answers.append(recommend())
    assert services.ask.ask(NOTE, "dense").recommendations[0].confidence == "strong"
    services.ask._answer = replace(services.ask._answer, strong_from=2.0)
    llm.answers.append(recommend())
    assert services.ask.ask(NOTE, "dense").recommendations[0].confidence == "weak"


def test_other_modes_are_never_strong(services):
    services.ask._answer = replace(services.ask._answer, strong_from=-2.0)
    assert services.ask._confidence(0.9, "bm25") == "weak"
    assert services.ask._confidence(0.9, "dense") == "strong"
