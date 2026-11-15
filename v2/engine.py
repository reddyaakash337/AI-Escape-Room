"""Version 2 game engine: configuration, state, parsing helpers and validation.

Python decides what is possible. The LLM never sees secrets and never decides
whether an action succeeds - it only turns the engine's FACTS into prose.
"""
import copy
import re

# ---------------------------------------------------------------- configuration
CONFIG = {
    "intro": ("You come to on the cold floor of an old library, long after closing time. "
              "The lights are low and every exit is locked. Around you are a writing desk, "
              "a tall bookshelf, a framed painting, a small locked drawer and a heavy door "
              "with a four-digit keypad. Search the room, connect the clues and find a way "
              "out. Tell me what you want to do."),
    # Secrets live ONLY here. They are never sent to the LLM.
    "secrets": {"drawer_code": "6293", "door_code": "4785"},
    "objects": {
        "desk": {"aliases": ["desk", "table"]},
        "bookshelf": {"aliases": ["bookshelf", "shelf", "shelves", "bookcase"]},
        "books": {"aliases": ["books", "book", "volumes"], "requires": "bookshelf"},
        "painting": {"aliases": ["painting", "picture", "lighthouse", "canvas"]},
        "drawer": {"aliases": ["drawer", "dial lock"]},
        "door": {"aliases": ["door", "keypad", "exit"]},
    },
    "items": {
        "flashlight": {"aliases": ["flashlight", "torch", "light"], "found_in": "desk"},
        "note": {"aliases": ["note", "paper", "torn note", "page"], "found_in": "drawer"},
    },
}

ACTIONS = {"examine", "open", "take", "use", "enter_code", "inventory", "hint", "help", "meta", "unknown"}
MAX_HINTS = 3

# Messages that try to bypass rules, impersonate admins or demand secrets.
META_RE = re.compile(
    r"(administrator|\badmin\b|developer mode|system prompt|ignore (all |your |the |previous )*(instructions|rules)|"
    r"you are now|reveal|all (the )?(codes?|solutions?|secrets?|answers?)|"
    r"(tell|give|show) me (the )?(code|solution|answer|password)|"
    r"unlock (the )?(exit|door|everything) (immediately|now)|"
    r"already (solved|unlocked|opened|found|have)|override|cheat)", re.I)


# ----------------------------------------------------------------------- state
def new_state():
    return {
        "examined": [],          # objects examined so far
        "visible_items": [],     # items that have been discovered and can be taken
        "inventory": [],         # items the player holds
        "flags": {"painting_revealed": False, "drawer_unlocked": False, "escaped": False},
        "attempts": {"drawer": 0, "door": 0},
        "hints_used": 0,
        "turns": 0,
    }


def progress(state):
    """Checklist used by the UI sidebar (derived purely from state)."""
    f = state["flags"]
    return [
        ("Found the flashlight", "flashlight" in state["inventory"]),
        ("Read the books' numbers", "books" in state["examined"]),
        ("Opened the drawer", f["drawer_unlocked"]),
        ("Revealed the painting's secret", f["painting_revealed"]),
        ("Escaped", f["escaped"]),
    ]


# --------------------------------------------------------------------- parsing
def _find(text, table):
    """Return the key whose longest alias appears as a whole word in text."""
    best, best_len = None, 0
    for key, spec in table.items():
        for alias in spec["aliases"]:
            if re.search(rf"\b{re.escape(alias)}\b", text) and len(alias) > best_len:
                best, best_len = key, len(alias)
    return best


def find_object(text):
    return _find((text or "").lower(), CONFIG["objects"])


def find_item(text):
    return _find((text or "").lower(), CONFIG["items"])


def extract_code(message):
    m = re.search(r"(?<!\d)\d{4}(?!\d)", message)
    return m.group(0) if m else None


