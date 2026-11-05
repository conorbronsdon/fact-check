import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from score_log import parse_log, score, verdict_of  # noqa: E402

KEY = {"claims": [
    {"key": "err", "match": "Linux followed in 1995", "expect": ["incorrect"]},
    {"key": "clean", "match": "Python was first released", "expect": ["verified"]},
    {"key": "pair", "match": "CEO in 2016", "expect": ["incorrect", "inconsistent"]},
]}

GOOD = """**3 claims: 1 ✅, 1 ❌, 1 🔀.**

| # | Claim (as written) | Verdict | Source / correction |
|---|---|---|---|
| 1 | "Python was first released in 1991" | ✅ Verified | python.org |
| 2 | "Linux followed in 1995" | ❌ Incorrect | 1991 |
| 3 | "took over as Microsoft CEO in 2016" | 🔀 Inconsistent | 2014 elsewhere |
"""


class Verdicts(unittest.TestCase):
    def test_emoji_and_words(self):
        self.assertEqual(verdict_of("❌"), "incorrect")
        self.assertEqual(verdict_of("REFUTED"), "incorrect")
        self.assertEqual(verdict_of("🕰️ Stale"), "stale")
        self.assertEqual(verdict_of("⚠ Outdated"), "stale")
        self.assertEqual(verdict_of("🏷️ Self-reported"), "self-reported")
        self.assertEqual(verdict_of("Unverifiable"), "unverified")
        self.assertEqual(verdict_of("✅"), "verified")

    def test_incorrect_is_not_read_as_correct(self):
        self.assertEqual(verdict_of("Incorrect"), "incorrect")

    def test_unknown(self):
        self.assertIsNone(verdict_of("see notes"))


class Scoring(unittest.TestCase):
    def test_all_caught_no_false_alarms(self):
        res = score(KEY, parse_log(GOOD))
        self.assertEqual((res["caught"], res["planted_errors"]), (2, 2))
        self.assertEqual(res["false_alarms"], 0)
        self.assertEqual(res["agreement"], 1.0)

    def test_missed_error_lowers_recall(self):
        res = score(KEY, parse_log(GOOD.replace("❌ Incorrect", "✅ Verified")))
        self.assertEqual(res["caught"], 1)
        self.assertEqual(res["recall"], 0.5)

    def test_flagging_a_true_claim_is_a_false_alarm(self):
        res = score(KEY, parse_log(GOOD.replace("✅ Verified", "❌ Incorrect")))
        self.assertEqual(res["false_alarms"], 1)

    def test_unverified_true_claim_is_not_a_false_alarm(self):
        res = score(KEY, parse_log(GOOD.replace("✅ Verified", "⚠️ Unverified")))
        self.assertEqual(res["false_alarms"], 0)
        self.assertLess(res["agreement"], 1.0)

    def test_missing_row(self):
        res = score(KEY, parse_log(GOOD.replace("Linux followed", "Something else")))
        self.assertEqual(res["missing"], ["err"])
        self.assertEqual(res["caught"], 1)

    def test_counts_linked_sources(self):
        log = GOOD.replace("| python.org |", "| https://www.python.org/doc/ |")
        self.assertEqual(score(KEY, parse_log(log))["linked"], 1)
        self.assertEqual(score(KEY, parse_log(GOOD))["linked"], 0)

    def test_header_and_prose_are_not_rows(self):
        self.assertEqual(len(parse_log(GOOD)), 3)


class EvalSet(unittest.TestCase):
    def test_every_key_matches_its_draft_exactly_once(self):
        for path in sorted((ROOT / "evals" / "answers").glob("*.json")):
            key = json.loads(path.read_text(encoding="utf-8"))
            draft = (ROOT / "evals" / key["draft"]).read_text(encoding="utf-8").lower()
            self.assertTrue(any(set(c["expect"]) & {"incorrect", "stale"} for c in key["claims"]))
            for c in key["claims"]:
                self.assertEqual(draft.count(c["match"].lower()), 1, f"{path.name}: {c['key']}")


class CLI(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(ROOT / "scripts" / "score_log.py"), *args],
                              capture_output=True, text=True)

    def test_exit_codes(self):
        with tempfile.TemporaryDirectory() as d:
            key, log = Path(d) / "key.json", Path(d) / "log.md"
            key.write_text(json.dumps(KEY), encoding="utf-8")
            log.write_text(GOOD, encoding="utf-8")
            r = self.run_cli(str(key), str(log), "--min-recall", "1.0")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("2/2", r.stdout)
            log.write_text(GOOD.replace("❌ Incorrect", "✅ Verified"), encoding="utf-8")
            self.assertEqual(self.run_cli(str(key), str(log), "--min-recall", "1.0").returncode, 1)
            self.assertEqual(self.run_cli(str(key), "nope.md").returncode, 2)


if __name__ == "__main__":
    unittest.main()
