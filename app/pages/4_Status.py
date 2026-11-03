"""Models, search index and data problems."""

from common import get_services, setup_page, show_ollama_error, show_system_banner

import streamlit as st

from linkmate.services import OllamaError

setup_page("Status · LinkMate", "⚙️")
st.title("Status")

services = get_services()
status = services.contacts.status()
ready = show_system_banner(status)

ollama = status.ollama
st.subheader("Ollama")
st.write(f"Service: {'running' if ollama.running else 'not running'}")
st.write(f"Chat model `{ollama.chat_model}`: {'installed' if ollama.chat_model_ok else 'missing'}")
st.write(f"Embedding model `{ollama.embed_model}`: {'installed' if ollama.embed_model_ok else 'missing'}")

st.subheader("Search index")
st.write(f"{status.contact_count} contacts, {status.index_entries} entries in the index.")
if status.index_in_sync:
    st.success("Index is in sync with the contacts.")
else:
    st.warning(f"Index out of sync: {status.index_missing} entries missing, {status.index_extra} left over.")
if st.button("Rebuild index", disabled=not ready):
    try:
        with st.spinner("Rebuilding the index ..."):
            services.contacts.rebuild_index()
        st.rerun()
    except OllamaError as error:
        show_ollama_error(error)

st.subheader("Data")
if status.corrupt_files:
    st.warning("These contact files could not be read and were skipped:")
    st.json(status.corrupt_files)
else:
    st.write("All contact files are readable.")

st.subheader("LLM calls")
if status.llm_calls:
    st.write(f"{status.llm_calls} calls logged, {status.llm_average_seconds:.1f} s on average.")
    st.caption("The log holds note texts, so it keeps them after you delete a contact.")
    if st.button("Delete the LLM log"):
        services.contacts.clear_llm_log()
        st.rerun()
else:
    st.write("No calls logged yet.")
