# Experiment protocol

## Question

How do Qwen2.5-Coder 1.5B, 3B and 7B differ in execution accuracy, response latency,
and memory use on the same laptop when generating SQL over a 12-table schema?
All are local instruction models, with Q4_K_M quantization. The project scope was
revised from the original PDF to use three local models without hosted API models.

## Runtime

Ollama loads and serves the model. Python sends one request with a complete schema,
business rules, and question, then receives SQL text. SQLite executes the SQL; the
Python scorer compares returned tables. Model generation never receives the reference
SQL, expected results, prior questions, database rows, or execution feedback.

Use the same Ollama version and `config/models.json` for all three models. Their
exact installed digests, model metadata/templates, runtime options and GPU placement
are recorded in each run's `metadata.json`. The same explicit system instruction
overrides model-default system instructions.

## Development and final evaluation

1. Build all fixtures and pass automated validation and evaluator tests.
2. Review the 10 development questions and exercise the runtime on them.
3. Check prompt lengths, generation limits, model residency and reasonable timeouts.
   The initial common budget is 4096 context tokens and 1024 output tokens; adjust
   all models together during development if the full schema needs more space.
4. Obtain two independent human reviews of every label, correcting source data and
   reference answers where required. Set `review_status` and `reviewers` accurately.
5. Freeze the final 50 questions, reference answers, three fixtures, prompt, parser,
   model artifacts and settings before inspecting final model results.
6. Run all 50 questions on each model, in the same order and one request at a time.
7. Derive the summary from the resulting CSV and analyze actual wrong answers.

The current catalog is an AI-authored draft, with 8 easy, 16 medium and 26 hard test
questions. It is **not human-verified**. Runs before review are marked provisional.
Reference execution establishes syntactic and operational validity, not an independent
proof that the gold answer matches the natural-language question.

## Scoring

- One model call per item; no retries, repair prompts, output edits, retrieval, or agents.
- The shared parser accepts raw SQL or one complete `sql`/`sqlite` Markdown fence.
  It removes only surrounding whitespace and that fence; it never edits query logic.
- Execute the answer once per fixture under the same read-only restrictions.
- An item is correct only when every fixture matches its reference result.
- Output aliases are ignored; column position/count, strings, NULLs and duplicate
  counts matter. Requested row order matters. The one unordered duplicate-preservation
  item uses multiset comparison, not set comparison.
- Ordered numeric outputs use absolute tolerance 0.000001; integers are compared
  exactly. Decimal-valued questions are ordered, avoiding approximate multiset matching.
- SQLite authorization permits SELECT/CTEs and an explicit set of normal SQL
  functions; writes, attachments, PRAGMAs, extension loading and metadata reads are
  rejected. Queries have a progress deadline, result-row cap and SQLite size limits.
- Wrong rows, SQL errors, timeouts, empty responses, refusals and truncation count
  as wrong. Raw answers and detailed fixture verdicts are retained.
- Automatic refusal tagging recognizes a conservative set of English prefixes; other
  non-SQL refusals may fall under SQL errors. They still count as wrong and remain
  available for inspection. This classification is not an LLM-based judge.

## Timing and memory

Warm up each model once outside the scored dataset and keep it loaded for its run.
Only one model is loaded at a time; no chat history is sent. Measure client wall time
from request dispatch through receipt of the full answer. SQL grading is outside
this interval. Include failed attempts in the latency distribution and retain failure
counts alongside it. Percentiles use linear interpolation on sorted latencies.

Ollama's load duration and generation duration are recorded separately. Generation
tokens/second is total generated tokens divided by total generation seconds. Prompt
cache counters are saved when exposed; warm model memory is distinct from prompt
prefix caching. The runtime's native prefix-cache behavior is retained consistently.

Keep the laptop plugged in, use one power mode, and close GPU-heavy applications.
GPU name, memory, temperature and power snapshots are recorded when nvidia-smi is
available. Ollama's resident model GPU allocation is recorded; it is not a sampled
peak VRAM measurement. A model partially on CPU must be labeled as such: its latency
measures this deployment, not a pure parameter-count effect.

## Cost and reporting

API charges are zero. Local compute is not automatically free. `src/cost.py` accepts
explicit hardware-per-hour, estimated/measured power, electricity and operator-time
assumptions. It projects baseline and 100x volume, reports required busy hours, and
flags when 100x demand exceeds a 720-hour month on one sequential worker. It does
not invent power measurements or an API/self-hosted break-even for an all-local study.

Each run retains `per_item.csv`, `summary.csv`, `metadata.json`, and raw JSON responses.
After the frozen run, copy its selected CSVs into `results/` and write the two-page
report, three genuine wrong answers per model (or explicitly fewer if fewer exist),
and an honest postmortem. No model results or report conclusions exist yet.
