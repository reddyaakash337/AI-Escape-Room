# Report - AI-Powered Escape Room (≈2 pages)

## 1. Design
The game takes place in a locked library with six interactive things (desk, bookshelf, books, painting, drawer, door) and two items (flashlight, note). The solution chain: the desk holds a **flashlight**; the bookshelf's four odd books show **4-1-7-2**, the drawer code; the drawer holds a **note** saying the last two door digits are **31** and the first two are in the painting; the **flashlight** reveals **58** on the painting; the door code is **5831**. That gives three puzzles plus a final escape challenge. Stack: Python, Streamlit, Google Gemini (free tier), pytest.

## 2. Version 1
V1 puts the whole scenario, including the solutions, into a system prompt. Gemini acts as Game Master, and the chat history is the only memory. A `[ESCAPED]` token tells the app the player won. This works well for cooperative play, is under 100 lines, and produces engaging narration.

**Problems:** (a) state is implicit, so the model can forget or contradict earlier events; (b) it may invent objects or accept actions that should be impossible; (c) solutions sit in the prompt, so they can be leaked early or extracted; (d) victory depends on the model emitting a token, so it can be tricked or wrong; (e) results differ run to run, which makes testing hard. (Fill in your own observations from docs/test-cases.md.)

## 3. Version 2
V2 separates *deciding* from *describing*. `engine.py` stores the secrets and a structured state dictionary (examined objects, discoverable items, inventory, flags, attempts, hints). Each turn: (1) Gemini parses the player's text into a JSON intent; (2) Python validates it (action whitelist, targets re-resolved against config, the code extracted by regex from the player's own words, and a META filter that overrides the parser for admin/jailbreak/secret-demand patterns); (3) the engine applies rules and returns FACTS; (4) Gemini narrates only those FACTS; (5) an output guard rejects narration containing numbers absent from the facts. If the API fails, a rule-based parser and plain facts keep the game running. Victory is a boolean set only by the engine.

## 4. Why it is more reliable
- **Memory:** flags and inventory are data, so they cannot be forgotten.
- **Invalid actions:** uncollected items, undiscovered items, wrong codes and nonexistent objects are rejected by code.
- **Adversarial prompts:** the LLM never sees secrets, so persuading it cannot reveal them, and it cannot change state, since only `apply_action` can.
- **Testability:** 14 deterministic tests run offline.

## 5. Problems encountered and limitations
Balancing flexibility with control was the main tension: the stricter the parser, the less natural the game feels. Regex-based meta detection is a heuristic and can false-positive (e.g. a player saying "I already have the note"). Free-form creative actions are not supported. Free-tier rate limits require the fallbacks. Possible future work: LLM-based injection classifier, multiple rooms, persistent saves, a timer.
