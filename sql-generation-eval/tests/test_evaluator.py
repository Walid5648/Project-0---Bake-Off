"""Behavioral checks for correctness, duplicate semantics, and query restrictions."""

import json
import unittest

from src.common import DATABASES, FIXTURES, read_items
from src.ollama_client import OllamaClient
from src.score import ParseError, QueryError, QueryResult, QueryTimeout, execute_sql, grade, parse_sql, results_equal
from src.summarize import percentile


class EvaluatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.database = DATABASES / "retail_a.sqlite"
        cls.databases = [DATABASES / f"{name}.sqlite" for name in FIXTURES]
        cls.items = {item["id"]: item for item in read_items()}
        if not cls.database.exists():
            raise RuntimeError("Run python -m src.setup before the tests")

    def test_equivalent_sql_passes_with_different_aliases_and_join_style(self):
        sql = "SELECT p.product_id AS id FROM products p WHERE p.product_id NOT IN (SELECT product_id FROM product_suppliers) ORDER BY p.product_id"
        self.assertTrue(grade(sql, self.items["test_19"], self.databases)["correct"])

    def test_incorrect_fanout_inflates_money_and_fails(self):
        sql = """SELECT o.order_id,SUM(oi.quantity*oi.unit_price_cents-oi.discount_cents),
                 SUM(CASE WHEN p.status='succeeded' THEN p.amount_cents ELSE 0 END),COUNT(s.shipment_id)
                 FROM orders o JOIN order_items oi ON oi.order_id=o.order_id
                 LEFT JOIN payments p ON p.order_id=o.order_id LEFT JOIN shipments s ON s.order_id=o.order_id
                 WHERE o.status='completed' GROUP BY o.order_id ORDER BY o.order_id"""
        result = grade(sql, self.items["test_27"], self.databases)
        self.assertFalse(result["correct"])
        self.assertTrue(all(not fixture["correct"] for fixture in result["fixtures"]))

    def test_distinct_is_wrong_when_duplicates_are_required(self):
        self.assertFalse(grade("SELECT DISTINCT country FROM customers", self.items["test_08"], self.databases)["correct"])

    def test_wrong_blob_output_can_still_be_logged(self):
        result = grade("SELECT x'ffff'", self.items["test_08"], self.databases)
        self.assertFalse(result["correct"])
        self.assertIn("sqlite_blob_hex", json.dumps(result))

    def test_counts_include_customers_without_addresses(self):
        wrong = "SELECT c.customer_id,COUNT(*) FROM customers c LEFT JOIN addresses a ON a.customer_id=c.customer_id GROUP BY c.customer_id ORDER BY c.customer_id"
        self.assertFalse(grade(wrong, self.items["test_02"], self.databases)["correct"])

    def test_unordered_results_preserve_multiplicity(self):
        expected = QueryResult(("country",), [("TN",), ("TN",), ("FR",)])
        shuffled = QueryResult(("alias",), [("FR",), ("TN",), ("TN",)])
        fewer = QueryResult(("country",), [("FR",), ("TN",)])
        self.assertTrue(results_equal(shuffled, expected, ordered=False))
        self.assertFalse(results_equal(shuffled, expected, ordered=True))
        self.assertFalse(results_equal(fewer, expected, ordered=False))

    def test_numeric_tolerance_does_not_coerce_text_or_null(self):
        expected = QueryResult(("ratio",), [(1 / 3,), (None,)])
        close = QueryResult(("alias",), [(0.3333333,), (None,)])
        text = QueryResult(("ratio",), [("0.3333333",), (None,)])
        self.assertTrue(results_equal(close, expected, True))
        self.assertFalse(results_equal(text, expected, True))

    def test_column_order_and_shape_matter(self):
        expected = QueryResult(("a", "b"), [(1, 2)])
        self.assertFalse(results_equal(QueryResult(("b", "a"), [(2, 1)]), expected, True))
        self.assertFalse(results_equal(QueryResult(("a",), [(1,)]), expected, True))

    def test_writes_attachments_and_filesystem_functions_are_rejected(self):
        for sql in ["DELETE FROM orders", "CREATE TABLE escaped(id INTEGER)",
                    "PRAGMA user_version=42", "ATTACH DATABASE ':memory:' AS other",
                    "SELECT load_extension('missing')", "SELECT readfile('README.md')",
                    "SELECT * FROM sqlite_master", "SELECT randomblob(1000000000)",
                    "SELECT 1; DELETE FROM orders"]:
            with self.subTest(sql=sql), self.assertRaises(QueryError):
                execute_sql(self.database, sql)
        self.assertEqual(execute_sql(self.database, "SELECT COUNT(*) FROM orders").rows, [(480,)])

    def test_expensive_recursive_query_times_out(self):
        sql = "WITH RECURSIVE t(n) AS (SELECT 1 UNION ALL SELECT n+1 FROM t) SELECT SUM(n) FROM t"
        with self.assertRaises(QueryTimeout):
            execute_sql(self.database, sql, timeout_s=.02)

    def test_result_rows_are_bounded(self):
        with self.assertRaises(QueryError):
            execute_sql(self.database, "SELECT a.order_id FROM orders a CROSS JOIN orders b", max_rows=100)

    def test_single_fence_is_accepted_but_commentary_is_not_removed(self):
        self.assertEqual(parse_sql("```sql\nSELECT 1;\n```"), "SELECT 1;")
        with self.assertRaises(ParseError):
            parse_sql("```sql\nSELECT 1;\n```\nHere is the answer")
        with self.assertRaises(ParseError):
            parse_sql("   ")

    def test_remote_model_endpoints_are_rejected(self):
        with self.assertRaises(ValueError):
            OllamaClient("https://example.com")

    def test_percentiles_use_linear_interpolation(self):
        self.assertEqual(percentile([1, 2, 3, 4], .5), 2.5)
        self.assertAlmostEqual(percentile([1, 2, 3, 4], .95), 3.85)


if __name__ == "__main__":
    unittest.main()
