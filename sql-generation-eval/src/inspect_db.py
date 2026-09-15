"""Inspect the database or execute a read-only query without a GUI dependency."""

import argparse

from .common import DATABASES, FIXTURES
from .score import execute_sql


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", choices=FIXTURES, default="retail_a")
    parser.add_argument("--sql", help="One read-only SQL query")
    args = parser.parse_args()
    database = DATABASES / f"{args.fixture}.sqlite"
    if not database.exists():
        raise SystemExit("Database missing. Run python -m src.setup first.")
    if args.sql:
        result = execute_sql(database, args.sql)
        print(" | ".join(result.columns))
        for row in result.rows:
            print(" | ".join("NULL" if value is None else str(value) for value in row))
        print(f"({len(result.rows)} rows)")
    else:
        from .score import TABLES
        for table in sorted(TABLES):
            count = execute_sql(database, f'SELECT COUNT(*) FROM "{table}"').rows[0][0]
            print(f"{table:20} {count:6} rows")


if __name__ == "__main__":
    main()
