# Architecture

## Version 1 - LLM does everything
```mermaid
flowchart LR
    P[Player] -->|natural language| UI[Streamlit chat UI]
    UI -->|message| CH[Gemini chat session<br/>history = only memory]
    SP[System prompt<br/>room + puzzles + SOLUTIONS] --> CH
    CH -->|narration + ESCAPED token| UI
    UI --> P
```
State, rules, secrets and win detection all live inside the LLM's context.

## Version 2 - Python decides, LLM describes
```mermaid
flowchart LR
    P[Player] --> UI[Streamlit UI + sidebar]
    UI -->|text| IP[LLM intent parser<br/>JSON output only]
    IP -->|raw intent| N[normalize_intent<br/>whitelist + META filter + regex code]
    RB[Rule-based parser<br/>fallback] -.-> N
    N -->|validated intent| E[Engine: apply_action]
    CFG[(CONFIG: secrets, objects, items)] --> E
    ST[(Game state dict)] <--> E
    E -->|FACTS only, no secrets| NA[LLM narrator]
    NA --> G[Output guard<br/>no numbers absent from facts]
    G --> UI
    ST --> UI
```
Key idea: secrets and state never enter an LLM prompt. The LLM sees the player's text (parser) and a short FACTS string (narrator).
