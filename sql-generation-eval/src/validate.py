"""Validate fixture integrity and draft reference queries; never calls an LLM."""

from __future__ import annotations

import json
import sqlite3
from collections import Counter

from .common import DATA, DATABASES, FIXTURES, ROOT, file_hash, read_items
from .score import TABLES, execute_sql


def validate(verbose: bool = True) -> dict:
    manifest = json.loads((DATABASES / "manifest.json").read_text(encoding="utf-8"))
    for relative, expected in manifest["sources"].items():
        if file_hash(ROOT / relative) != expected:
            raise ValueError(f"Fixture source changed: {relative}. Rebuild with python -m src.setup --force")
    for name in FIXTURES:
        path = DATABASES / f"{name}.sqlite"
        if file_hash(path) != manifest["fixtures"][name]["sha256"]:
            raise ValueError(f"Fixture changed: {name}; rebuild before benchmarking")
        with sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True) as connection:
            assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
            assert not connection.execute("PRAGMA foreign_key_check").fetchall()
            assert set(row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")) == TABLES
            assert not connection.execute("""
                SELECT ri.order_item_id FROM return_items ri JOIN returns r ON r.return_id=ri.return_id
                JOIN order_items oi ON oi.order_item_id=ri.order_item_id
                WHERE r.status='approved' GROUP BY ri.order_item_id
                HAVING SUM(ri.quantity)>MAX(oi.quantity)
                    OR SUM(ri.refund_cents)>MAX(oi.quantity*oi.unit_price_cents-oi.discount_cents)
            """).fetchall(), "Approved returns exceed the original sale"
            assert not connection.execute("""
                WITH line_totals AS (SELECT order_id,SUM(quantity*unit_price_cents-discount_cents) AS total FROM order_items GROUP BY order_id),
                paid AS (SELECT order_id,SUM(amount_cents) AS total FROM payments WHERE status='succeeded' GROUP BY order_id)
                SELECT o.order_id FROM orders o JOIN line_totals i ON i.order_id=o.order_id
                LEFT JOIN paid p ON p.order_id=o.order_id WHERE o.status='completed'
                AND COALESCE(p.total,0)<>i.total+o.shipping_fee_cents
            """).fetchall(), "Completed-order payment reconciliation failed"
    items = read_items()
    assert len({item["id"] for item in items}) == len(items), "Duplicate item IDs"
    assert len({item["question"] for item in items}) == len(items), "Duplicate questions"
    assert Counter(item["split"] for item in items) == {"dev": 10, "test": 50}
    unreviewed = 0
    for item in items:
        assert item["difficulty"] in ("easy", "medium", "hard")
        assert isinstance(item["ordered"], bool)
        if item["review_status"] != "reviewed" or len(set(item["reviewers"])) < 2:
            unreviewed += 1
        outputs = []
        for name in FIXTURES:
            result = execute_sql(DATABASES / f"{name}.sqlite", item["reference_sql"])
            assert len(result.columns) == len(item["expected_columns"]), item["id"] + ": wrong column count"
            outputs.append(result)
        assert any(output.rows for output in outputs), item["id"] + ": empty on every fixture; revise the question or fixture before freezing"
    summary = {"fixtures": len(FIXTURES), "tables_per_fixture": len(TABLES),
               "items": len(items), "reference_executions": len(items) * len(FIXTURES),
               "test_difficulties": dict(Counter(item["difficulty"] for item in items if item["split"] == "test")),
               "awaiting_two_human_reviews": unreviewed}
    if verbose:
        print(json.dumps(summary, indent=2))
        print("Automated checks passed. Human label review is tracked separately.")
    return summary


if __name__ == "__main__":
    validate()
