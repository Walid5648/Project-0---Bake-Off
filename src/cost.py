import csv
import numpy as np

PER_ITEM_PATH = "results/per_item.csv"
SUMMARY_PATH = "results/summary.csv"

# Cost configurations (per 1M tokens)
# Gemini 3.1 Flash-Lite list prices:
API_INPUT_PRICE_PER_M = 0.25
API_OUTPUT_PRICE_PER_M = 1.50

# Local Hardware Cost Model (Macbook amortization + power)
# $2000 Mac over 3 years = $0.076/hr + 0.05 kW * $0.15/kWh ($0.0075/hr) = $0.0835/hr
HARDWARE_COST_PER_HOUR = 0.0835

def load_data():
    data = {}
    with open(PER_ITEM_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            model = row["model"]
            if model not in data:
                data[model] = []
            data[model].append({
                "item_id": int(row["item_id"]),
                "latency_ms": float(row["latency_ms"]),
                "is_correct": int(row["is_correct"]),
                "status": row["status"],
                "input_tokens": int(row["input_tokens"]),
                "output_tokens": int(row["output_tokens"]),
                "sql": row["output_sql"],
            })
    return data

def analyze():
    data = load_data()
    summary_rows = []

    print("\n" + "="*80)
    print("PROJECT 0: BAKE-OFF SUMMARY METRICS")
    print("="*80)

    for model, items in data.items():
        n = len(items)
        correct = sum(1 for x in items if x["is_correct"] == 1)
        syntax_err = sum(1 for x in items if x["status"] == "syntax_error")
        refusal_err = sum(1 for x in items if x["status"] == "refusal/timeout")
        gold_err = sum(1 for x in items if x["status"] == "gold_sql_error")
        incorrect = sum(1 for x in items if x["status"] == "incorrect_results")

        latencies = [x["latency_ms"] for x in items]
        p50 = np.percentile(latencies, 50)
        p95 = np.percentile(latencies, 95)
        mean_lat = np.mean(latencies)

        total_in_tokens = sum(x["input_tokens"] for x in items)
        total_out_tokens = sum(x["output_tokens"] for x in items)

        avg_in = total_in_tokens / n
        avg_out = total_out_tokens / n

        # Cost calculation
        if "gemini" in model.lower():
            # API pricing: (avg_in * price_in + avg_out * price_out) * 1000 / 1M
            cost_per_1k = ((avg_in * API_INPUT_PRICE_PER_M) + (avg_out * API_OUTPUT_PRICE_PER_M)) / 1000.0
            throughput = 1000.0 / (mean_lat / 1000.0) if mean_lat > 0 else 0
        else:
            # Self-hosted: Hardware hourly cost / requests per hour * 1000
            reqs_per_hour = 3600.0 / (mean_lat / 1000.0) if mean_lat > 0 else 1
            cost_per_1k = (HARDWARE_COST_PER_HOUR / reqs_per_hour) * 1000.0
            # Tokens per second generated:
            throughput = total_out_tokens / (sum(latencies) / 1000.0)

        cost_100x = cost_per_1k * 100

        summary_rows.append({
            "model": model,
            "accuracy": f"{correct}/{n}",
            "accuracy_pct": round((correct / n) * 100, 1),
            "syntax_errors": syntax_err,
            "refusals_timeouts": refusal_err,
            "incorrect_results": incorrect + gold_err,
            "p50_latency_ms": round(p50, 1),
            "p95_latency_ms": round(p95, 1),
            "mean_latency_ms": round(mean_lat, 1),
            "cost_per_1k_usd": round(cost_per_1k, 4),
            "cost_100x_usd": round(cost_100x, 2),
            "throughput": round(throughput, 2)
        })

    # Save to results/summary.csv
    with open(SUMMARY_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=summary_rows[0].keys())
        writer.writeheader()
        writer.writerows(summary_rows)

    # Print clean terminal report
    for row in summary_rows:
        print(f"\nModel: {row['model']}")
        print(f"  • Accuracy: {row['accuracy']} ({row['accuracy_pct']}%)")
        print(f"  • Errors: {row['syntax_errors']} syntax | {row['refusals_timeouts']} refusals/timeouts | {row['incorrect_results']} incorrect/gold")
        print(f"  • Latency: p50 = {row['p50_latency_ms']} ms | p95 = {row['p95_latency_ms']} ms (mean = {row['mean_latency_ms']} ms)")
        print(f"  • Cost / 1k Requests: ${row['cost_per_1k_usd']} (100x Traffic: ${row['cost_100x_usd']})")
        if "gemini" in row['model']:
            print(f"  • Throughput: {row['throughput']} req/sec")
        else:
            print(f"  • Throughput: {row['throughput']} tok/sec (Local generation)")

    print(f"\n✓ Successfully updated {SUMMARY_PATH}")

if __name__ == "__main__":
    analyze()