# Suggested commit sequence (make these as you actually work, over several sittings)

1. `chore: init repo with .gitignore, .env.example, requirements.txt`
2. `feat(v1): streamlit chat UI skeleton`
3. `feat(v1): gemini game master with library scenario prompt`
4. `feat(v1): restart button and win detection`
5. `docs: add v1 architecture diagram and observed v1 failures`
6. `feat(v2): add structured game state and config`
7. `feat(v2): action validation (examine/take/use/enter_code)`
8. `feat(v2): LLM intent parser with rule-based fallback`
9. `feat(v2): LLM narrator limited to engine facts + output guard`
10. `feat(v2): meta/injection filter and limited hints`
11. `test: add pytest suite for engine`
12. `docs: README, test cases, screenshots, report`

Commands: `git add <files>` then `git commit -m "<message>"` after each step; `git push` at the end of each session.
