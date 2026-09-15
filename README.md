# Project 0: Bake-Off — Text-to-SQL (Chinook)
CS496 AI Engineering | Mediterranean Institute of Technology

An empirical benchmark evaluating natural language to SQLite translation on the Chinook database across three model tiers: an open-weights model run locally on consumer hardware, a low-cost cloud API model, and a flagship API model.

---

## Setup

Run the following single command from the project root to create the virtual environment, install dependencies, and initialize the SQLite database:

```bash
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && sqlite3 chinook.db < Chinook_Sqlite.sql
```

> **Note:** Ensure LM Studio is running locally on port 1234 with your local model loaded, and your Google AI Studio key is populated in `.env` as `GEMINI_API_KEY=your_key_here`.

---

## Run

Execute the end-to-end benchmark and cost analysis with this single command:

```bash
python src/run.py && python src/cost.py
```

---

## Results Table

Evaluated on 50 stratified test items (15 Easy, 20 Medium, 15 Hard) under identical decoding conditions (Temperature 0.0, max 256 output tokens).

| Model | Type | Accuracy ($n/50$) | Syntax Errors | Refusals / Timeouts | $p_{50}$ Latency (ms) | $p_{95}$ Latency (ms) | Cost / 1k Requests |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `gemma-4-12b-heretic-abliterated@q6_k` | Local (Apple Silicon) | 30 / 50 (60.0%) | 1 | 0 | 5,530.1 | 15,494.9 | $0.1537 |
| `gemini-3.1-flash-lite` | Cheap API | 30 / 50 (60.0%) | 2 | 0 | 1,974.4 | 3,865.9 | $0.1268 |
| *`[Top API Model — e.g., gemini-3.1-pro]`* | Top API | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* | *[Pending]* |

*Local hardware notes: Apple Silicon Mac (Unified Memory), LM Studio Metal backend, single concurrency slot, context capped at 2,048 tokens.*

---

## Contributions

* **[Teammate 1 Full Name] (Dataset Lead):** Authored the 50 stratified natural language query prompts, wrote ground-truth SQLite statements in `data/items.jsonl`, and co-authored `data/labeling_note.md`.
* **[Teammate 2 Full Name] (Local Inference & Hardware):** Configured and managed the local LM Studio runtime, debugged Apple Metal memory allocation/OOM crashes, tuned KV cache context limits, and produced `results/hardware_note.md`.
* **[Teammate 3 Full Name] (Pipeline & Scoring Architecture):** Implemented the execution client in `src/run.py`, built the read-only SQLite auto-grader in `src/score.py`, and handled Gemini API integration and response logging.
* **[Teammate 4 Full Name] (Cost Modeling & Analysis):** Developed `src/cost.py`, calculated $p_{50}/p_{95}$ latency distributions and hardware amortization metrics, and led the drafting of `report.pdf` and `postmortem.md`.