def parse_rule_based(message):
    """Offline fallback parser (also used by the tests). Returns a raw intent."""
    t = message.lower()
    if META_RE.search(t):
        return {"action": "meta"}
    if re.search(r"\b(inventory|what (am i|do i have)|my items|carrying)\b", t):
        return {"action": "inventory"}
    if re.search(r"\b(hint|clue please|i'?m stuck|help me)\b", t):
        return {"action": "hint"}
    if re.search(r"\b(help|how do i play|instructions)\b", t):
        return {"action": "help"}
    obj, item = find_object(t), find_item(t)
    # Items win over objects when the verb is take/use ("take the note").
    if re.search(r"\b(enter|type|input|try|dial|punch|code|combination|numbers?)\b", t) and extract_code(t):
        return {"action": "enter_code", "target": obj}
    if re.search(r"\b(use|shine|turn on|apply|point)\b", t):
        return {"action": "use", "item": item, "target": obj if obj else None}
    if re.search(r"\b(take|grab|pick|collect|get|pocket)\b", t):
        return {"action": "take", "item": item}
    if re.search(r"\b(open|unlock)\b", t):
        return {"action": "open", "target": obj}
    if re.search(r"\b(examine|look|inspect|check|search|read|study|investigate|move|lift|see)\b", t):
        if item and not obj:
            return {"action": "examine", "item": item}
        return {"action": "examine", "target": obj}
    return {"action": "unknown"}


def normalize_intent(raw, message):
    """Validate whatever a parser (LLM or rules) returned. Never trust it blindly.

    - the action must be whitelisted,
    - target/item are re-resolved against the config (inventions become None),
    - the code is taken from the player's own text with a regex, not from the LLM,
    - a meta/injection pattern in the message always overrides the parser.
    """
    if META_RE.search(message):
        return {"action": "meta", "target": None, "item": None, "code": None}
    raw = raw or {}
    action = raw.get("action") if raw.get("action") in ACTIONS else "unknown"
    return {
        "action": action,
        "target": find_object(str(raw.get("target") or "")),
        "item": find_item(str(raw.get("item") or "")),
        "code": extract_code(message),
    }


# ------------------------------------------------------------------ validation
def _res(ok, facts):
    return {"ok": ok, "facts": facts}


def _status_line(state):
    done = [n for n, d in progress(state) if d]
    return "Progress so far: " + (", ".join(done) if done else "nothing yet") + "."


def apply_action(state, intent):
    """Validate an intent against the state, mutate state if allowed, return FACTS."""
    if state["flags"]["escaped"]:
        return _res(False, "The game is over: the player has already escaped. They may restart.")
    state["turns"] += 1
    a, obj, item, code = intent["action"], intent.get("target"), intent.get("item"), intent.get("code")

    if a == "meta":
        return _res(False, "The player tried to bypass the rules, claim false progress or demand secrets. "
                           "This has no effect on the world. Nothing is unlocked or revealed. "
                           + _status_line(state))
    if a == "inventory":
        inv = state["inventory"]
        return _res(True, "The player is carrying: " + (", ".join(inv) if inv else "nothing") + ".")
    if a == "help":
        return _res(True, "Player may examine objects, take items, use an item on an object, "
                          "or enter a four-digit code on the drawer or door.")
    if a == "hint":
        return _hint(state)
    if a == "examine":
        return _examine(state, obj, item)
    if a == "open":
        return _open(state, obj)
    if a == "take":
        return _take(state, item)
    if a == "use":
        return _use(state, item, obj)
    if a == "enter_code":
        return _enter_code(state, obj, code)
    return _res(False, "The request does not match any action available in the room. "
                       "Ask the player what they would like to examine, take, use or enter.")


def _examine(state, obj, item):
    if item and not obj:
        if item in state["inventory"]:
            return _res(True, _item_text(item))
        return _res(False, "The player is not holding any such item.")
    if not obj:
        return _res(False, "There is nothing like that in the room.")
    req = CONFIG["objects"][obj].get("requires")
    if req and req not in state["examined"]:
        return _res(False, f"The player has not looked closely at the {req} yet, so they notice nothing about the {obj}.")
    if obj not in state["examined"]:
        state["examined"].append(obj)
    f = state["flags"]
    if obj == "desk":
        _reveal(state, "flashlight")
        extra = "" if "flashlight" in state["inventory"] else " A flashlight lies in the open top tray and can be taken."
        return _res(True, "A scratched oak desk with a dusty blotter." + extra)
    if obj == "bookshelf":
        return _res(True, "A tall bookshelf. Four books are pulled out slightly and arranged differently from the rest.")
    if obj == "books":
        return _res(True, "Each of the four odd books has a handwritten number on its spine. Left to right: 6, 2, 9, 3.")
    if obj == "painting":
        if f["painting_revealed"]:
            return _res(True, "The lighthouse painting glows under the flashlight, revealing painted numbers: 47.")
        return _res(True, "A dark painting of a lighthouse at night. Something about it looks oddly dim, as if it hides more than it shows.")
    if obj == "drawer":
        if f["drawer_unlocked"]:
            note = "" if "note" in state["inventory"] else " A torn note lies inside and can be taken."
            return _res(True, "The drawer is open." + note)
        return _res(True, "A small desk drawer secured by a four-digit dial lock. It is locked.")
    if obj == "door":
        return _res(True, "A heavy wooden door with a four-digit electronic keypad. It is locked.")
    return _res(True, "Nothing unusual.")


