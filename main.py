# main.py  (replace your existing main.py with this file)
import streamlit as st
import pandas as pd
import json
import time
from datetime import datetime
from uipath_connector import run_robot_and_get_output

# Page config and small CSS to keep look similar to your previous app
st.set_page_config(page_title="Welcome to Finclose AI Agent", layout="wide", page_icon="assets/jadeglobalbig.png")

# --- Minimal CSS to make chat look nicer (keeps general style from your original app) ---
st.markdown("""
    <style>
    .chat-user { background:#46729f; color:white; padding:10px 14px; border-radius:12px; max-width:80%; margin-left:auto; margin-bottom:8px;}
    .chat-agent { background:#f1f5f9; color:#111; padding:10px 14px; border-radius:12px; max-width:80%; margin-right:auto; margin-bottom:8px;}
    .chat-container { height: 60vh; overflow-y: auto; padding: 12px; border-radius: 8px; border: 1px solid #eee; background: white;}
    .header-title {font-size:24px; font-weight:700;}
    .muted { color:#6b7280; font-size:13px;}
    </style>
""", unsafe_allow_html=True)

# --- Session state initialization ---
if "messages" not in st.session_state:
    # messages is list of dicts: {role: "user"|"agent", "text": str, "table": optional DataFrame}
    st.session_state.messages = [
        {"role": "agent", "text": "Welcome to Finclose AI Agent. Ask me queries like: 'give me top 5 vendors' or 'top employees by expense'.", "table": None}
    ]

# header row
col1, col2 = st.columns([1, 3], gap="small")
with col1:
    st.image("assets/jadeglobalbig.png", width=100)
with col2:
    st.markdown('<div class="header-title">Welcome to Finclose AI Agent</div>', unsafe_allow_html=True)
    st.markdown('<div class="muted">Ask questions in natural language — the agent will generate and run SQL and return results.</div>', unsafe_allow_html=True)

st.write("")  # spacing

# Main layout: left: chat, right: info/help
left, right = st.columns([3, 1], gap="large")

with left:
    st.markdown("### Chat")
    chat_box = st.container()
    with chat_box:
        st.markdown('<div class="chat-container" id="chat-window">', unsafe_allow_html=True)
        # render chat messages
        for m in st.session_state.messages:
            if m["role"] == "user":
                st.markdown(f'<div class="chat-user">{st.session_state.get("last_user_name","You")}: {st.markdown(m["text"], unsafe_allow_html=True) if False else st.write("",unsafe_allow_html=True)}</div>', unsafe_allow_html=True)
                # The above is a trick to allow consistent layout; below we actually render text:
                st.markdown(f'<div class="chat-user">You: {m["text"]}</div>', unsafe_allow_html=True)
            else:
                # agent
                st.markdown(f'<div class="chat-agent">Finclose Agent:</div>', unsafe_allow_html=True)
                if m.get("text"):
                    # pretty JSON text
                    st.code(m["text"], language="json")
                if m.get("table") is not None:
                    st.dataframe(m["table"], use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # Input form
    with st.form("chat_form", clear_on_submit=True):
        prompt = st.text_input("Write your message here...", key="user_prompt")
        submitted = st.form_submit_button("Send")
        if submitted and prompt:
            # Append user message immediately
            st.session_state.messages.append({"role": "user", "text": prompt, "table": None})

            # Call the agent (UiPath) synchronously (this function polls until job finishes)
            with st.spinner("Sending to Finclose Agent..."):
                try:
                    result = run_robot_and_get_output(prompt)
                except Exception as e:
                    # show error from uipath connector
                    err_text = f"Error calling UiPath: {str(e)}"
                    st.session_state.messages.append({"role": "agent", "text": err_text, "table": None})
                else:
                    # Normalize various kinds of outputs and display appropriately
                    agent_text, agent_table = None, None

                    # If connector returns a python object already (dict/list) -> handle
                    parsed = result
                    # Many possible shapes:
                    # - list of dicts -> table
                    # - dict with { "data": "<json string>" } -> parse inner
                    # - dict with "error" -> show error
                    try:
                        if isinstance(parsed, str):
                            # maybe JSON string
                            try:
                                parsed_json = json.loads(parsed)
                                parsed = parsed_json
                            except Exception:
                                # plain text string
                                agent_text = parsed
                        if isinstance(parsed, dict) and "error" in parsed:
                            agent_text = "Agent error: " + str(parsed["error"])
                        elif isinstance(parsed, dict) and "data" in parsed:
                            # agent_backend used "data": the string may be a serialized dataframe (orient='split')
                            inner = parsed["data"]
                            # sometimes inner is a json string of dataframe - try to parse
                            if isinstance(inner, str):
                                try:
                                    # try the orient='split' parse first
                                    df = pd.read_json(inner, orient="split")
                                    agent_table = df
                                except Exception:
                                    # try normal json loads -> if it's list of dicts
                                    try:
                                        maybe_list = json.loads(inner)
                                        if isinstance(maybe_list, list):
                                            agent_table = pd.DataFrame(maybe_list)
                                        else:
                                            agent_text = json.dumps(maybe_list, indent=2)
                                    except Exception:
                                        agent_text = str(inner)
                            elif isinstance(inner, list):
                                agent_table = pd.DataFrame(inner)
                            else:
                                agent_text = json.dumps(inner, indent=2)
                        elif isinstance(parsed, list):
                            # list of dicts -> table
                            if len(parsed) > 0 and isinstance(parsed[0], dict):
                                agent_table = pd.DataFrame(parsed)
                            else:
                                agent_text = json.dumps(parsed, indent=2)
                        elif isinstance(parsed, dict):
                            # map/dict -> pretty JSON
                            agent_text = json.dumps(parsed, indent=2)
                        else:
                            # fallback
                            agent_text = str(parsed)
                    except Exception as e:
                        agent_text = "Error processing agent response: " + str(e)

                    # append agent response to messages
                    st.session_state.messages.append({"role": "agent", "text": agent_text, "table": agent_table})

            # Force rerun to show new messages immediately
            st.experimental_rerun()

with right:
    st.markdown("### Help / Tips")
    st.markdown("- Ask: `give me top 5 vendors`")
    st.markdown("- Ask: `show top employees by expenses`")
    st.markdown("- The agent will build and run SQL and return a table when applicable.")
    st.markdown("**Debug tips**:")
    st.markdown("1. If nothing shows, check the UiPath job status in Orchestrator.")
    st.markdown("2. If UiPath job fails, `main.py` will show the error returned by the connector.")
