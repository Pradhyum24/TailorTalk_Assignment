# frontend/streamlit_app.py

import streamlit as st
import requests
BACKEND_URL = "https://tailortalk-backend.onrender.com/chat"

st.set_page_config(page_title="Assignment", page_icon="🧵")
st.title("Book your meeting")

# Session history
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# User input
user_input = st.chat_input("Ask me to book, cancel, or show available slots")

# Display chat history
for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# On user message
if user_input:
    st.session_state.chat_history.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # Send request to FastAPI backend
    try:
        response = requests.post(BACKEND_URL, json={"message": user_input})
        response_data = response.json()
        bot_reply = response_data.get("response", "❌ Something went wrong.")
    except Exception as e:
        bot_reply = f"❌ Error: {e}"

    st.session_state.chat_history.append({"role": "assistant", "content": bot_reply})
    with st.chat_message("assistant"):
        st.markdown(bot_reply)
