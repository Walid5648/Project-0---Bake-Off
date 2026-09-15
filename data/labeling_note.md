# Dataset Labeling & Verification Note

## Data Source
The dataset consists of 50 natural language questions targeting the standard SQLite version of the Chinook sample database. 

## Difficulty Stratification
- **Easy (Items 1–15):** Single-table lookups, string pattern matching (`LIKE`), basic counts, and simple `WHERE` filters.
- **Medium (Items 16–35):** 2–3 table `JOIN` operations, `GROUP BY`, aggregate calculations, and `HAVING` clauses.
- **Hard (Items 36–50):** Multi-table joins (4+ tables), conditional aggregations (`CASE WHEN`), `INTERSECT`, self-joins, and subquery logic.

## Label Verification
- Ground-truth queries were drafted and verified directly against `chinook.db`.
- Each query was executed in read-only mode to ensure:
  1. Valid SQLite dialect syntax.
  2. Non-empty, unambiguous result sets.
  3. Deterministic ordering using tie-breaking `ORDER BY` clauses when `LIMIT` is used.