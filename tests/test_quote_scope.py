"""Issue #13 acceptance controls for a scope contract without markup inference."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from check_quotes import check, to_text

PHRASE = 'we never lost a single customer record'


class ScopeContract(unittest.TestCase):
    def test_issue13_hidden_prose_is_never_clean(self):
        drafts = [
            '---\nsummary: >\n  She said "' + PHRASE + '".\n---',
            '---\nexcerpt: "She said “' + PHRASE + '”"\n---',
            'The users` data is safe; she said "' + PHRASE + '" and that`s it.',
            'It `s a live claim: "' + PHRASE + '" said she` today.',
        ]
        for draft in drafts:
            with self.subTest(draft=draft):
                results = check(draft, 'A source.')
                self.assertTrue(results)
                self.assertTrue(any(r['status'] in ('absent', 'near', 'ambiguous') for r in results))

    def test_valid_single_quoted_yaml_value_scans_inner_phrase(self):
        draft = "---\nexcerpt: 'She said \"" + PHRASE + "\"'\n---"
        result = check(draft, PHRASE)
        self.assertEqual([r['status'] for r in result], ['verbatim'])
        self.assertEqual(result[0]['line'], 2)

    def test_folded_metadata_quote_matches_without_yaml_parsing(self):
        draft = '---\nsummary: >\n  She said "' + PHRASE + '".\n---'
        self.assertEqual(check(draft, PHRASE)[0]['status'], 'verbatim')

    def test_explicit_metadata_and_code_exclusions_are_visible(self):
        draft = ('---\ntitle: "a normal front matter title"\n---\n'
                 '```python\nprint("a harmless code string")\n```\n'
                 'She said "' + PHRASE + '".\n')
        results = check(draft, PHRASE, exclude_lines=[(1, 3), (4, 6)])
        self.assertEqual([r['status'] for r in results], ['verbatim', 'excluded', 'excluded'])
        self.assertEqual(results[0]['line'], 7)
        self.assertEqual([(r['line'], r['end_line']) for r in results[1:]], [(1, 3), (4, 6)])
        self.assertIn('NOT CHECKED', to_text(results))
        self.assertNotIn('No eligible', to_text(results))
        self.assertTrue(any(r['status'] != 'verbatim' for r in check(draft, PHRASE)))

    def test_inline_code_has_an_explicit_line_exclusion_path(self):
        draft = 'Use `print("a harmless code string")`.\nNo quotations here.\n'
        self.assertEqual([r['status'] for r in check(draft, 'A source.', exclude_lines=[(1, 1)])], ['excluded'])
        self.assertNotEqual(check(draft, 'A source.')[0]['status'], 'verbatim')

    def test_exclusion_does_not_pair_delimiters_across_a_gap(self):
        draft = 'She said "the first half\nexcluded material\nand the second half".\n'
        results = check(draft, 'the first half and the second half', exclude_lines=[(2, 2)])
        self.assertNotIn('verbatim', [r['status'] for r in results])
        self.assertIn('ambiguous', [r['status'] for r in results])
        self.assertEqual(check('"the first half and the second half"',
                               'the first half and the second half')[0]['status'], 'verbatim')

    def test_bad_ranges_are_errors_not_scope_changes(self):
        for ranges in [[(0, 1)], [(2, 1)], [(1, 3)], [(1, 1), (1, 2)]]:
            with self.subTest(ranges=ranges), self.assertRaises(ValueError):
                check('one\ntwo', 'A source.', exclude_lines=ranges)
        self.assertEqual(check('one\ntwo', 'A source.', exclude_lines=[(1, 2)])[0]['status'], 'excluded')

    def test_mixed_fences_and_html_comments_have_no_masking_power(self):
        for draft in ['~~~\n```\n~~~\n"' + PHRASE + '"', '<!-- "' + PHRASE + '" -->']:
            self.assertNotEqual(check(draft, 'A source.')[0]['status'], 'verbatim')
            self.assertEqual(check(draft, PHRASE)[0]['status'], 'verbatim')

    def test_escaped_quotes_require_review_not_an_empty_success(self):
        results = check('She said \\"' + PHRASE + '\\".', 'A source.')
        self.assertIn('ambiguous', [r['status'] for r in results])
        self.assertEqual(check('She said "' + PHRASE + '".', PHRASE)[0]['status'], 'verbatim')

    def test_march_2024_is_not_a_speaker_boundary(self):
        source = 'The release was planned for\nMarch 2024: we shipped it on schedule.'
        result = check('"The release was planned for March 2024: we shipped it on schedule"', source)[0]
        self.assertEqual(result['status'], 'verbatim')
        self.assertIn('March 2024:', result['context']['sentence'])
        self.assertNotEqual(check('"The release was planned for March 2025: we shipped it on schedule"', source)[0]['status'], 'verbatim')

    def test_character_comparison_keeps_internal_spacing_and_numeric_edges(self):
        pairs = [
            ('in the US, markets grew', 'in the US , markets grew'),
            ('100 dollars was the cost', '$100 dollars was the cost'),
            ('100 dollars was the cost', '-100 dollars was the cost'),
            ('the cost was exactly 100', 'the cost was exactly 100%'),
            ('the cost was exactly 100', 'the cost was exactly 100 €'),
            ('100 dollars was the cost', '₩100 dollars was the cost'),
            ('.5 million was the total', '1.5 million was the total'),
            ('the year was 2024', 'the year was 2024.5'),
            ('were ready for launch', "we're ready for launch"),
        ]
        for quote, source in pairs:
            with self.subTest(quote=quote, source=source):
                self.assertNotEqual(check('"' + quote + '"', source)[0]['status'], 'verbatim')
                self.assertEqual(check('"' + quote + '"', quote)[0]['status'], 'verbatim')

    def test_word_edges_do_not_match_partial_words(self):
        for source in ['We need to undo the change', 'do the changes now']:
            self.assertNotEqual(check('"do the change"', source)[0]['status'], 'verbatim')
        self.assertEqual(check('"do the change"', 'We should do the change now')[0]['status'], 'verbatim')

    def test_combining_marks_cannot_be_dropped_at_quote_end(self):
        for mark in ('\u0301', '\u093e', '\u20dd'):
            with self.subTest(mark=mark):
                quote = 'We met at the cafe'
                source = quote + mark + ' yesterday.'
                self.assertNotEqual(check('"' + quote + '"', source)[0]['status'], 'verbatim')
                full = check('"' + quote + mark + '"', source)[0]
                self.assertEqual(full['status'], 'verbatim')
                self.assertEqual(full['source_text'], quote + mark)

    def test_matches_cannot_start_after_a_combining_mark(self):
        for mark in ('\u0301', '\u093e', '\u20dd'):
            with self.subTest(mark=mark):
                quote = 'We met at the cafe'
                source = 'e' + mark + quote + ' yesterday.'
                self.assertNotEqual(check('"' + quote + '"', source)[0]['status'], 'verbatim')
                self.assertEqual(check('"e' + mark + quote + '"', source)[0]['status'], 'verbatim')

    def test_quote_edges_that_are_marks_still_require_whole_words(self):
        pairs = [
            ('We met at the cafe\u0301', 'We met at the cafe\u0301\u20dd yesterday.'),
            ('\u0301We met at the cafe', 'e\u0301We met at the cafe yesterday.'),
            ('We met at the café', 'We met at the cafe\u0301 yesterday.'),
        ]
        for quote, source in pairs:
            with self.subTest(quote=quote, source=source):
                self.assertNotEqual(check('"' + quote + '"', source)[0]['status'], 'verbatim')
                self.assertEqual(check('"' + quote + '"', quote)[0]['status'], 'verbatim')

    def test_cli_coverage_receipt_and_exit_codes(self):
        with tempfile.TemporaryDirectory() as directory:
            draft, source = Path(directory, 'draft.md'), Path(directory, 'source.md')
            draft.write_text('---\ntitle: "a normal front matter title"\n---\n"' + PHRASE + '"', encoding='utf-8')
            source.write_text(PHRASE, encoding='utf-8')
            args = [sys.executable, str(ROOT/'scripts/check_quotes.py'), str(draft), '--source', str(source)]
            plain = subprocess.run(args, capture_output=True, text=True)
            scoped = subprocess.run(args + ['--exclude-lines', '1:3', '--json'], capture_output=True, text=True)
            self.assertEqual(plain.returncode, 1)
            self.assertEqual(scoped.returncode, 0, scoped.stderr)
            self.assertEqual([r['status'] for r in json.loads(scoped.stdout)], ['verbatim', 'excluded'])
            for value in ['0:1', '3:1', '1:100', 'oops']:
                bad = subprocess.run(args + ['--exclude-lines', value], capture_output=True, text=True)
                self.assertEqual(bad.returncode, 2, bad.stdout)
