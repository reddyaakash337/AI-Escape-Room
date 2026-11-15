"""Version 1 - Interactive AI Escape Room.

The LLM is the Game Master AND the only keeper of game state. Everything
(room, puzzles, solutions) lives in the system prompt; memory is just the
chat history. Simple and fun, but unreliable (see docs/test-cases.md).

Run:  streamlit run v1/app.py
"""
import os
import streamlit as st
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

SYSTEM_PROMPT = """You are the Game Master of a text escape room. Stay in character.

SETTING: The player woke up in a locked library at night. Objects: a desk, a
bookshelf, a painting, a locked drawer and a door with a four-digit keypad.

SECRET SOLUTION (never state it outright; reveal only through play):
- Desk: contains a flashlight.
- Bookshelf: four oddly arranged books with handwritten numbers 4, 1, 7, 2.
- Drawer: opens with code 4172. Inside is a torn note: "Last two digits: 31.
  The first two are hidden in the painting."
- Painting: looks like a plain lighthouse; shining the flashlight on it reveals
  glowing numbers 58.
- Door: code 5831 opens it.

RULES:
- Describe what the player sees in 2-4 sentences, then wait for their next action.
- Remember what the player has found and done.
- Give a small nudge only if the player is stuck.
- When the player enters 5831 on the door, describe their escape and end the
  message with the exact token [ESCAPED].
"""

INTRO = ("You wake up on a cold floor in a dim, locked library. A desk, a tall "
         "bookshelf, a painting, a small drawer and a door with a four-digit "
         "keypad surround you. Find the clues and escape. Type what you want to do.")


@st.cache_resource
def get_client():
    return genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def new_chat():
    client = get_client()
    return client.chats.create(
        model=MODEL,
        config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
    )

def reset():
    st.session_state.chat = new_chat()
    st.session_state.messages = [("assistant", INTRO)]
    st.session_state.escaped = False


st.set_page_config(page_title="AI Escape Room v1", page_icon="🗝️")
st.title("🗝️ AI Escape Room - Version 1")
if not os.getenv("GEMINI_API_KEY"):
    st.error("Set GEMINI_API_KEY in your .env file (see .env.example).")
    st.stop()
if "chat" not in st.session_state:
    reset()

with st.sidebar:
    st.markdown("**How to play**\n\nType actions like *examine the bookshelf*, "
                "*take the flashlight*, *try 1234 on the drawer*.")
    if st.button("🔄 Restart game"):
        reset()
        st.rerun()

for role, text in st.session_state.messages:
    st.chat_message(role).write(text)

if st.session_state.escaped:
    st.success("🎉 You escaped! Press Restart to play again.")
elif prompt := st.chat_input("What do you do?"):
    st.session_state.messages.append(("user", prompt))
    try:
        reply = st.session_state.chat.send_message(prompt).text or ""
    except Exception as e:  # network / quota errors
        reply = f"(The Game Master is unavailable: {e})"
    if "[ESCAPED]" in reply:  # V1 trusts the LLM to declare victory
        st.session_state.escaped = True
        reply = reply.replace("[ESCAPED]", "").strip()
    st.session_state.messages.append(("assistant", reply))
    st.rerun()
