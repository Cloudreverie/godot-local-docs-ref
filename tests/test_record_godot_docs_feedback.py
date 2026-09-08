from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "record_godot_docs_feedback.py"


class FeedbackTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.log = self.root / "feedback.jsonl"

    def invoke(self, options=(), environment=None):
        env = dict(os.environ, GODOT_DOCS_FEEDBACK_FILE="", GODOT_DOCS_TASK_ID="", PYTHONDONTWRITEBYTECODE="1")
        env.update(environment or {})
        return subprocess.run([
            sys.executable, "-B", str(SCRIPT), "--query", "Node.queue_free",
            "--reason", "结果明确了释放时机，足以修正调用顺序。",
            "--version", "4.7", *options,
        ], cwd=self.root, env=env, capture_output=True, text=True)

    def test_default_disabled_and_independent_from_usage_log(self):
        result = self.invoke(environment={"GODOT_DOCS_LOG_FILE": str(self.log)})
        self.assertEqual(result.returncode, 0)
        self.assertFalse(self.log.exists())
        self.assertEqual(result.stdout, "")

    def test_appends_feedback_with_queries_sources_and_task(self):
        env = {"GODOT_DOCS_FEEDBACK_FILE": str(self.log), "GODOT_DOCS_TASK_ID": "task-17"}
        options = ["--outcome", "helpful", "--query", "Node.free", "--source", "classes/class_node.md:20",
                   "--follow-up", "补读了同页相邻说明。"]
        for _ in range(2):
            self.assertEqual(self.invoke(options, env).returncode, 0)
        records = [json.loads(line) for line in self.log.read_text().splitlines()]
        self.assertEqual(len(records), 2)
        record = records[0]
        self.assertEqual(record["event_type"], "feedback")
        self.assertEqual(record["author"], "agent")
        self.assertEqual(record["queries"], ["Node.queue_free", "Node.free"])
        self.assertEqual(record["sources"], ["classes/class_node.md:20"])
        self.assertEqual(record["task_id"], "task-17")
        self.assertEqual(record["outcome"], "helpful")
        self.assertIn("follow_up", record)

    def test_brief_observation_needs_no_rating_source_or_task(self):
        result = self.invoke(environment={"GODOT_DOCS_FEEDBACK_FILE": str(self.log)})
        self.assertEqual(result.returncode, 0)
        record = json.loads(self.log.read_text())
        self.assertEqual(record["outcome"], "uncertain")
        self.assertTrue(record["reason"])
        self.assertEqual(record["sources"], [])
        self.assertNotIn("task_id", record)

    def test_cli_overrides_environment_and_no_log_disables(self):
        other = self.root / "other.jsonl"
        env = {"GODOT_DOCS_FEEDBACK_FILE": str(other)}
        self.assertEqual(self.invoke(["--no-log"], env).returncode, 0)
        self.assertFalse(other.exists())
        self.assertEqual(self.invoke(["--log-file", str(self.log)], env).returncode, 0)
        self.assertTrue(self.log.exists())
        self.assertFalse(other.exists())

    def test_rejects_invalid_or_excessive_feedback(self):
        for options in (["--outcome", "correct"], ["--reason", " "],
                        ["--reason", "长" * 401], ["--query", "q"] * 10):
            with self.subTest(options=options):
                result = self.invoke([*options, "--log-file", str(self.log)])
                self.assertEqual(result.returncode, 2)
                self.assertFalse(self.log.exists())

    def test_log_failure_and_protected_locations_do_not_block(self):
        corpus = self.root / "corpus"
        for destination in (self.root / "references" / "feedback.jsonl", corpus / "feedback.jsonl"):
            with self.subTest(destination=destination):
                result = self.invoke(["--log-file", str(destination), "--docs-root", str(corpus)])
                self.assertEqual(result.returncode, 0)
                self.assertIn("日志写入失败", result.stderr)
                self.assertFalse(destination.exists())
        self.log.mkdir()
        result = self.invoke(["--log-file", str(self.log)])
        self.assertEqual(result.returncode, 0)
        self.assertIn("日志写入失败", result.stderr)


if __name__ == "__main__":
    unittest.main()
