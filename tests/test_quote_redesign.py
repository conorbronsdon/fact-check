"""Safety controls for quote boundaries, semantic punctuation and source context."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from check_quotes import check, find_quotes  # noqa: E402


class QuoteBoundaries(unittest.TestCase):
    def test_short_pair_does_not_consume_the_following_quote(self):
        draft = 'He said "yes" and then he remarked "we achieved 100 percent growth".'
        self.assertEqual([q["quote"] for q in find_quotes(draft)], ['we achieved 100 percent growth'])
        results = check(draft, 'The record says and then he remarked. Nothing about growth.')
        self.assertNotEqual(results[0]["status"], "verbatim")

    def test_malformed_pair_requires_review_and_short_only_is_clean(self):
        self.assertTrue(any(r["status"] == "ambiguous" for r in check('He said "unfinished', 'A source.')))
        self.assertEqual(check('He said "yes".', 'A source.'), [])
        with tempfile.TemporaryDirectory() as d:
            draft, source = Path(d, 'draft.md'), Path(d, 'source.md')
            draft.write_text('He said "unfinished', encoding='utf8')
            source.write_text('A source.', encoding='utf8')
            run = subprocess.run([sys.executable, str(ROOT/'scripts/check_quotes.py'), str(draft), '--source', str(source)], capture_output=True, text=True)
            self.assertNotEqual(run.returncode, 0)

    def test_bad_paragraph_does_not_hide_later_valid_quote(self):
        draft = 'An unfinished "quote here\n\nThen "the system is safe to deploy".'
        results = check(draft, 'the system is safe to deploy')
        self.assertEqual([r['status'] for r in results], ['verbatim', 'ambiguous'])

    def test_unclosed_markup_and_mixed_quotes_require_review(self):
        for draft in ('<!-- unclosed', '`unclosed', '---\ntitle: unclosed',
                      '\u201ca mismatched closing quote"'):
            with self.subTest(draft=draft):
                self.assertIn('ambiguous', [r['status'] for r in check(draft, 'A source.')])
        self.assertEqual(check('`a complete code span`', 'A source.'), [])

    def test_unclosed_fence_requires_review(self):
        self.assertTrue(any(r["status"] == "ambiguous" for r in check('```\n"hidden long quote"', 'A source.')))


class QuoteMeaning(unittest.TestCase):
    def test_changed_numbers_units_and_apostrophes_are_not_verbatim(self):
        pairs = [
            ('"the price was 5 million dollars"', 'the price was .5 million dollars'),
            ('"revenue grew 10 this quarter"', 'revenue grew 10 % this quarter'),
            ('"the price was 10 million dollars"', 'the price was $10 million dollars'),
            ('"were ready for the launch"', "we're ready for the launch"),
            ('"lets eat grandma now"', "let's eat, grandma now"),
        ]
        for draft, source in pairs:
            with self.subTest(draft=draft):
                self.assertNotEqual(check(draft, source)[0]['status'], 'verbatim')

    def test_case_changes_are_visible_in_diff(self):
        result = check('"US markets are growing today"', 'us markets are growing today')[0]
        self.assertEqual(result['status'], 'near')
        self.assertIn('[-us-]', result['diff'])
        self.assertIn('{+US+}', result['diff'])

    def test_equivalent_apostrophe_and_spaced_percent_still_match(self):
        self.assertEqual(check('"we\u2019re ready for the launch"', "we're ready for the launch")[0]['status'], 'verbatim')
        self.assertEqual(check('"revenue grew 10% this quarter"', 'revenue grew 10 % this quarter')[0]['status'], 'verbatim')
        self.assertEqual(check('"the price was .5 million dollars"', 'the price was .5 million dollars')[0]['status'], 'verbatim')


class TranscriptContext(unittest.TestCase):
    def test_wrapped_warning_is_complete(self):
        source = 'This can corrupt your data if you use it in\nproduction. The system is safe to deploy.\n'
        result = check('"The system is safe to deploy"', source)[0]
        self.assertIn('This can corrupt your data if you use it in production.', result['context']['before'])

    def test_exact_quote_cannot_span_speaker_turns(self):
        source = 'HOST: this is a dangerous\nGUEST: system to deploy today\n'
        self.assertNotEqual(check('"this is a dangerous system to deploy today"', source)[0]['status'], 'verbatim')

    def test_repeated_exact_quote_is_ambiguous(self):
        source = 'HOST: the system is safe to deploy.\nGUEST: the system is safe to deploy.\n'
        result = check('"the system is safe to deploy"', source)[0]
        self.assertEqual(result['status'], 'ambiguous')
        self.assertEqual(result['candidate_count'], 2)


if __name__ == '__main__':
    unittest.main()
