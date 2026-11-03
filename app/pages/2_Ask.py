"""Flow B: question -> up to three contacts with a reason and source notes."""

from common import get_services, render_sources, safe_md, setup_page, show_ollama_error, show_system_banner

import streamlit as st

from linkmate.services import OllamaError
from linkmate.services.ask import MODES

setup_page("Ask · LinkMate", "🔎")
st.title("Ask for a contact")
st.caption("Every recommendation is backed by a source note. Without a valid source there is no recommendation.")

services = get_services()
ready = show_system_banner(services.contacts.status())

with st.form("ask"):
    question = st.text_input("What do you need?", placeholder="Who could help me calibrate an IMU sensor?")
    mode = st.selectbox(
        "Search mode",
        MODES,
        index=MODES.index(services.ask.default_mode),
        help="dense: embeddings. bm25: keywords. hybrid: both.",
    )
    submitted = st.form_submit_button("Ask", type="primary", disabled=not ready)

if submitted and not question.strip():
    st.warning("Please enter a question first.")
elif submitted:
    try:
        with st.spinner("Searching and asking the local model ..."):
            result = services.ask.ask(question, mode)
    except OllamaError as error:
        show_ollama_error(error)
        st.stop()
    except Exception as error:  # a damaged index must not end in a raw traceback
        st.error(f"The search failed. Try rebuilding the index on the Status page. ({safe_md(str(error))})")
        st.stop()

    if result.status == "no_match":
        st.info("No suitable contact.")
    elif result.status == "llm_failed":
        st.warning("The model did not give a valid explanation. These are the search hits without one:")
        for candidate in result.candidates:
            with st.container(border=True):
                st.markdown(
                    f"**{safe_md(candidate.name)}** · {safe_md(candidate.organization)} · score {candidate.score:.2f}"
                )
                render_sources(candidate.sources)

    for recommendation in result.recommendations:
        with st.container(border=True):
            details = " · ".join(part for part in (recommendation.organization, recommendation.role) if part)
            st.markdown(f"### {safe_md(recommendation.name)}")
            if recommendation.confidence == "weak":
                st.warning("Weak match. This contact may only be related to your need, so check the source note.")
            if details:
                st.caption(safe_md(details))
            st.markdown(safe_md(recommendation.reason))
            with st.expander(f"Source notes ({len(recommendation.sources)})", expanded=True):
                render_sources(recommendation.sources)

    with st.expander("Behind the answer"):
        st.write(f"Mode: {result.mode}. LLM called: {result.llm_called}.")
        st.write({step: f"{seconds:.2f} s" for step, seconds in result.timings.items()})
        if result.candidates:
            st.write("Candidates above the threshold:")
            st.table(
                [{"contact": c.name, "organization": c.organization, "score": round(c.score, 3)} for c in result.candidates]
            )
        if result.dropped:
            st.write("Dropped by validation:")
            st.json(result.dropped)