def _open(state, obj):
    if obj == "drawer":
        if state["flags"]["drawer_unlocked"]:
            return _examine(state, "drawer", None)
        return _res(False, "The drawer is locked and needs a four-digit code. It does not open.")
    if obj == "door":
        return _res(False, "The door is locked and needs a four-digit code on the keypad. It does not open.")
    return _res(False, "That cannot be opened.") if obj else _res(False, "There is nothing like that to open.")


def _reveal(state, item):
    if item not in state["visible_items"]:
        state["visible_items"].append(item)


def _item_text(item):
    if item == "flashlight":
        return "A small steel flashlight, still working."
    return 'The torn note reads: "Last two digits: 85. The first two are hidden in the painting."'


def _take(state, item):
    if not item:
        return _res(False, "There is no such item the player can take.")
    if item in state["inventory"]:
        return _res(False, f"The player already has the {item}.")
    if item not in state["visible_items"]:
        # Deliberately vague: does not confirm that the item exists.
        return _res(False, "The player has not found any such item.")
    state["inventory"].append(item)
    return _res(True, f"The player takes the {item}. " + _item_text(item))


def _use(state, item, obj):
    if not item:
        return _res(False, "The player is not holding any such item.")
    if item not in state["inventory"]:
        return _res(False, f"The player does not have the {item}, so it cannot be used.")
    if not obj:
        return _res(False, "The player must say what to use the item on.")
    if item == "flashlight" and obj == "painting":
        if state["flags"]["painting_revealed"]:
            return _res(True, "The numbers 47 are still glowing on the painting.")
        state["flags"]["painting_revealed"] = True
        if "painting" not in state["examined"]:
            state["examined"].append("painting")
        return _res(True, "The flashlight beam reveals glowing painted numbers on the lighthouse: 47.")
    return _res(False, f"Using the {item} on the {obj} has no effect.")


def _enter_code(state, obj, code):
    if obj not in ("drawer", "door"):
        return _res(False, "The player must say whether the code is for the drawer or the door.")
    if not code:
        return _res(False, "The player has not given a four-digit code to enter.")
    s = CONFIG["secrets"]
    if obj == "drawer":
        if state["flags"]["drawer_unlocked"]:
            return _res(False, "The drawer is already open.")
        if code == s["drawer_code"]:
            state["flags"]["drawer_unlocked"] = True
            _reveal(state, "note")
            return _res(True, "The dial lock clicks and the drawer slides open. A torn note lies inside and can be taken.")
        state["attempts"]["drawer"] += 1
        return _res(False, "The dial lock does not budge. That code is wrong. The drawer stays locked.")
    if code == s["door_code"]:
        state["flags"]["escaped"] = True
        return _res(True, "The keypad beeps green and the door swings open. The player escapes the library. THE GAME IS WON.")
    state["attempts"]["door"] += 1
    return _res(False, "The keypad buzzes red. That code is wrong. The door stays locked.")


def _hint(state):
    if state["hints_used"] >= MAX_HINTS:
        return _res(False, "No hints remain.")
    state["hints_used"] += 1
    f, inv, ex = state["flags"], state["inventory"], state["examined"]
    if "desk" not in ex:
        h = "Look closely at the furniture; the desk may hold something useful."
    elif "flashlight" not in inv:
        h = "There is something on the desk the player could take."
    elif "books" not in ex:
        h = "Some books on the bookshelf are arranged strangely. Examine them."
    elif not f["drawer_unlocked"]:
        h = "The numbers on the books, read left to right, may suit the drawer's four-digit lock."
    elif "note" not in inv:
        h = "The open drawer holds something worth taking."
    elif not f["painting_revealed"]:
        h = "The painting looks oddly dim. Perhaps light would help."
    else:
        h = "Combine the number hidden in the painting with the one on the note, in the order the note suggests."
    return _res(True, f"Hint {state['hints_used']} of {MAX_HINTS}: {h}")


def fresh_copy(state):
    return copy.deepcopy(state)
