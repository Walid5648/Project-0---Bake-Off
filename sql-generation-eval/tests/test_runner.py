"""Exercise durable logging and failure accounting without impersonating real model runs."""

import csv
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import MagicMock, patch

from src import run


class RunnerTests(unittest.TestCase):
    def test_timeout_is_logged_once_and_included_in_summary(self):
        model = "qwen2.5-coder:1.5b"
        client = MagicMock()

        def request(path, payload=None):
            return {
                "/api/version": {"version": "test-double"},
                "/api/tags": {"models": [{"name": model, "digest": "test-double"}]},
                "/api/ps": {"models": []},
                "/api/show": {"details": {"quantization_level": "Q4_K_M"}},
            }[path]

        client.request.side_effect = request
        client.generate.side_effect = [
            {"done": True, "response": "SELECT 1;"},
            {"done": True, "done_reason": "stop", "response": "SELECT customer_id,email FROM customers WHERE country='TN' ORDER BY customer_id",
             "prompt_eval_count": 100, "eval_count": 25, "eval_duration": 1_000_000_000, "load_duration": 0},
            TimeoutError("simulated timeout for runner test"),
        ]
        with tempfile.TemporaryDirectory() as temporary:
            with patch("sys.argv", ["run", "--model", model, "--limit", "2", "--output-root", temporary]), \
                 patch.object(run, "OllamaClient", return_value=client), \
                 patch.object(run, "hardware_snapshot", return_value={"source": "test-double"}), \
                 redirect_stdout(io.StringIO()):
                run.main()
            artifacts = next(Path(temporary).iterdir())
            with (artifacts / "per_item.csv").open(newline="", encoding="utf-8") as source:
                rows = list(csv.DictReader(source))
            with (artifacts / "summary.csv").open(newline="", encoding="utf-8") as source:
                summary = next(csv.DictReader(source))
            metadata = json.loads((artifacts / "metadata.json").read_text())
            self.assertEqual([row["status"] for row in rows], ["correct", "request_timeout"])
            self.assertEqual([row["correct"] for row in rows], ["1", "0"])
            self.assertEqual(summary["n"], "2")
            self.assertEqual(summary["correct"], "1")
            self.assertEqual(summary["request_timeout"], "1")
            self.assertEqual(len(list((artifacts / "raw").iterdir())), 2)
            self.assertTrue(metadata["provisional"])
            self.assertEqual(metadata["status"], "complete")
            self.assertEqual(client.generate.call_count, 3)  # One warm-up, two items; no retry.


if __name__ == "__main__":
    unittest.main()
