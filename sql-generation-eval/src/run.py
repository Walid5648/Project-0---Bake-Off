"""Run the local SQL benchmark, saving every response and failure without retries."""

from __future__ import annotations

import argparse
import csv
import json
import platform
import re
import socket
import sqlite3
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError

from .common import DATA, DATABASES, FIXTURES, ROOT, dump_json, file_hash, read_items
from .ollama_client import OllamaClient
from .score import ParseError, grade, parse_sql
from .summarize import summarize
from .validate import validate


def render_prompt(item: dict) -> str:
    schema = (DATA / "schema.sql").read_text(encoding="utf-8")
    # Indexes and the connection PRAGMA are operational details, not task information.
    schema = re.sub(r"CREATE INDEX[^;]+;", "", schema)
    schema = schema.replace("PRAGMA foreign_keys = ON;", "").strip()
    return (ROOT / "src/prompt.txt").read_text(encoding="utf-8").format(schema=schema, question=item["question"])


def hardware_snapshot() -> dict:
    snapshot = {"platform": platform.platform(), "python": platform.python_version(), "sqlite": sqlite3.sqlite_version}
    try:
        result = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total,memory.used,temperature.gpu,power.draw", "--format=csv,noheader"],
                                capture_output=True, text=True, timeout=10)
        snapshot["gpu"] = result.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        snapshot["gpu"] = "nvidia-smi unavailable"
    return snapshot


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=("dev", "test"), default="dev")
    parser.add_argument("--model", action="append", help="Run selected configured model(s); default: all three")
    parser.add_argument("--limit", type=int, help="Development smoke test only")
    parser.add_argument("--config", type=Path, default=ROOT / "config/models.json")
    parser.add_argument("--output-root", type=Path, default=ROOT / "results/runs", help="Parent directory for timestamped run artifacts")
    args = parser.parse_args()
    if args.limit is not None and (args.split != "dev" or args.limit <= 0):
        parser.error("--limit must be positive and may only be used with --split dev")
    validation = validate(verbose=False)
    config = json.loads(args.config.read_text(encoding="utf-8"))
    models = args.model or config["models"]
    if len(set(models)) != len(models) or any(model not in config["models"] for model in models):
        parser.error("Choose distinct models from config/models.json")
    client = OllamaClient(config["base_url"], config["request_timeout_seconds"])
    try:
        version = client.request("/api/version")
        installed = client.request("/api/tags")["models"]
        loaded = client.request("/api/ps")["models"]
    except (URLError, OSError) as error:
        raise SystemExit("Ollama is unavailable. Install/start Ollama, then pull the three models listed in config/models.json.") from error
    available = {model["name"]: model for model in installed}
    missing = [model for model in models if model not in available]
    if missing:
        raise SystemExit("Missing local models: " + ", ".join(missing) + ". Download them with ollama pull <model>.")
    unrelated = [model["name"] for model in loaded if model["name"] not in config["models"]]
    if unrelated:
        raise SystemExit("Other Ollama models are currently loaded: " + ", ".join(unrelated) + ". Stop them before the benchmark to avoid GPU contention.")
    items = read_items(args.split)
    if args.limit:
        items = items[:args.limit]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    output = args.output_root / f"{stamp}_{args.split}"
    output.mkdir(parents=True)
    (output / "raw").mkdir()
    hashes = {name: file_hash(ROOT / name) for name in ("data/items.jsonl", "data/schema.sql", "src/prompt.txt", "src/run.py", "src/score.py", "src/ollama_client.py")}
    metadata = {"started_utc": stamp, "status": "running", "split": args.split,
                "provisional": validation["awaiting_two_human_reviews"] > 0 or bool(args.limit),
                "items": [item["id"] for item in items], "config": config, "models": models,
                "model_details": {model: available[model] for model in models},
                "ollama_version": version, "hardware_before": hardware_snapshot(), "input_hashes": hashes,
                "fixtures": json.loads((DATABASES / "manifest.json").read_text()),
                "loaded_models": {}, "warmups": {}, "failure_policy": "One attempt per item; every failure counts as wrong",
                "timing_policy": "Client wall time from sending request to complete non-streaming response; warm-up excluded; SQL grading excluded; prompt-cache behavior recorded when exposed"}
    dump_json(output / "metadata.json", metadata)
    columns = ["model", "item_id", "split", "difficulty", "skill", "correct", "status", "latency_ms", "input_tokens", "cached_input_tokens", "output_tokens", "generation_ms", "load_ms", "gpu_memory_bytes", "raw_file"]
    per_item = output / "per_item.csv"
    print(f"Saving actual run records to {output}", flush=True)
    try:
        with per_item.open("w", encoding="utf-8", newline="") as target:
            writer = csv.DictWriter(target, fieldnames=columns)
            writer.writeheader()
            for previous in loaded:
                client.unload(previous["name"])
            for model in models:
                slug = model.replace(":", "_").replace("/", "_")
                print(f"Loading and warming {model}", flush=True)
                details = client.request("/api/show", {"model": model})
                if details.get("remote_model") or details.get("remote_host"):
                    raise ValueError("Cloud-backed model rejected; only locally executed models are allowed")
                metadata["model_details"][model]["show"] = details
                warmup = client.generate(model, "Write only the SQLite query SELECT 1;", config["options"])
                metadata["warmups"][model] = warmup
                resident = client.request("/api/ps")["models"]
                metadata["loaded_models"][model] = resident
                model_state = next((state for state in resident if state["name"] == model), {})
                dump_json(output / "metadata.json", metadata)
                for number, item in enumerate(items, 1):
                    prompt = render_prompt(item)
                    raw = {"model": model, "item_id": item["id"], "prompt": prompt, "response": None}
                    row = {key: "" for key in columns}
                    row.update(model=model, item_id=item["id"], split=args.split, difficulty=item["difficulty"], skill=item["skill"], correct=0,
                               gpu_memory_bytes=model_state.get("size_vram", ""))
                    start = time.perf_counter()
                    response = None
                    try:
                        response = client.generate(model, prompt, config["options"])
                    except (URLError, OSError, ValueError) as error:
                        timeout = isinstance(error, (TimeoutError, socket.timeout)) or isinstance(getattr(error, "reason", None), (TimeoutError, socket.timeout))
                        row["status"] = "request_timeout" if timeout else "request_error"
                        raw["error"] = str(error)
                    row["latency_ms"] = round((time.perf_counter() - start) * 1000, 3)
                    if response is not None:
                        raw["response"] = response
                        row.update(input_tokens=response.get("prompt_eval_count", ""), cached_input_tokens=response.get("prompt_eval_cached_count", ""),
                                   output_tokens=response.get("eval_count", ""), generation_ms=response.get("eval_duration", 0) / 1e6,
                                   load_ms=response.get("load_duration", 0) / 1e6)
                        answer = response.get("response", "")
                        if response.get("error") or not response.get("done"):
                            row["status"] = "request_error"
                        elif response.get("done_reason") == "length":
                            row["status"] = "truncated"
                        elif response.get("prompt_eval_count", 0) + config["options"]["num_predict"] > config["options"]["num_ctx"]:
                            row["status"] = "context_overflow"
                        elif re.match(r"(?is)^\s*(?:sorry[, ]|i\s+(?:cannot|can't|am unable|won't))", answer):
                            row["status"] = "refusal"
                        else:
                            try:
                                sql = parse_sql(answer)
                                raw["parsed_sql"] = sql
                                verdict = grade(sql, item, [DATABASES / f"{name}.sqlite" for name in FIXTURES])
                                raw["grading"] = verdict
                                row["status"] = verdict["status"]
                                row["correct"] = int(verdict["correct"])
                            except ParseError as error:
                                row["status"] = "parse_error"
                                raw["error"] = str(error)
                    raw_path = output / "raw" / f"{slug}_{item['id']}.json"
                    dump_json(raw_path, raw)
                    row["raw_file"] = str(raw_path.relative_to(output))
                    writer.writerow(row)
                    target.flush()
                    print(f"{model} {number}/{len(items)} {item['id']}: {row['status']} ({row['latency_ms']} ms)", flush=True)
                client.unload(model)
        metadata["status"] = "complete"
    except BaseException as error:
        metadata["status"] = "interrupted" if isinstance(error, KeyboardInterrupt) else "failed"
        metadata["error"] = str(error)
        raise
    finally:
        try:
            for state in client.request("/api/ps")["models"]:
                if state["name"] in models:
                    client.unload(state["name"])
        except (URLError, OSError, ValueError):
            pass
        metadata["hardware_after"] = hardware_snapshot()
        for name, original_hash in hashes.items():
            if file_hash(ROOT / name) != original_hash:
                metadata["status"] = "invalid_inputs_changed"
        dump_json(output / "metadata.json", metadata)
        if per_item.exists():
            summarize(per_item)
    print(f"Finished. Results: {output}", flush=True)


if __name__ == "__main__":
    main()
