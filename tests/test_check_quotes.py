import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from check_quotes import check, find_quotes  # noqa: E402

SCRIPT = ROOT / "scripts" / "check_quotes.py"
DRAFT = ROOT / "evals" / "drafts" / "episode-launch.md"
TRANSCRIPT = ROOT / "evals" / "drafts" / "episode-launch.transcript.md"

SOURCE = (
    "HOST: What did the migration teach you?\n\n"
    "SAM: We moved everything to one queue, and the pager finally went quiet for a month. "
    "Nobody expected that.\n\n"
    "HOST: Would you do it again?\n"
)


def one(draft, source=SOURCE):
    results = check(draft, source)
    assert len(results) == 1, results
    return results[0]


def run(*args):
    proc = subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)
    return proc.returncode, proc.stdout, proc.stderr


class MustFire(unittest.TestCase):
    def test_exact_quote_is_verbatim(self):
        r = one('Sam said "the pager finally went quiet for a month" after the move.')
        self.assertEqual(r["status"], "verbatim")
        self.assertEqual(r["context"]["after"], "Nobody expected that.")

    def test_episode_launch_misquote_is_near_and_shows_dropped_our(self):
        r = one(DRAFT.read_text(encoding="utf-8"), TRANSCRIPT.read_text(encoding="utf-8"))
        self.assertEqual(r["status"], "near")
        self.assertEqual(r["quote"], "Most outages start in config, not code,")
        self.assertIn("most of our outages started in config", r["source_text"])
        self.assertIn("[-of our-]", r["diff"])
        self.assertEqual(r["context"]["before"], "Small on purpose.")
        self.assertIn("most of our outages", r["context"]["sentence"])
        self.assertEqual(r["context"]["after"], "That was the surprise.")

    def test_quote_not_in_source_is_absent(self):
        r = one('She said "we rewrote the billing system in Rust over a weekend" on stage.')
        self.assertEqual(r["status"], "absent")
        self.assertNotIn("source_text", r)

    def test_changed_word_is_near(self):
        r = one('"the pager finally went silent for a month"')
        self.assertEqual(r["status"], "near")
        self.assertIn("[-quiet-]", r["diff"])
        self.assertIn("{+silent+}", r["diff"])

    def test_cli_exit_1_on_near_or_absent(self):
        code, out, _ = run(str(DRAFT), "--source", str(TRANSCRIPT))
        self.assertEqual(code, 1)
        self.assertIn("NEAR", out)
        self.assertIn("[-of our-]", out)
        self.assertIn("before: Small on purpose.", out)

    def test_cli_exit_2_on_bad_input(self):
        self.assertEqual(run(str(DRAFT), "--source", "/no/such/file")[0], 2)
        self.assertEqual(run("/no/such/file", "--source", str(TRANSCRIPT))[0], 2)
        self.assertEqual(run(str(DRAFT))[0], 2)
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as fh:
            fh.write("  \n")
        self.assertEqual(run(str(DRAFT), "--source", fh.name)[0], 2)
        Path(fh.name).unlink()


class MustNotFire(unittest.TestCase):
    def test_curly_quotes_are_still_verbatim(self):
        r = one("Sam said “the pager finally went quiet for a month” after the move.")
        self.assertEqual(r["status"], "verbatim")

    def test_line_wrapping_is_still_verbatim(self):
        r = one('Sam said "the pager finally\nwent quiet for a month" after the move.')
        self.assertEqual(r["status"], "verbatim")
        self.assertEqual(r["quote"], "the pager finally went quiet for a month")

    def test_source_wrapped_across_lines_is_still_verbatim(self):
        r = one('"the pager finally went quiet"', "SAM: and the pager\nfinally went\nquiet.\n")
        self.assertEqual(r["status"], "verbatim")

    def test_case_punctuation_and_apostrophes_are_still_verbatim(self):
        r = one('"We moved everything to one queue -- and the pager finally went quiet!"')
        self.assertEqual(r["status"], "verbatim")
        r = one("“we’re small on purpose, honestly”", "DANA: We're small on purpose. Honestly.")
        self.assertEqual(r["status"], "verbatim")

    def test_short_quotes_are_not_checked(self):
        self.assertEqual(find_quotes('They called it "the queue" and moved on.'), [])

    def test_quotes_in_code_and_front_matter_are_not_checked(self):
        draft = ('---\ntitle: "a front matter title string"\n---\n'
                 '```\nprint("this is a code string, not a quote")\n```\n'
                 'Run `echo "another code string here"` first.\n')
        self.assertEqual(find_quotes(draft), [])

    def test_unbalanced_quote_does_not_cross_paragraphs(self):
        self.assertEqual(find_quotes('He said "maybe\n\nlater it shipped" ok.'), [])

    def test_cli_exit_0_when_all_verbatim_or_no_quotes(self):
        with tempfile.TemporaryDirectory() as d:
            draft, source = Path(d, "draft.md"), Path(d, "source.md")
            source.write_text(SOURCE, encoding="utf-8")
            draft.write_text('Sam: "the pager finally went quiet for a month."\n', encoding="utf-8")
            code, out, _ = run(str(draft), "--source", str(source), "--json")
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(out)[0]["status"], "verbatim")
            draft.write_text("No quotes here at all.\n", encoding="utf-8")
            self.assertEqual(run(str(draft), "--source", str(source))[0], 0)


if __name__ == "__main__":
    unittest.main()
