"""Flow A: note -> proposal -> review -> save."""

from common import get_services, profile_form_fields, safe_md, setup_page, show_ollama_error, show_system_banner

import streamlit as st

from linkmate.services import OllamaError

setup_page("Capture · LinkMate", "📝")
st.title("Capture a contact")
st.caption("The model only proposes a profile. Nothing is saved until you confirm it.")

services = get_services()
ready = show_system_banner(services.contacts.status())

SAVED_KEY = "capture_saved"
PROPOSAL_KEY = "capture_proposal"
PROPOSAL_NUMBER_KEY = "capture_proposal_number"
NOTICE_KEY = "capture_notice"


saved = st.session_state.pop(SAVED_KEY, None)
if saved:
    st.success(f"Saved {safe_md(saved.contact.name)}.")
    for change in saved.changes:
        st.info(f"{change.field.title()}: '{safe_md(change.old)}' was replaced by '{safe_md(change.new)}'.")
    if saved.index_error:
        st.warning(f"Saved, but not indexed yet, so search cannot find it: {safe_md(saved.index_error)}")

with st.form("capture_note"):
    note_text = st.text_area("Note or pasted email", height=180, placeholder="Met Lena at the robotics meetup ...")
    source_type = st.radio("Type", ["note", "email"], horizontal=True)
    extract = st.form_submit_button("Extract profile", type="primary", disabled=not ready)

if extract:
    if not note_text.strip():
        st.warning("Please enter a note first.")
    else:
        try:
            with st.spinner("The local model is reading the note ..."):
                st.session_state[PROPOSAL_KEY] = services.capture.propose(note_text, source_type)
            st.session_state[PROPOSAL_NUMBER_KEY] = st.session_state.get(PROPOSAL_NUMBER_KEY, 0) + 1
        except OllamaError as error:
            show_ollama_error(error)

proposal = st.session_state.get(PROPOSAL_KEY)
if proposal:
    # Widgets get new keys per proposal, so edits from an earlier proposal cannot carry over.
    number = st.session_state[PROPOSAL_NUMBER_KEY]

    st.divider()
    st.subheader("Review")
    if proposal.extraction_failed:
        st.warning("The model did not return a valid profile. Please fill in the form by hand.")
    for warning in proposal.warnings:
        st.warning(safe_md(warning))
    notice = st.session_state.pop(NOTICE_KEY, None)
    if notice:
        st.warning(safe_md(notice))

    options = {"Create a new contact": None}
    for match in proposal.matches:
        label = f"Add to {match.name}" + (f" ({match.organization})" if match.organization else "")
        options[safe_md(label)] = match.contact_id
    # Only an exact name is preselected. For a similar name the user has to decide.
    default_target = 1 if proposal.matches and proposal.matches[0].score == 1.0 else 0
    target_label = st.radio(
        "Save as", list(options), index=default_target, key=f"target_{number}_{len(options)}"
    )
    target_id = options[target_label]

    draft, list_prefix, form_key = proposal.draft, "", str(number)
    review = services.capture.additive_review(target_id, proposal.draft) if target_id else None
    if target_id and not review:
        st.error("This contact no longer exists. Choose to create a new contact instead.")
    if review:
        contact, draft = review
        list_prefix, form_key = "New: ", f"{number}_{target_id}"
        st.info(f"This note is added to {safe_md(contact.name)}. Everything already known stays.")
        known = {
            "Skills": contact.values_of("skill"),
            "Interests": contact.values_of("interest"),
            "Offers of help": contact.values_of("offers_help"),
        }
        with st.expander("Already known", expanded=True):
            for label, values in known.items():
                if values:
                    st.markdown(f"**{label}:** {safe_md(', '.join(values))}")
            st.caption(f"{len(contact.notes)} earlier notes stay attached.")
        for change in services.capture.preview(target_id, proposal.draft):
            st.info(
                f"The note suggests {change.field} '{safe_md(change.new)}'. The current value stays "
                "unless you change it below."
            )

    with st.form(f"capture_review_{form_key}"):
        edited = profile_form_fields(draft, form_key, list_prefix)
        with st.expander("Original note"):
            st.text(proposal.note_text)
        save = st.form_submit_button("Confirm and save", type="primary")

    if st.button("Discard"):
        st.session_state.pop(PROPOSAL_KEY, None)
        st.rerun()

    if save:
        known = {match.contact_id for match in proposal.matches}
        matches = services.capture.propose_matches(edited.name) if edited.name.strip() else []
        if not edited.name.strip():
            st.error("A contact needs a name.")
        elif target_id is None and any(match.contact_id not in known for match in matches):
            # The name was typed or changed in the form, so it was not compared yet.
            proposal.matches = matches
            proposal.draft = edited
            st.session_state[NOTICE_KEY] = (
                f"A contact with a similar name to {edited.name} already exists. "
                "Choose below, then save again."
            )
            st.rerun()
        else:
            try:
                st.session_state[SAVED_KEY] = services.capture.confirm(
                    proposal.note_text, proposal.source_type, edited, target_id
                )
            except ValueError as error:  # e.g. the contact was deleted in the meantime
                st.error(safe_md(str(error)))
            else:
                st.session_state.pop(PROPOSAL_KEY, None)
                st.rerun()
