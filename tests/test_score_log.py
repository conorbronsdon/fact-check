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

    def test_negation_and_qualifiers(self):
        self.assertEqual(verdict_of("Not verified"), "unverified")
        self.assertEqual(verdict_of("Not correct"), "incorrect")
        self.assertEqual(verdict_of("not true"), "incorrect")
        self.assertEqual(verdict_of("Partially correct"), "incorrect")

    def test_first_verdict_wins_over_later_words(self):
        self.assertEqual(verdict_of("⚠️ Unverified (figure may be outdated)"), "unverified")
        self.assertEqual(verdict_of("✅ Verified — not false"), "verified")
        self.assertEqual(verdict_of("✅ Verified (draft said ❌ earlier)"), "verified")

    def test_more_vocabulary(self):
        for word in ("Inaccurate", "Wrong", "Misattributed"):
            self.assertEqual(verdict_of(word), "incorrect", word)
        self.assertEqual(verdict_of("Confirmed"), "verified")
        self.assertEqual(verdict_of("✓"), "verified")

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

    def test_overclaim_when_only_self_reported_is_marked_verified(self):
        key = {"claims": [{"key": "bio", "match": "Python was first released", "expect": ["self-reported", "unverified"]}]}
        self.assertEqual(score(key, parse_log(GOOD))["overclaims"], 1)
        weak = GOOD.replace("✅ Verified", "🏷️ Self-reported")
        self.assertEqual(score(key, parse_log(weak))["overclaims"], 0)

    def test_verified_claim_is_never_an_overclaim(self):
        self.assertEqual(score(KEY, parse_log(GOOD))["overclaims"], 0)

    def test_counts_linked_sources(self):
        log = GOOD.replace("| python.org |", "| https://www.python.org/doc/ |")
        self.assertEqual(score(KEY, parse_log(log))["linked"], 1)
        self.assertEqual(score(KEY, parse_log(GOOD))["linked"], 0)

    def test_split_grouped_and_bold_rows(self):
        log = ("| 5a | \"Linux followed in 1995\" (attribution) | ❌ | x |\n"
               "| 5b | same, content | ⚠️ | x |\n"
               "| 3–4 | Python was first released; others | ⚠️ Unverified | x |\n"
               "| **6** | took over as Microsoft CEO in 2016 | 🔀 | x |\n")
        rows = parse_log(log)
        self.assertEqual(len(rows), 4)
        res = score(KEY, rows)
        self.assertEqual(res["missing"], [])
        self.assertEqual(res["caught"], 2)

    def test_escaped_pipe_inside_a_claim(self):
        log = "| 2 | a \\| b Linux followed in 1995 | ❌ Incorrect | https://kernel.org |\n"
        rows = parse_log(log)
        self.assertEqual(rows[0]["verdict"], "incorrect")
        self.assertIn("a | b", rows[0]["claim"])
        self.assertTrue(rows[0]["linked"])

    def test_link_only_counts_in_the_source_column(self):
        log = "| 1 | Python was first released | ✅ | python.org | https://notes.example |\n"
        self.assertFalse(parse_log(log)[0]["linked"])

    def test_header_and_prose_are_not_rows(self):
        self.assertEqual(len(parse_log(GOOD)), 3)


class EvalSet(unittest.TestCase):
    def test_every_key_matches_its_draft_exactly_once(self):
        for path in sorted((ROOT / "evals" / "answers").glob("*.json")):
            key = json.loads(path.read_text(encoding="utf-8"))
            draft = (ROOT / "evals" / key["draft"]).read_text(encoding="utf-8").lower()
            for comp in key.get("companions", []):
                self.assertTrue((ROOT / "evals" / comp).is_file(), comp)
            self.assertTrue(any(set(c["expect"]) & {"incorrect", "stale"} for c in key["claims"]))
            for c in key["claims"]:
                self.assertEqual(draft.count(c["match"].lower()), 1, f"{path.name}: {c['key']}")

    def test_every_key_entry_says_why(self):
        for path in sorted((ROOT / "evals" / "answers").glob("*.json")):
            key = json.loads(path.read_text(encoding="utf-8"))
            keys = [c["key"] for c in key["claims"]]
            self.assertEqual(len(keys), len(set(keys)), f"{path.name}: duplicate key")
            for c in key["claims"]:
                self.assertTrue(c.get("why", "").strip(), f"{path.name}: {c['key']} has no why")

    def test_coreweave_description_and_invented_customer_are_scored_separately(self):
        key = json.loads((ROOT / "evals/answers/episode-recap.json").read_text(encoding="utf-8"))
        provider = next((c for c in key["claims"] if c["key"] == "coreweave"), None)
        customer = next((c for c in key["claims"] if c["key"] == "fernwick-coreweave"), None)
        self.assertIsNotNone(provider)
        self.assertIsNotNone(customer)
        rows = [{"claim": provider["match"], "verdict": "verified", "linked": True},
                {"claim": customer["match"], "verdict": "verified", "linked": True}]
        result = score(key, rows)
        claims = {c["key"]: c for c in result["claims"]}
        self.assertTrue(claims["coreweave"]["ok"])
        self.assertFalse(claims["fernwick-coreweave"]["ok"])
        self.assertTrue(claims["fernwick-coreweave"]["overclaim"])
        rows[1]["verdict"] = "unverified"
        self.assertTrue({c["key"]: c for c in score(key, rows)["claims"]}["fernwick-coreweave"]["ok"])

    def test_baseline_prompt_exposes_all_verdicts_needed_by_new_keys(self):
        prompt_path = ROOT / "evals/baseline-prompt.txt"
        self.assertTrue(prompt_path.is_file(), "the baseline prompt must be saved for reproducible runs")
        prompt = prompt_path.read_text(encoding="utf-8").lower()
        required = {"verified", "self-reported", "stale", "unverified", "incorrect", "inconsistent"}
        prefix = "use one of these verdicts: "
        self.assertIn(prefix, prompt)
        labels = {part.strip(" .\n") for part in prompt.split(prefix, 1)[1].split(",")}
        self.assertEqual(labels, required)
        needed = set()
        for path in (ROOT / "evals" / "answers").glob("*.json"):
            key = json.loads(path.read_text(encoding="utf-8"))
            needed.update(v for claim in key["claims"] for v in claim["expect"])
        self.assertLessEqual(needed, labels)
        for verdict in labels:
            self.assertEqual(verdict_of(verdict), verdict)

    def test_matches_do_not_overlap_within_a_key(self):
        # One log row per claim: if one match contains another, both keys
        # would score the same row.
        for path in sorted((ROOT / "evals" / "answers").glob("*.json")):
            matches = [c["match"].lower() for c in json.loads(path.read_text(encoding="utf-8"))["claims"]]
            for i, a in enumerate(matches):
                for b in matches[i + 1:]:
                    self.assertNotIn(a, b, f"{path.name}: '{a}' inside '{b}'")
                    self.assertNotIn(b, a, f"{path.name}: '{b}' inside '{a}'")


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

    def test_malformed_or_empty_key_is_2(self):
        with tempfile.TemporaryDirectory() as d:
            log = Path(d) / "log.md"
            log.write_text(GOOD, encoding="utf-8")
            for bad in ({}, {"claims": []}, {"claims": [{"key": "x"}]}, []):
                key = Path(d) / "key.json"
                key.write_text(json.dumps(bad), encoding="utf-8")
                r = self.run_cli(str(key), str(log), "--min-recall", "0.8")
                self.assertEqual(r.returncode, 2, bad)


if __name__ == "__main__":
    unittest.main()
