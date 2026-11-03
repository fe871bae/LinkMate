"""The Streamlit pages with fake services' LLM. Regression tests for review form behavior."""

import json
from dataclasses import replace
from pathlib import Path

import pytest
from conftest import profile_json
from streamlit.testing.v1 import AppTest

from linkmate.models import ProfileDraft

APP = Path(__file__).resolve().parents[1] / "app"
NOTE = "Lena Hoffmann calibrates IMU sensors at Kessler."


@pytest.fixture
def open_page(services, monkeypatch):
    monkeypatch.syspath_prepend(str(APP))
    import common

    monkeypatch.setattr(common, "get_services", lambda: services)

    def run(page: str) -> AppTest:
        return AppTest.from_file(str(APP / "pages" / page), default_timeout=30).run()

    return run


def field(page, label):
    widgets = list(page.text_input) + list(page.text_area)
    return next(widget for widget in widgets if widget.label == label)


def click(page, label):
    next(button for button in page.button if button.label == label).click()
    return page.run()


def extract(page, note):
    field(page, "Note or pasted email").set_value(note)
    return click(page, "Extract profile")


def saved_lena(services):
    return services.capture.confirm(NOTE, "note", ProfileDraft(name="Lena Hoffmann", organization="Kessler")).contact


def test_edits_do_not_carry_over_to_the_next_proposal(open_page, llm, store):
    llm.answers += [profile_json(name=""), profile_json(name="Bob Stone")]
    page = extract(open_page("1_Capture.py"), "A note without a name.")
    field(page, "Role").set_value("CTO")
    page = click(page, "Confirm and save")
    assert page.error  # no name

    page = extract(page, "Bob Stone is nice.")
    assert field(page, "Role").value == ""
    click(page, "Confirm and save")
    assert store.all()[0].name == "Bob Stone" and store.all()[0].role == ""


def test_exact_name_preselects_merge(open_page, services, llm):
    saved_lena(services)
    llm.answers.append(profile_json(name="Lena Hoffmann"))
    page = extract(open_page("1_Capture.py"), NOTE)
    assert page.radio[1].value.startswith("Add to Lena")


def test_similar_name_does_not_preselect_merge(open_page, services, llm):
    saved_lena(services)
    llm.answers.append(profile_json(name="Lea Hoffmann"))
    page = extract(open_page("1_Capture.py"), "Lea Hoffmann runs a bakery.")
    assert page.radio[1].value == "Create a new contact"
    assert any(option.startswith("Add to Lena") for option in page.radio[1].options)


def test_contact_deleted_during_review_shows_an_error(open_page, services, llm, store):
    contact = saved_lena(services)
    llm.answers.append(profile_json(name="Lena Hoffmann"))
    page = extract(open_page("1_Capture.py"), NOTE)
    services.contacts.delete_contact(contact.id)
    page = click(page, "Confirm and save")
    assert page.error and not page.exception and store.all() == []


def test_typed_name_of_existing_contact_asks_before_creating_a_duplicate(open_page, services, llm, store):
    saved_lena(services)
    llm.answers += ["broken", "still broken"]
    page = extract(open_page("1_Capture.py"), NOTE)
    field(page, "Name").set_value("Lena Hoffmann")
    page = click(page, "Confirm and save")
    assert len(store.all()) == 1 and page.warning
    assert field(page, "Name").value == "Lena Hoffmann"

    page.radio[1].set_value("Create a new contact")
    click(page, "Confirm and save")
    assert len(store.all()) == 2  # two people can share a name, the user decided


def test_model_output_is_not_rendered_as_markdown(open_page, services, llm):
    saved_lena(services)
    evil = "![x](http://evil.example/leak)"
    llm.answers.append(
        json.dumps({"recommendations": [{"contact": "C1", "reason": evil, "sources": ["S1"]}]})
    )
    page = open_page("2_Ask.py")
    field(page, "What do you need?").set_value("Who calibrates IMU sensors at Kessler?")
    page = click(page, "Ask")
    rendered = [element.value for element in page.markdown]
    assert not any(evil in value for value in rendered)
    assert any("evil" in value for value in rendered)


def test_shut_down_button_stops_the_server(open_page, monkeypatch):
    import threading

    import common

    stopped = threading.Event()
    monkeypatch.setattr(common, "SHUTDOWN_DELAY_SECONDS", 0)
    monkeypatch.setattr(common, "stop_server", stopped.set)
    page = open_page("4_Status.py")
    assert not stopped.is_set()
    click(page, "Shut down LinkMate")
    assert stopped.wait(timeout=5)


def test_contact_can_be_edited_on_the_contacts_page(open_page, services, store):
    contact = saved_lena(services)
    page = open_page("3_Contacts.py")
    field(page, "Role").set_value("Team lead")
    page = click(page, "Save changes")
    assert store.get(contact.id).role == "Team lead"
    assert not page.exception


def test_weak_match_is_labeled_on_the_ask_page(open_page, services, llm):
    saved_lena(services)
    services.ask._answer = replace(services.ask._answer, strong_from=2.0)
    llm.answers.append(json.dumps({"recommendations": [{"contact": "C1", "reason": "Fits.", "sources": ["S1"]}]}))
    page = open_page("2_Ask.py")
    field(page, "What do you need?").set_value(NOTE)
    page = click(page, "Ask")
    assert any("Weak match" in warning.value for warning in page.warning)
