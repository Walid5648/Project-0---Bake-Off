"""Build auditable result tables from actual per-item records."""

from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path


def percentile(values: list[float], fraction: float) -> float:
    values = sorted(values)
    if not values:
        return 0.0
    index = (len(values) - 1) * fraction
    left = int(index)
    right = min(left + 1, len(values) - 1)
    return values[left] + (values[right] - values[left]) * (index - left)


def summarize(path: Path) -> Path:
    with path.open(newline="", encoding="utf-8") as source:
        rows = list(csv.DictReader(source))
    groups = defaultdict(list)
    for row in rows:
        groups[row["model"]].append(row)
    summaries = []
    for model, records in groups.items():
        latencies = [float(row["latency_ms"]) for row in records]
        correct = sum(row["correct"] == "1" for row in records)
        failures = Counter(row["status"] for row in records)
        generated = sum(int(row["output_tokens"] or 0) for row in records)
        seconds = sum(float(row["generation_ms"] or 0) / 1000 for row in records)
        summary = {"model": model, "n": len(records), "correct": correct,
                   "accuracy": round(correct / len(records), 4),
                   "p50_latency_ms": round(percentile(latencies, .5), 2),
                   "p95_latency_ms": round(percentile(latencies, .95), 2),
                   "mean_latency_ms": round(sum(latencies) / len(latencies), 2),
                   "generation_tokens_per_second": round(generated / seconds, 2) if seconds else "",
                   "api_charge_usd": 0}
        for status in ("wrong_result", "parse_error", "refusal", "request_timeout", "sql_timeout", "sql_error", "request_error", "truncated", "context_overflow"):
            summary[status] = failures[status]
        for difficulty in ("easy", "medium", "hard"):
            subset = [row for row in records if row["difficulty"] == difficulty]
            summary[difficulty + "_correct"] = sum(row["correct"] == "1" for row in subset)
            summary[difficulty + "_n"] = len(subset)
        summaries.append(summary)
    output = path.with_name("summary.csv")
    if summaries:
        with output.open("w", newline="", encoding="utf-8") as target:
            writer = csv.DictWriter(target, fieldnames=list(summaries[0]))
            writer.writeheader()
            writer.writerows(summaries)
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("per_item_csv", type=Path)
    print(summarize(parser.parse_args().per_item_csv))
