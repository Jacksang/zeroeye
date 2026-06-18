#!/usr/bin/env python3
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tools"))

from log_aggregator import LogAggregator  # noqa: E402


class LogAggregatorJsonlTest(unittest.TestCase):
    def test_jsonl_records_include_required_schema_warning_and_timestamp_order(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            app_log = tmp / "app.log"
            access_log = tmp / "access.log"
            app_log.write_text(
                '\n'.join(
                    [
                        '2024-01-15 12:00:02 INFO [api] request finished',
                        'this line has no structured timestamp level or service',
                    ]
                )
                + '\n',
                encoding="utf-8",
            )
            access_log.write_text(
                '127.0.0.1 - - [15/Jan/2024:12:00:01 +0000] "GET /health HTTP/1.1" 200 2 "-" "curl"\n',
                encoding="utf-8",
            )

            aggregator = LogAggregator()
            aggregator.process_file(str(app_log))
            aggregator.process_file(str(access_log))
            records = aggregator.iter_jsonl_records()

        self.assertEqual([record["timestamp"] for record in records[:2]], [
            "2024-01-15T12:00:01Z",
            "2024-01-15T12:00:02Z",
        ])
        for record in records:
            self.assertEqual(set(record), {"timestamp", "level", "source", "message", "metadata"})
        warning = records[-1]
        self.assertEqual(warning["level"], "warning")
        self.assertEqual(warning["metadata"].get("warning"), "unparsed_line")
        self.assertIn("raw", warning["metadata"].get("fields", {}))

    def test_cli_jsonl_emits_parseable_lines(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            sample = tmp / "sample.log"
            sample.write_text('2024-01-15T12:00:03 ERROR [worker] failed job\n', encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, str(REPO_ROOT / "tools" / "log_aggregator.py"), "--input", str(sample), "--format", "jsonl"],
                text=True,
                capture_output=True,
                check=True,
            )
        lines = [json.loads(line) for line in proc.stdout.splitlines() if line.strip()]
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0]["level"], "error")
        self.assertEqual(lines[0]["message"], "2024-01-15T12:00:03 ERROR [worker] failed job")


if __name__ == "__main__":
    unittest.main()
