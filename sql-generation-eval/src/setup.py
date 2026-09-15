"""Create reproducible SQLite files. Run: python -m src.setup"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import tempfile
from pathlib import Path

from .common import DATA, DATABASES, FIXTURES, ROOT, dump_json, file_hash
from .seed import populate


def build_database(path: Path, seed: int) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Build a complete temporary file before replacing an existing generated fixture.
    fd, temporary = tempfile.mkstemp(prefix="retail-", suffix=".sqlite", dir=path.parent)
    os.close(fd)
    staging = Path(temporary)
    connection = sqlite3.connect(staging)
    try:
        connection.executescript((DATA / "schema.sql").read_text(encoding="utf-8"))
        populate(connection, seed)
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert not connection.execute("PRAGMA foreign_key_check").fetchall()
        tables = [row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        counts = {table: connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0] for table in tables}
    finally:
        connection.close()
    staging.replace(path)
    return {"seed": seed, "sha256": file_hash(path), "rows": counts}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="Rebuild generated database files; discards GUI edits to these files")
    args = parser.parse_args()
    fingerprint = {name: file_hash(ROOT / name) for name in ("data/schema.sql", "src/seed.py", "src/setup.py")}
    manifest_path = DATABASES / "manifest.json"
    old = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    manifest = {"sqlite_version": sqlite3.sqlite_version, "sources": fingerprint, "fixtures": {}}
    for name, seed in zip(FIXTURES, (17, 43, 97)):
        path = DATABASES / f"{name}.sqlite"
        if path.exists() and not args.force:
            previous = old.get("fixtures", {}).get(name, {})
            if old.get("sources") != fingerprint or previous.get("sha256") != file_hash(path):
                raise SystemExit(f"{path.name} or its source changed. Use --force to rebuild after saving any manual work.")
            manifest["fixtures"][name] = previous
            print(f"Unchanged: {path.relative_to(ROOT)}")
        else:
            manifest["fixtures"][name] = build_database(path, seed)
            print(f"Created: {path.relative_to(ROOT)} (12 tables)")
    dump_json(manifest_path, manifest)
    print("Open data/databases/retail_a.sqlite with DB Browser for SQLite to explore it.")


if __name__ == "__main__":
    main()
