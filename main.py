# main.py
import streamlit as st
import pandas as pd
import json
from uipath_connector import run_robot_and_get_output

# Page config
st.set_page_config(
    page_title="Welcome to Finclose AI Agent",
    layout="wide",
    page_icon="assets/jadeglobalbig.png"
)

# --- Custom CSS for chat layout ---
st.markdown("""
    <style>
    .chat-user { background:#46729f; color:white; padding:10px 14px; border-radius:12px;
                 max-width:80%; margin-left:auto; margin-bottom:8px; word-wrap: break-word;}
    .chat-agent { background:#f1f5f9; color:#111; padding:10px 14px; border-radius:12px;
                  max-width:80%; margin-right:auto; margin-bottom:8px; word-wrap: break-word;}
    .chat-container { height: 65vh; overflow-y: auto; padding: 12px; border-radius: 8px;
                      border: 1px solid #eee; background: white; display: flex; flex-direction: column-reverse;}
    .header-title {font-size:26px; font-weight:700;}
    .description { color:#374151; font-size:15px; margin-top:4px;}
    </style>
""", unsafe_allow_html=True)

# --- Session state initialization ---
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "agent", "text": "Hello 👋, I am ready to assist you. Please ask your finance-related query.", "table": None}
    ]

# --- Header ---
col1, col2 = st.columns([1, 6], gap="small")
with col1:
    st.image("assets/jadeglobalbig.png", width=90)
with col2:
    st.markdown('<div class="header-title">Welcome to Finclose AI Agent</div>', unsafe_allow_html=True)
    st.markdown("""
        <div class="description">
        I am Finance Assistant of your company.  
        I possess the ability to extract information from your company's financial statements like expense, invoice, balance sheet etc.  
        Please ask me questions and I will try my level best to provide accurate responses.
        </div>
    """, unsafe_allow_html=True)

st.write("")  # spacing

# --- Chat Window ---
st.markdown("### Chat")
chat_box = st.container()
with chat_box:
    # We add a div with a specific ID to scroll to it later
    st.markdown('<div class="chat-container" id="chat-window">', unsafe_allow_html=True)
    
    # Render messages
    for m in st.session_state.messages:
        if m["role"] == "user":
            st.markdown(f'<div class="chat-user">You: {m["text"]}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="chat-agent">Finclose Agent:</div>', unsafe_allow_html=True)
            # The agent response can be text, a table, or both
            if m.get("text"):
                st.code(m["text"], language="json")
            if m.get("table") is not None:
                st.dataframe(m["table"], use_container_width=True)

    st.markdown('</div>', unsafe_allow_html=True)


# --- Chat Input (NEW IMPLEMENTATION) ---
if prompt := st.chat_input("Write your message here..."):
    # Add user message to session state
    st.session_state.messages.append({"role": "user", "text": prompt, "table": None})

    # Call UiPath Agent
    with st.spinner("Sending to Finclose Agent..."):
        try:
            result = run_robot_and_get_output(prompt)
        except Exception as e:
            err_text = f"Error calling UiPath: {str(e)}"
            st.session_state.messages.append({"role": "agent", "text": err_text, "table": None})
        else:
            agent_text, agent_table = None, None
            parsed = result

            # This parsing logic remains the same as your original file
            try:
                if isinstance(parsed, str):
                    try:
                        parsed_json = json.loads(parsed)
                        parsed = parsed_json
                    except Exception:
                        agent_text = parsed
                if isinstance(parsed, dict) and "error" in parsed:
                    agent_text = "Agent error: " + str(parsed["error"])
                elif isinstance(parsed, dict) and "data" in parsed:
                    inner = parsed["data"]
                    if isinstance(inner, str):
                        try:
                            df = pd.read_json(inner, orient="split")
                            agent_table = df
                        except Exception:
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
                    if len(parsed) > 0 and isinstance(parsed[0], dict):
                        agent_table = pd.DataFrame(parsed)
                    else:
                        agent_text = json.dumps(parsed, indent=2)
                elif isinstance(parsed, dict):
                    agent_text = json.dumps(parsed, indent=2)
                else:
                    agent_text = str(parsed)
            except Exception as e:
                agent_text = "Error processing agent response: " + str(e)

            st.session_state.messages.append({"role": "agent", "text": agent_text, "table": agent_table})

    # Refresh the page to show the new messages
    st.rerun()
