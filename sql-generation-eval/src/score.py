"""Execute and compare SQL under one read-only, bounded grading policy."""

from __future__ import annotations

import math
import re
import sqlite3
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

TABLES = {
    "customers", "addresses", "categories", "suppliers", "products", "product_suppliers",
    "orders", "order_items", "payments", "shipments", "returns", "return_items",
}
FUNCTIONS = {
    "abs", "avg", "cast", "ceil", "ceiling", "coalesce", "count", "cume_dist", "date",
    "datetime", "dense_rank", "first_value", "floor", "format", "glob", "group_concat",
    "ifnull", "iif", "instr", "julianday", "lag", "last_value", "lead", "length", "like",
    "lower", "ltrim", "max", "min", "nth_value", "ntile", "nullif", "percent_rank", "printf",
    "rank", "replace", "round", "row_number", "rtrim", "strftime", "substr", "substring",
    "sum", "time", "total", "trim", "typeof", "unicode", "unixepoch", "upper",
}


class ParseError(ValueError):
    pass


class QueryError(ValueError):
    pass


class QueryTimeout(QueryError):
    pass


@dataclass
class QueryResult:
    columns: tuple[str, ...]
    rows: list[tuple]


def parse_sql(output: str) -> str:
    """Accept raw SQL or one complete sql/sqlite Markdown fence; never repair SQL."""
    sql = output.strip()
    if sql.startswith("```"):
        match = re.fullmatch(r"```(?:sql|sqlite)?[ \t]*\r?\n(.*?)\r?\n```", sql, flags=re.S | re.I)
        if not match:
            raise ParseError("Expected a single complete SQL code fence without commentary")
        sql = match.group(1).strip()
    if not sql:
        raise ParseError("Empty response")
    if len(sql) > 50_000:
        raise ParseError("SQL exceeds the 50,000-character limit")
    # SQLite handles comments, WITH clauses, and single-statement enforcement.
    return sql


def _authorize(action: int, arg1: str | None, arg2: str | None, database: str | None, source: str | None) -> int:
    if action in (sqlite3.SQLITE_SELECT, sqlite3.SQLITE_RECURSIVE):
        return sqlite3.SQLITE_OK
    if action == sqlite3.SQLITE_READ and database in ("main", None) and arg1 in TABLES:
        return sqlite3.SQLITE_OK
    if action == sqlite3.SQLITE_FUNCTION and (arg2 or "").lower() in FUNCTIONS:
        return sqlite3.SQLITE_OK
    return sqlite3.SQLITE_DENY


def execute_sql(database: Path, sql: str, timeout_s: float = 3.0, max_rows: int = 10_000) -> QueryResult:
    connection = sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)
    deadline = time.perf_counter() + timeout_s
    expired = False

    def check_deadline() -> int:
        nonlocal expired
        expired = time.perf_counter() >= deadline
        return int(expired)

    try:
        connection.execute("PRAGMA query_only = ON")
        connection.execute("PRAGMA temp_store = MEMORY")
        connection.setlimit(sqlite3.SQLITE_LIMIT_SQL_LENGTH, 50_000)
        connection.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, 1_000_000)
        connection.setlimit(sqlite3.SQLITE_LIMIT_EXPR_DEPTH, 100)
        connection.setlimit(sqlite3.SQLITE_LIMIT_COMPOUND_SELECT, 30)
        connection.set_authorizer(_authorize)
        connection.set_progress_handler(check_deadline, 1000)
        cursor = connection.execute(sql)
        if cursor.description is None:
            raise QueryError("Query did not return a result table")
        rows = cursor.fetchmany(max_rows + 1)
        if len(rows) > max_rows:
            raise QueryError(f"Query exceeded {max_rows} result rows")
        if check_deadline():
            raise QueryTimeout("SQL execution deadline exceeded")
        return QueryResult(tuple(column[0] for column in cursor.description), rows)
    except sqlite3.Error as error:
        if expired:
            raise QueryTimeout("SQL execution deadline exceeded") from error
        raise QueryError(str(error)) from error
    finally:
        connection.close()


def results_equal(actual: QueryResult, expected: QueryResult, ordered: bool, float_tolerance: float = 1e-6) -> bool:
    """Aliases are ignored; column position, NULL, text case, and duplicates matter."""
    if len(actual.columns) != len(expected.columns) or len(actual.rows) != len(expected.rows):
        return False
    # Questions put decimal-valued outputs in explicitly ordered results, avoiding
    # ambiguous matching of near-equal floating-point rows in unordered results.
    if not ordered:
        return Counter(actual.rows) == Counter(expected.rows)

    def cell_equal(left: object, right: object) -> bool:
        if isinstance(left, (int, float)) and isinstance(right, (int, float)):
            if isinstance(left, int) and isinstance(right, int):
                return left == right
            return math.isclose(left, right, rel_tol=0.0, abs_tol=float_tolerance)
        return type(left) is type(right) and left == right

    return all(all(cell_equal(a, b) for a, b in zip(row_a, row_b))
               for row_a, row_b in zip(actual.rows, expected.rows))


def grade(sql: str, item: dict, databases: list[Path]) -> dict:
    def sample(rows: list[tuple]) -> list[list]:
        # SQLite may return BLOBs even though our schema contains no BLOB columns.
        # Retain their actual value in an explicit JSON representation when a
        # wrong model answer produces one, instead of crashing result logging.
        return [[{"sqlite_blob_hex": value.hex()} if isinstance(value, bytes) else value
                 for value in row] for row in rows[:5]]

    details = []
    for database in databases:
        # A broken gold query is a benchmark defect, not a model failure.
        expected = execute_sql(database, item["reference_sql"])
        try:
            actual = execute_sql(database, sql)
            correct = results_equal(actual, expected, item["ordered"])
            details.append({"fixture": database.stem, "correct": correct,
                            "status": "correct" if correct else "wrong_result",
                            "expected_rows": len(expected.rows), "actual_rows": len(actual.rows),
                            "expected_sample": sample(expected.rows), "actual_sample": sample(actual.rows)})
        except QueryError as error:
            details.append({"fixture": database.stem, "correct": False,
                            "status": "sql_timeout" if isinstance(error, QueryTimeout) else "sql_error",
                            "error": str(error)})
    failure = next((detail["status"] for detail in details if not detail["correct"]), None)
    return {"correct": failure is None, "status": failure or "correct", "fixtures": details}
