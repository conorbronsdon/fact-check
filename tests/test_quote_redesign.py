"""Safety controls for quote boundaries, semantic punctuation and source context."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from check_quotes import check, find_quotes, source_regions  # noqa: E402


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

    def test_mixed_quote_delimiters_require_review(self):
        self.assertIn('ambiguous', [r['status'] for r in check('“a mismatched closing quote"', 'A source.')])
        self.assertEqual(check('`a complete code span`', 'A source.'), [])

    def test_markup_inside_a_quote_is_literal_not_erased(self):
        for embedded in ('`not`', '<!-- not -->'):
            with self.subTest(embedded=embedded):
                draft = 'She said "the fix is ' + embedded + ' ready for production".'
                self.assertNotIn('verbatim', [r['status'] for r in check(draft, 'SAM: the fix is ready for production.')])
        self.assertEqual(check('Use `not ready` in docs. "the fix is ready for production"',
                               'the fix is ready for production')[0]['status'], 'verbatim')

    def test_stray_backticks_do_not_hide_later_paragraph(self):
        draft = 'It`s live.\n\nShe said "we never lost a single customer record".\n\nThat`s it.'
        self.assertEqual([r['status'] for r in check(draft, 'we never lost a single customer record')], ['verbatim'])
        self.assertNotEqual(check(draft, 'A source.')[0]['status'], 'verbatim')

    def test_horizontal_rule_and_front_matter_do_not_change_scope(self):
        for prefix in ('He said ', 'title: '):
            draft = '---\n' + prefix + '"we never lost a single customer record".\n---'
            self.assertEqual(check(draft, 'we never lost a single customer record')[0]['status'], 'verbatim')
            self.assertNotEqual(check(draft, 'A source.')[0]['status'], 'verbatim')

    def test_simple_prose_colon_is_not_a_speaker_turn(self):
        source = 'SAM: we tried it and\nthe short answer is: it worked.'
        self.assertEqual(check('"we tried it and the short answer is: it worked"', source)[0]['status'], 'verbatim')

    def test_utf8_input_and_output_in_ascii_environment(self):
        with tempfile.TemporaryDirectory() as d:
            source = Path(d, 'source.md')
            source.write_text('The temperature was \u221210 degrees yesterday.', encoding='utf-8')
            import os
            env = dict(os.environ, PYTHONIOENCODING='ascii')
            run = subprocess.run([sys.executable, str(ROOT/'scripts/check_quotes.py'), '-', '--source', str(source), '--json'],
                                 input='"The temperature was \u221210 degrees yesterday."'.encode('utf-8'),
                                 capture_output=True, env=env)
            self.assertEqual(run.returncode, 0, run.stderr.decode('utf-8', errors='replace'))
            self.assertEqual(__import__('json').loads(run.stdout.decode('utf-8'))[0]['status'], 'verbatim')

    def test_stray_backticks_and_real_inline_code_are_both_scanned(self):
        for draft in ('It`s live; she said "we never lost a single customer record" and that`s it.',
                      'Use `print("we never lost a single customer record")` here.'):
            self.assertNotEqual(check(draft, 'A source.')[0]['status'], 'verbatim')
            self.assertEqual(check(draft, 'we never lost a single customer record')[0]['status'], 'verbatim')

    def test_speaker_labels_stay_literal_and_context_remains_visible(self):
        for header in ('Speaker 2:', 'JAMES VAN DER MEER:'):
            source = 'HOST: We shipped it.\n' + header + ' it is safe to deploy today.'
            self.assertEqual(len(source_regions(source)), 1)
            result = check('"it is safe to deploy today"', source)[0]
            self.assertEqual(result['status'], 'verbatim')
            self.assertIn(header, result['context']['sentence'])
        self.assertEqual(check('"we tried it and the short answer is: it worked"',
                               'SAM: we tried it and\nthe short answer is: it worked.')[0]['status'], 'verbatim')

    def test_utf8_bom_on_both_files_and_stdin(self):
        with tempfile.TemporaryDirectory() as d:
            draft, source = Path(d, 'draft.md'), Path(d, 'source.md')
            draft.write_text('---\ntitle: "a normal front matter title"\n---\n"the system is safe to deploy"', encoding='utf-8-sig')
            source.write_text('SAM: the system is safe to deploy', encoding='utf-8-sig')
            args = [sys.executable, str(ROOT/'scripts/check_quotes.py')]
            by_file = subprocess.run(args + [str(draft), '--source', str(source), '--exclude-lines', '1:3', '--json'], capture_output=True)
            by_stdin = subprocess.run(args + ['-', '--source', str(source), '--exclude-lines', '1:3', '--json'], input=draft.read_bytes(), capture_output=True)
            for result in (by_file, by_stdin):
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual([r['status'] for r in __import__('json').loads(result.stdout)], ['verbatim', 'excluded'])

    def test_unclosed_fence_never_hides_a_quote(self):
        self.assertNotEqual(check('```\n"hidden long quote"', 'A source.')[0]['status'], 'verbatim')
        self.assertEqual(check('```\n"hidden long quote"', 'hidden long quote')[0]['status'], 'verbatim')


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

    def test_apostrophe_style_matches_but_percent_spacing_is_literal(self):
        self.assertEqual(check('"we\u2019re ready for the launch"', "we're ready for the launch")[0]['status'], 'verbatim')
        self.assertEqual(check('"revenue grew 10% this quarter"', 'revenue grew 10 % this quarter')[0]['status'], 'near')
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
