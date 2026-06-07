"""ui/app.py — BankIQ Streamlit UI
Run from project root:  streamlit run ui/app.py
"""

import os
import sys

import requests
import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

API_BASE = "http://localhost:8000"

st.set_page_config(
    page_title="BankIQ",
    page_icon="🏦",
    layout="centered",
    initial_sidebar_state="expanded",
)
### Sidebar
with st.sidebar:
    st.title("BankIQ 🏦")
    st.divider()
    if st.button("＋ New Chat", use_container_width=True, type="primary"):
        st.session_state.messages = []
        st.rerun()
    if st.button("Clear", use_container_width=True, type="secondary"):
        st.session_state.messages = []
        st.rerun()

### Session state
if "messages" not in st.session_state:
    st.session_state.messages = []

### Chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

### Chat input (pinned to bottom by Streamlit) 
if prompt := st.chat_input("Ask BankIQ anything…"):
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.spinner("Thinking…"):
        try:
            resp = requests.post(
                f"{API_BASE}/chat",
                json={"message": prompt},
                timeout=120,
            )
            resp.raise_for_status()
            answer = resp.json()["answer"]
        except requests.exceptions.ConnectionError:
            answer = "⚠️ Cannot reach the API. Run `python main.py` first."
        except Exception as exc:
            answer = f"⚠️ Error: {exc}"

    st.session_state.messages.append({"role": "assistant", "content": answer})
    st.rerun()
