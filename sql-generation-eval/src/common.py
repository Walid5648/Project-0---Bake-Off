"""Paths, immutable input fingerprints, and JSONL helpers."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DATABASES = DATA / "databases"
FIXTURES = ("retail_a", "retail_b", "retail_c")


def read_items(split: str | None = None) -> list[dict]:
    with (DATA / "items.jsonl").open(encoding="utf-8") as source:
        items = [json.loads(line) for line in source if line.strip()]
    if split:
        items = [item for item in items if item["split"] == split]
    return items


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def dump_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
