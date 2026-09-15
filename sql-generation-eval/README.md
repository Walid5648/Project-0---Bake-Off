<<<<<<< HEAD
# Local SQL model bake-off

Compare **Qwen2.5-Coder 1.5B, 3B and 7B** on SQL generation against a reproducible
12-table retail database. All three models run locally through Ollama.

## Status

The database, 60 draft questions, read-only evaluator and benchmark runner are
implemented. Automated label checks do not replace two-person human review. Actual
model runs, final results and the two-page report are still pending.

## Database setup: one command

Requires Python 3.11+ with SQLite 3.37+; no pip dependencies are needed for the benchmark.

```powershell
python -m src.setup
```

This creates three local SQLite files under `data/databases/`, with 12 tables, 480
orders and 1,200 order lines each. Repeated setup verifies and reuses existing files.

## Managing the database

Install the optional [DB Browser for SQLite](https://sqlitebrowser.org/dl/) desktop
client and open **`data/databases/retail_a.sqlite`**. Browse tables, inspect the schema,
and use its Execute SQL tab. The benchmark itself requires only Python's built-in
SQLite support. The schema and business rules are in [docs/database.md](docs/database.md).

Built-in command-line inspection:

```powershell
python -m src.inspect_db
python -m src.inspect_db --sql "SELECT status, COUNT(*) AS orders FROM orders GROUP BY status"
```

List the complex questions or inspect an individual reference query and its results:

```powershell
python -m src.review --split test
python -m src.review --id test_26 --fixture retail_a
```

Save manual experiments in a scratch database. Benchmark input hashes detect edits;
rebuild generated fixtures with `python -m src.setup --force` after changing schema/seed.

## Local model setup

Install [Ollama for Windows](https://ollama.com/download/windows), start it, and download:

```powershell
ollama pull qwen2.5-coder:1.5b
ollama pull qwen2.5-coder:3b
ollama pull qwen2.5-coder:7b
```

Approximate download sizes are 986 MB, 1.9 GB and 4.7 GB. Only one model is loaded at
a time. The 7B model's GPU fit must be checked on the 6 GB RTX 3050. Settings are in
[config/models.json](config/models.json); all requests use a local-only endpoint.

## Run: one command

Start with development questions:

```powershell
python -m src.run
```

For a short development smoke test:

```powershell
python -m src.run --split dev --model qwen2.5-coder:1.5b --limit 2
```

After development, actual human label review and freezing the experiment:

```powershell
python -m src.run --split test
```

Every run gets its own timestamped directory under `results/runs/`, containing
`per_item.csv`, `summary.csv`, exact configuration/model/fixture metadata and each
raw response. One attempt per item; failures count as wrong. Generation timing
excludes SQLite grading. See [docs/experiment.md](docs/experiment.md).

## Validation

```powershell
python -m src.validate
python -m unittest discover -s tests -v
```

Validation checks database integrity, foreign keys, payment reconciliation, return
limits, item IDs/splits, reference execution and output shapes. Evaluator tests check
equivalent SQL, join multiplication, duplicate preservation, forbidden operations,
timeouts and numeric comparison.

## Results

No measured model results yet. Populate this table from the frozen run's CSV.

| Model | Correct / 50 | Accuracy | p50 latency | p95 latency | Generation tokens/s |
|---|---|---|---|---|---|
| Qwen2.5-Coder 1.5B | Pending | Pending | Pending | Pending | Pending |
| Qwen2.5-Coder 3B | Pending | Pending | Pending | Pending | Pending |
| Qwen2.5-Coder 7B | Pending | Pending | Pending | Pending | Pending |

Local API charges are zero; hardware/electricity and operator costs require explicit
assumptions. Run `python -m src.cost --help` for the local cost calculator. There is
no API/self-hosted break-even in this revised all-local comparison.

## Repository map

- `data/schema.sql`: relational schema and constraints.
- `data/items.jsonl`: 10 development and 50 draft test questions/reference queries.
- `data/labelling.md`: actual human-review procedure and provenance.
- `src/setup.py`, `src/seed.py`: reproducible fixture creation.
- `src/prompt.txt`, `src/run.py`: common prompt and local model experiment.
- `src/score.py`: automatic read-only SQL evaluator.
- `src/cost.py`, `src/summarize.py`: cost assumptions and result tables.
- `docs/database.md`: entity diagram, business definitions and GUI workflow.
- `docs/experiment.md`: fair-comparison protocol and limitations.
- `results/hardware.md`: observed hardware and unresolved runtime checks.

## Contributions

Add one entry per actual team member before submission. Do not invent names or work.
The initial code and draft question catalog were created with Codex assistance and
must be understood and reviewed by the submitting team.

>>>>>>> d2bbe181143e3a761f2b531fe2fff3a824d7075d
