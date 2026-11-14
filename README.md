# Sports Tournament Manager Agent

An LLM-powered agent that manages a sports tournament: it adds and withdraws
teams, generates a round-robin schedule, checks for conflicts, records results
and shows standings. It chooses and runs tools itself, plans multi-step tasks,
remembers user preferences, and adapts to user feedback.

## Features
- 8 tools: add_team, withdraw_team, generate_schedule, find_conflicts,
  record_result, standings, list_matches, avoid_weekday
- Multi-step workflows (for example: list matches, then record a result,
  then check conflicts and standings)
- Persistent memory (`memory.json`): avoided weekdays, courts, times, days
- Reflection: after scheduling, the agent runs a conflict check on its own
  output and advises when matches could not be placed
- Feedback adaptation: if the last 5 user ratings average below 3, the prompt
  asks the agent to explain steps and confirm details
- Guardrails: input blocklist and length limit, human confirmation before
  withdrawing a team
- Tracing: every tool call, reply and rating is logged to `trace.jsonl`

## Requirements
- Python 3.11+ [CHECK: run `python --version`]
- [Ollama](https://ollama.com) with the `qwen2.5:3b` model

## Setup
```
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
ollama pull qwen2.5:3b
```
Make sure Ollama is running (`ollama list` should work; otherwise run
`ollama serve`).

## Run
Command line:
```
python agent.py
```
Web app (Streamlit):
```
streamlit run app.py
```
Then open http://localhost:8501.

## Evaluation
Close Streamlit first so Ollama is not shared, then run:
```
python eval.py
```
It runs 23 test cases and prints a summary (task success rate, tool-selection
accuracy, safety block rate, average latency). Per-case results are saved to
`results.csv`. Recorded runs: `before.txt` (before adding `list_matches` and
`avoid_weekday`) and `after.txt` (after).

| Metric | Before | After |
|---|---|---|
| Task success | 17/23 (74%) | 22/23 (96%) |
| Tool-selection accuracy | 11/17 (65%) | 16/17 (94%) |
| Safety block rate | 4/4 | 4/4 |
| Average latency | 9.2 s | 18.6 s |

Results come from single runs with a small local model and may vary.

## Project structure
| File | Purpose |
|---|---|
| `agent.py` | Agent: tools, system prompt, guardrails, memory, feedback, CLI loop |
| `tools.py` | Database logic behind the tools (SQLite) [CHECK] |
| `app.py` | Streamlit interface |
| `eval.py` | Evaluation script (23 test cases) |
| `test_tools.py` | Tests for the database tools |
| `memory.json` | Persistent preferences |
| `trace.jsonl` | Log of tool calls, replies and ratings |
| `results.csv` | Latest evaluation results |
| `before.txt`, `after.txt` | Recorded evaluation outputs |

## Known limitations
- A 3B local model sometimes fails to pick a tool (case `list_2` still fails).
- The input blocklist is a simple substring check and can be bypassed.
- No automatic retries when a tool fails.
- Evaluation is a small suite run once per version.

## Acknowledgements
Built with LangChain / LangGraph, Ollama (qwen2.5:3b) and Streamlit.
AI coding assistants were used during development; all code was reviewed
and tested by the author.