import sqlite3

def clean_sql(raw_output: str) -> str:
    """Removes markdown formatting and ensures a clean SQL string."""
    sql = raw_output.strip()
    if sql.lower().startswith("```sql"):
        sql = sql[6:]
    elif sql.startswith("```"):
        sql = sql[3:]
    if sql.endswith("```"):
        sql = sql[:-3]
    return sql.strip().rstrip(";") + ";"

def execute_sql(db_path: str, sql: str, timeout: float = 5.0):
    """Executes SQL in read-only mode and returns the fetched rows."""
    try:
        # uri=True allows us to strictly enforce read-only mode (mode=ro)
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=timeout)
        cursor = conn.cursor()
        cursor.execute(sql)
        rows = cursor.fetchall()
        conn.close()
        return True, rows, None
    except Exception as e:
        return False, None, str(e)

def score(db_path: str, pred_sql_raw: str, gold_sql: str) -> tuple:
    """Returns (binary_score, status, cleaned_sql)."""
    pred_sql = clean_sql(pred_sql_raw)

    # Execute predicted SQL
    pred_ok, pred_rows, pred_err = execute_sql(db_path, pred_sql)
    if not pred_ok:
        return 0, "syntax_error", pred_sql

    # Execute ground-truth SQL
    gold_ok, gold_rows, gold_err = execute_sql(db_path, gold_sql)
    if not gold_ok:
        return 0, "gold_sql_error", pred_sql

    # Compare result sets (independent of order unless specified)
    if pred_rows == gold_rows or set(pred_rows) == set(gold_rows):
        return 1, "correct", pred_sql
    else:
        return 0, "incorrect_results", pred_sql