"""Version 2 - Reliable AI Escape Room (Streamlit).

Pipeline per turn:
  player text -> LLM intent parser -> Python normalisation/validation
  -> engine applies rules to structured state -> FACTS -> LLM narrator -> UI

Run:  streamlit run v2/app.py
"""
import streamlit as st
import engine
import llm

st.set_page_config(page_title="AI Escape Room v2", page_icon="🗝️")
st.title("🗝️ AI Escape Room - Version 2 (Reliable)")


def reset():
    st.session_state.state = engine.new_state()
    st.session_state.messages = [("assistant", engine.CONFIG["intro"])]


def play_turn(text):
    state = st.session_state.state
    raw = llm.parse_intent(text) or engine.parse_rule_based(text)   # LLM, else rules
    intent = engine.normalize_intent(raw, text)                      # never trust parser output
    result = engine.apply_action(state, intent)                      # Python decides
    st.session_state.messages.append(("user", text))
    st.session_state.messages.append(("assistant", llm.narrate(result["facts"])))  # LLM describes


if "state" not in st.session_state:
    reset()
state = st.session_state.state

with st.sidebar:
    st.header("Your journal")
    done = [label for label, ok in engine.progress(state) if ok]
    for label in done:
        st.write("✅ " + label)
    if not done:
        st.caption("Nothing accomplished yet.")
    st.write(f"🎒 Inventory: {', '.join(state['inventory']) or 'empty'}")
    st.write(f"🧭 Turns: {state['turns']}")
    left = engine.MAX_HINTS - state["hints_used"]
    if st.button(f"💡 Hint ({left} left)", disabled=left <= 0 or state["flags"]["escaped"]):
        play_turn("hint")
        st.rerun()
    if st.button("🔄 Restart game"):
        reset()
        st.rerun()
    st.caption("Try: *examine the desk*, *take the flashlight*, *try 1234 on the drawer*.")

for role, text in st.session_state.messages:
    st.chat_message(role).write(text)

if state["flags"]["escaped"]:
    st.success("🎉 You escaped! Press Restart to play again.")
elif prompt := st.chat_input("What do you do?"):
    play_turn(prompt)
    st.rerun()
