"""Unit tests for monitoring/check_runbooks.py: each case breaks one rule the checker enforces."""
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import check_runbooks  # noqa: E402

URL = check_runbooks.BASE + "egaexample"
RULES = f"""groups:
  - name: example
    rules:
      - alert: EGAExample
        expr: up == 0
        annotations:
          runbook_url: {URL}
"""
RUNBOOKS = "# Runbooks\n\n## EGAExample\n\nWhat to do.\n"


class CheckRunbooksTest(unittest.TestCase):
    def problems(self, rules=RULES, runbooks=RUNBOOKS):
        with tempfile.TemporaryDirectory() as tmp:
            rules_path, runbooks_path = os.path.join(tmp, "rules.yaml"), os.path.join(tmp, "runbooks.md")
            with open(rules_path, "w") as f:
                f.write(rules)
            with open(runbooks_path, "w") as f:
                f.write(runbooks)
            return check_runbooks.problems([rules_path], runbooks_path)

    def test_matching_alert_and_section_pass(self):
        self.assertEqual(self.problems(), [])

    def test_shipped_files_pass(self):
        root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
        paths = [os.path.join(root, d, f) for d in ("rules", "grafana") if os.path.isdir(os.path.join(root, d))
                 for f in sorted(os.listdir(os.path.join(root, d))) if f.endswith(".yaml")]
        self.assertEqual(check_runbooks.problems(paths), [])

    def test_missing_url_fails(self):
        self.assertIn("runbook_url must be", " ".join(self.problems(RULES.replace(f"runbook_url: {URL}", "summary: x"))))

    def test_wrong_url_fails(self):
        self.assertIn("runbook_url must be", " ".join(self.problems(RULES.replace("#egaexample", "#other"))))

    def test_alert_without_section_fails(self):
        self.assertIn("runbook_url must be", " ".join(self.problems(runbooks="# Runbooks\n")))

    def test_section_without_alert_fails(self):
        self.assertIn("has no alert", " ".join(self.problems(runbooks=RUNBOOKS + "\n## EGAOther\n")))

    def test_duplicate_section_fails(self):
        self.assertIn("duplicate sections", " ".join(self.problems(runbooks=RUNBOOKS + "\n## EGAExample\n")))

    def test_null_annotations_fail_cleanly(self):
        rules = RULES.replace(f"        annotations:\n          runbook_url: {URL}\n", "        annotations:\n")
        self.assertIn("runbook_url must be", " ".join(self.problems(rules)))

    def test_empty_file_has_no_alerts(self):
        self.assertEqual(len(self.problems(rules="")), 1)
        self.assertIn("has no alert", self.problems(rules="")[0])

    def test_empty_groups_have_no_alerts(self):
        self.assertEqual(len(self.problems(rules="groups:\n")), 1)

    def test_heading_with_trailing_words_is_not_a_section(self):
        found = self.problems(runbooks="# Runbooks\n\n## EGAExample (old)\n")
        self.assertIn("runbook_url must be", " ".join(found))

    def test_recording_rules_are_ignored(self):
        rules = RULES + "      - record: job:up:sum\n        expr: sum(up)\n"
        self.assertEqual(self.problems(rules), [])

    def test_missing_files_fail_cleanly(self):
        self.assertTrue(check_runbooks.problems(["/nonexistent/rules.yaml"]))
        with tempfile.NamedTemporaryFile("w", suffix=".yaml") as f:
            f.write(RULES)
            f.flush()
            self.assertTrue(check_runbooks.problems([f.name], "/nonexistent/runbooks.md"))

    def test_command_exit_status(self):
        script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "check_runbooks.py")
        with tempfile.NamedTemporaryFile("w", suffix=".yaml") as f:
            f.write(RULES)
            f.flush()
            bad = subprocess.run([sys.executable, script, f.name], capture_output=True)
        self.assertEqual(bad.returncode, 1)
        self.assertIn(b"runbook_url must be", bad.stderr)

    def test_malformed_files_fail_cleanly(self):
        for rules in ("- a\n", "groups: 5\n"):
            with self.subTest(rules=rules):
                found = self.problems(rules=rules)
                self.assertTrue(any("rules.yaml" in problem for problem in found), found)


if __name__ == "__main__":
    unittest.main()
