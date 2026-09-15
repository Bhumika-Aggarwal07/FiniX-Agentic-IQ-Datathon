"""Interactive Investigation Explorer with integrated Gemini AI & deterministic evidence grounding."""
import streamlit as st

from dashboard.data import load_bundle
from dashboard.ui import page_header
from src.finix.gemini_chat import ask_gemini, gemini_available, load_gemini_config
from src.finix.investigation import EXAMPLES


page_header(
    "Investigation explorer",
    "AI-assisted and deterministic entity investigation. Ask natural-language questions or investigate specific users, merchants, transactions, or chargebacks grounded in verified risk evidence.",
)
bundle = load_bundle()

st.session_state.setdefault("investigation_messages", [])

key, model = load_gemini_config()
with st.sidebar:
    st.markdown("### Investigation engine")
    if gemini_available():
        st.success(f"Gemini Active ({model})", icon=":material/smart_toy:")
    else:
        st.info("Deterministic Engine Active", icon=":material/manage_search:")
        st.caption("Configure GEMINI_API_KEY in `env/.env` for generative AI responses.")
    st.caption("Privacy guarantee: No raw PII (PAN, Aadhaar, names) is ever transmitted.")


if not st.session_state["investigation_messages"]:
    suggestion = st.pills(
        "Try asking",
        list(EXAMPLES),
        selection_mode="single",
        label_visibility="collapsed",
        key="investigation_pills",
    )
    if suggestion:
        st.session_state["investigation_query"] = suggestion

for message in st.session_state["investigation_messages"]:
    avatar = ":material/manage_search:" if message["role"] == "assistant" else None
    with st.chat_message(message["role"], avatar=avatar):
        st.markdown(message["content"])
        if message.get("data") is not None and not message["data"].empty:
            st.dataframe(message["data"], hide_index=True)
        if message.get("provider"):
            st.caption(message["provider"])

prompt = st.chat_input("Ask about an entity (e.g. USR35882, MCH001)")
query = prompt or st.session_state.pop("investigation_query", "")
if query:
    st.session_state["investigation_messages"].append({"role": "user", "content": query})
    with st.chat_message("user"):
        st.markdown(query)
    with st.chat_message("assistant", avatar=":material/manage_search:"):
        with st.spinner("Analyzing risk signals and synthesizing evidence..."):
            reply = ask_gemini(query, bundle)
        st.markdown(reply.text)
        if not reply.evidence.data.empty:
            st.dataframe(reply.evidence.data, hide_index=True)
        if reply.provider:
            st.caption(f"Engine: {reply.provider}")
    st.session_state["investigation_messages"].append({
        "role": "assistant",
        "content": reply.text,
        "data": reply.evidence.data,
        "provider": f"Engine: {reply.provider}",
    })

if st.session_state["investigation_messages"] and st.button("Clear investigation", icon=":material/restart_alt:", type="tertiary"):
    st.session_state["investigation_messages"] = []
    st.rerun()

