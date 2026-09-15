# Project 0: Bake-Off Postmortem

## 1. Token Starvation via "Chain-of-Thought" Bottleneck
**What went wrong:** 
During our initial evaluation, the local `gemma-4-12b-heretic-abliterated` model scored an unexpectedly low 21/50 (42%). A review of the raw outputs in `results/per_item.csv` revealed that on almost all medium and hard queries, the model returned an empty query (`;`) and the `output_tokens` counter hit exactly 256. 

**What we learned & how we fixed it:** 
The 12B model was defaulting to an internal reasoning mode. It consumed its entire 256-token budget generating invisible `<thought>` tags before it could output the `SELECT` statement. Because the project brief strictly forbids changing the `max_tokens` limit for a single model to ensure fair comparison, we could not simply increase the limit. Instead, we bypassed the issue by injecting `{%- set enable_thinking = false %}` into the model's Jinja prompt template in LM Studio. This forced raw instruction following. Upon re-running, the model stopped wasting compute on hidden tokens, mean latency dropped significantly, and accuracy jumped to 30/50 (60%).

## 2. Apple Metal GPU Out-of-Memory (OOM) Crash
**What went wrong:** 
Midway through the local benchmark, the inference server crashed completely, throwing a `kIOGPUCommandBufferCallbackErrorOutOfMemory` error, followed by repeated API "Channel Errors."

**What we learned & how we fixed it:** 
LM Studio was attempting to load the 12B Q6_K weights (~11GB) while simultaneously allocating maximum Key-Value (KV) cache for multiple parallel evaluation slots and a massive 8K context window. This exceeded the unified memory ceiling of the Mac hardware. We resolved this by ejecting the backend, restricting the server to a single concurrent slot, and lowering the context window to 2048 (well above our ~350 token prompt). The subsequent run completed seamlessly, teaching us the importance of manually tuning KV cache allocation on consumer hardware.

## 3. Evaluation Script Brittleness & SQLite Dialect
**What went wrong:** 
On Item 44, both the local model and the Gemini API triggered a `gold_sql_error` during the automated scoring phase. 

**What we learned & how we fixed it:** 
Our ground-truth query utilized an `INTERSECT` operator. We discovered that standard SQLite strictly enforces that `ORDER BY` clauses in compound queries must refer to simple column aliases, not table-qualified names (e.g., `ORDER BY Name ASC` instead of `ORDER BY Artist.Name ASC`). Our automated executor failed to parse the ground-truth syntax under its read-only URI wrapper. This highlighted that while automated scoring is highly efficient, it is also extremely brittle to minor SQLite dialect quirks and driver execution modes. We learned that rigorous testing of the ground-truth dataset in the exact programmatic environment (Python `sqlite3` module) is just as critical as testing the LLMs themselves.