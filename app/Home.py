"""LinkMate start page. Run with: streamlit run app/Home.py"""

from common import get_services, setup_page, show_system_banner

import streamlit as st

setup_page("LinkMate", "🔗")

st.title("LinkMate")
st.write("Turn notes about people into searchable profiles and find the right contact for a need.")

services = get_services()
status = services.contacts.status()
show_system_banner(status)

columns = st.columns(3)
columns[0].metric("Contacts", status.contact_count)
columns[1].metric("Search index entries", status.index_entries)
columns[2].metric("Chat model", status.ollama.chat_model)

st.subheader("What do you want to do?")
st.page_link("pages/1_Capture.py", label="Capture a contact from a note or email", icon="📝")
st.page_link("pages/2_Ask.py", label="Ask who can help with a need", icon="🔎")
st.page_link("pages/3_Contacts.py", label="Browse, edit, export and delete contacts", icon="📇")
st.page_link("pages/4_Status.py", label="Check models and the search index", icon="⚙️")

if status.contact_count == 0:
    st.info("No contacts yet. Capture one, or load the synthetic dataset with `python scripts/seed.py`.")

st.caption("Everything runs on this laptop: local models via Ollama, data in local files.")
