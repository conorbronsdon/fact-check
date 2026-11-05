import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from extract_claims import extract  # noqa: E402


def kinds(text):
    found = extract(text)
    return set().union(*(c["kinds"] for c in found)) if found else set()


class MustFire(unittest.TestCase):
    def test_money(self):
        self.assertIn("money", kinds("The company raised $40M in its Series B."))

    def test_percent(self):
        self.assertIn("percent", kinds("Inference costs fell 80% last year."))
        self.assertIn("percent", kinds("Churn dropped 3 percentage points."))

    def test_scale_and_conjunction_stay_one_claim(self):
        found = extract("He scaled it at Netflix across 300M subscribers.")
        self.assertEqual(len(found), 1)
        self.assertIn("scale", found[0]["kinds"])

    def test_date(self):
        self.assertIn("date", kinds("The model shipped on March 4, 2025."))
        self.assertIn("date", kinds("She joined in 2018 and left in early 2020."))
        self.assertIn("date", kinds("Revenue doubled in Q3 2024."))

    def test_count(self):
        self.assertIn("count", kinds("We surveyed 1,200 engineers."))
        self.assertIn("count", kinds("More than 40 companies signed on."))

    def test_superlative(self):
        self.assertIn("superlative", kinds("It is the first open model to do this."))
        self.assertIn("superlative", kinds("They are the #1 app in the category."))

    def test_attribution(self):
        self.assertIn("attribution", kinds("According to Gartner, adoption is rising."))
        self.assertIn("attribution", kinds("A recent study found that reviews slow teams down."))

    def test_quote(self):
        self.assertIn("quote", kinds('She said "we will never ship a closed model again" on stage.'))

    def test_multiplier(self):
        self.assertIn("multiplier", kinds("Throughput improved 3x after the change."))

    def test_line_numbers(self):
        found = extract("Intro line.\n\nThe round was $12M.\n")
        self.assertEqual(found[0]["line"], 3)

    def test_splits_sentences(self):
        found = extract("Opinions are cheap. Revenue grew 40% in 2024. I like it.")
        self.assertEqual(len(found), 1)
        self.assertTrue(found[0]["sentence"].startswith("Revenue"))


class MustNotFire(unittest.TestCase):
    def test_opinion(self):
        self.assertEqual(extract("I think this changes how teams work together."), [])

    def test_code_fence(self):
        self.assertEqual(extract("```\nprice = 40%  # 2024\n```\n"), [])

    def test_inline_code_and_urls(self):
        self.assertEqual(extract("Run `retry --max 300` and see https://example.com/2024/50-percent."), [])

    def test_list_numbering(self):
        self.assertEqual(extract("1. Open the file\n2. Save it\n## 3. Wrap up\n"), [])

    def test_front_matter(self):
        self.assertEqual(extract("---\ntitle: Top 10 in 2024\n---\nA plain sentence here.\n"), [])

    def test_version_strings(self):
        self.assertEqual(extract("Upgrade to v3.38.0 before you start."), [])

    def test_year_is_not_a_count(self):
        found = extract("The 2025 report covers the market.")
        self.assertNotIn("count", found[0]["kinds"])

    def test_short_quote(self):
        self.assertEqual(extract('Call it "done" and move on.'), [])


class CLI(unittest.TestCase):
    def run_cli(self, *args, stdin=None):
        return subprocess.run([sys.executable, str(ROOT / "scripts" / "extract_claims.py"), *args],
                              input=stdin, capture_output=True, text=True)

    def test_json_stdin(self):
        r = self.run_cli("--json", "-", stdin="Sales hit $5 billion in 2023.")
        self.assertEqual(r.returncode, 0)
        data = json.loads(r.stdout)
        self.assertEqual(len(data), 1)
        self.assertIn("money", data[0]["kinds"])
        self.assertIn("date", data[0]["kinds"])

    def test_markdown_empty(self):
        r = self.run_cli("-", stdin="Nothing checkable here at all.")
        self.assertEqual(r.returncode, 0)
        self.assertIn("No candidate claims", r.stdout)

    def test_missing_file(self):
        r = self.run_cli("does-not-exist.md")
        self.assertEqual(r.returncode, 2)

    def test_example_draft(self):
        r = self.run_cli("--json", str(ROOT / "examples" / "draft.md"))
        self.assertEqual(r.returncode, 0)
        self.assertGreaterEqual(len(json.loads(r.stdout)), 5)


if __name__ == "__main__":
    unittest.main()
