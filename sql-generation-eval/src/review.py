"""List draft questions or inspect one reference answer and its actual results."""

import argparse

from .common import DATABASES, FIXTURES, read_items
from .score import execute_sql


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--id", help="Question identifier, for example test_26")
    parser.add_argument("--split", choices=("dev", "test"))
    parser.add_argument("--fixture", choices=FIXTURES, default="retail_a")
    parser.add_argument("--rows", type=int, default=10, help="Maximum result rows displayed")
    args = parser.parse_args()
    if args.rows < 0:
        parser.error("--rows must be nonnegative")
    items = read_items(args.split)
    if not args.id:
        for item in items:
            print(f"{item['id']:8} {item['difficulty']:6} {item['skill']:24} {item['question']}")
        return
    item = next((item for item in items if item["id"] == args.id), None)
    if item is None:
        parser.error("No matching item")
    print(f"{item['id']} | {item['difficulty']} | {item['skill']} | {item['review_status']}")
    print(item["question"])
    print("\nReference SQL:\n" + item["reference_sql"])
    result = execute_sql(DATABASES / f"{args.fixture}.sqlite", item["reference_sql"])
    print(f"\n{args.fixture}: {len(result.rows)} rows")
    print(" | ".join(item["expected_columns"]))
    for row in result.rows[:args.rows]:
        print(" | ".join("NULL" if value is None else str(value) for value in row))


if __name__ == "__main__":
    main()
