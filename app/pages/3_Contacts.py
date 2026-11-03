"""Browse contacts with their facts and source notes. Delete contacts and notes."""

from common import get_services, profile_form_fields, safe_md, setup_page

import streamlit as st

from linkmate.core.merge import draft_from_contact

setup_page("Contacts · LinkMate", "📇")
st.title("Contacts")

NOTICE_KEY = "contacts_notice"

services = get_services()
contacts = services.contacts.list_contacts()

notice = st.session_state.pop(NOTICE_KEY, None)
if notice:
    st.warning(f"Saved, but the index was not updated: {safe_md(notice)}")

query = st.text_input("Filter by name or organization").strip().lower()
if query:
    contacts = [c for c in contacts if query in c.name.lower() or query in c.organization.lower()]

st.caption(f"{len(contacts)} contacts")
if contacts:
    st.download_button(
        "Export all contacts as JSON",
        services.contacts.export_json(),
        file_name="linkmate_contacts.json",
        mime="application/json",
    )

if not contacts:
    st.info("No contacts found.")


def finish_delete(error: str) -> None:
    if error:
        st.session_state[NOTICE_KEY] = error
    st.rerun()


def finish_edit(error: str) -> None:
    if error:
        st.session_state[NOTICE_KEY] = error
    st.rerun()


for contact in contacts:
    title = safe_md(contact.name + (f" · {contact.organization}" if contact.organization else ""))
    with st.expander(title):
        if contact.aliases:
            st.markdown(f"**Also known as:** {safe_md(', '.join(contact.aliases))}")
        for label, value in (("Role", contact.role), ("Location", contact.location), ("Where met", contact.met_context)):
            if value:
                st.markdown(f"**{label}:** {safe_md(value)}")
        if contact.summary:
            st.markdown(safe_md(contact.summary))

        notes_by_id = {note.id: index for index, note in enumerate(contact.notes, start=1)}
        for label, kind in (("Skills", "skill"), ("Interests", "interest"), ("Offers help with", "offers_help")):
            facts = [fact for fact in contact.facts if fact.kind == kind]
            if facts:
                st.markdown(f"**{label}**")
                for fact in facts:
                    origin = ", ".join(f"note {notes_by_id[n]}" for n in fact.source_note_ids if n in notes_by_id)
                    st.markdown(f"- {safe_md(fact.value)} ({origin})")

        for index, note in enumerate(contact.notes, start=1):
            st.markdown(f"**Note {index}** · {note.source_type} · {note.created_at:%Y-%m-%d}")
            st.text(note.text)
            if len(contact.notes) > 1 and st.button(
                "Delete this note",
                key=f"delete_note_{note.id}",
                help="Removes the note and the facts only it supports. Fields like role stay as they are.",
            ):
                finish_delete(services.contacts.delete_note(contact.id, note.id))

        with st.popover("Edit profile"):
            with st.form(f"edit_{contact.id}"):
                edited = profile_form_fields(draft_from_contact(contact), f"edit_{contact.id}")
                if st.form_submit_button("Save changes", type="primary"):
                    try:
                        finish_edit(services.contacts.update_contact(contact.id, edited))
                    except ValueError as error:
                        st.error(safe_md(str(error)))

        if st.checkbox("I want to delete this contact", key=f"confirm_{contact.id}"):
            if st.button("Delete contact", key=f"delete_{contact.id}", type="primary"):
                finish_delete(services.contacts.delete_contact(contact.id))
