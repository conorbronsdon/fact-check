"""Issue #13 residual: nested straight quotes must never yield a partial verbatim."""
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from check_quotes import check, find_quotes  # noqa: E402

PHRASE = 'we never lost a single customer record'
OTHER = 'the system is safe to deploy'
REPRO = 'She said "the system "will never lose your data" is ready today".'

NESTED = {
    'issue reproduction': REPRO,
    'inner quote at start': 'He wrote ""never again" was the motto for years".',
    'inner quote at end': 'He said "they called it "the best year we ever had"".',
    'two inner quotes': 'She said "the memo "was clear" and "was final" in every respect".',
    'depth three': 'She said "the memo "quoted the line "we never lose data" in full" last week".',
    'inner closer without a following space': 'She said "the system "will never lose your data"is ready today".',
    'apostrophes inside': 'She said "it\'s the team\'s "best release in years" so far today".',
    'single-quoted YAML wrapper': "excerpt: 'She said \"the system \"will never lose your data\" is ready today\"'",
    'curly inner in straight outer': 'She said "the system “will never lose your data” is ready today".',
    'straight inner in curly outer': 'She said “the system "will never lose your data" is ready today”.',
}


def fragments(draft):
    """Every stretch of text between two quote delimiters, collapsed."""
    marks = [m.start() for m in re.finditer('["“”]', draft)]
    for i, a in enumerate(marks):
        for b in marks[i + 1:]:
            text = ' '.join(draft[a + 1:b].replace('"', ' ').replace('“', ' ').replace('”', ' ').split())
            if len(text) >= 6:
                yield text


class NestedStraightQuotes(unittest.TestCase):
    def test_issue_reproduction_is_not_verbatim(self):
        results = check(REPRO, 'is ready today')
        self.assertNotIn('verbatim', [r['status'] for r in results])
        self.assertIn('ambiguous', [r['status'] for r in results])
        self.assertEqual(find_quotes(REPRO), [])

    def test_no_fragment_of_a_nested_run_is_ever_verbatim(self):
        for name, draft in NESTED.items():
            for fragment in fragments(draft):
                with self.subTest(case=name, source=fragment):
                    statuses = [r['status'] for r in check(draft, fragment)]
                    self.assertNotIn('verbatim', statuses)
                    self.assertIn('ambiguous', statuses)

    def test_nesting_is_detected_when_the_inner_closer_is_unspaced(self):
        # Only nesting detection catches this: no delimiter is a stray closer.
        draft = 'She said "the system "will never lose your data"is ready today".'
        self.assertEqual([r['status'] for r in check(draft, 'is ready today')], ['ambiguous'])

    def test_nested_run_is_reported_with_its_line_and_span(self):
        results = check('Intro line.\n' + REPRO, 'A source.')
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['line'], 2)
        self.assertIn('nested', results[0]['reason'].lower())
        self.assertIn('will never lose your data', results[0]['span'])

    def test_quotes_after_a_nested_run_are_still_checked(self):
        for draft in NESTED.values():
            with self.subTest(draft=draft):
                results = check(draft + ' Later she said "' + PHRASE + '".', PHRASE)
                self.assertEqual([r['status'] for r in results], ['verbatim', 'ambiguous'])

    def test_unclosed_nested_run_stops_at_a_blank_line(self):
        draft = 'She said "the system "will never lose your data" is ready.\n\nThen "' + PHRASE + '".'
        results = check(draft, 'is ready.')
        self.assertNotIn('verbatim', [r['status'] for r in results][1:])
        self.assertEqual(check(draft, PHRASE)[0]['status'], 'verbatim')
        self.assertIn('ambiguous', [r['status'] for r in check(draft, PHRASE)])

    def test_mixed_run_does_not_pair_prose_between_quotes(self):
        draft = ('She said "the system “will never lose your data” is ready" and the vendor '
                 'said "' + PHRASE + '".')
        self.assertNotIn('verbatim', [r['status'] for r in check(draft, 'and the vendor said')])
        self.assertEqual([r['status'] for r in check(draft, PHRASE)], ['verbatim', 'ambiguous'])

    def test_stray_closing_straight_quote_does_not_open_a_pair(self):
        draft = 'The record was 12" wide and the vendor said "' + PHRASE + '".'
        self.assertNotIn('verbatim', [r['status'] for r in check(draft, 'wide and the vendor said')])
        self.assertEqual([r['status'] for r in check(draft, PHRASE)], ['verbatim', 'ambiguous'])

    def test_lone_straight_quote_makes_its_paragraph_ambiguous_not_clean(self):
        # Known coverage cost: a stray delimiter earlier in the paragraph
        # swallows the later quote, which is reported rather than checked.
        draft = 'Type the `"` key, then she said "' + PHRASE + '".\n\nThen "' + OTHER + '".'
        results = check(draft, PHRASE + ' ' + OTHER)
        self.assertEqual([r['status'] for r in results], ['verbatim', 'ambiguous'])
        self.assertEqual(results[0]['quote'], OTHER)
        self.assertEqual(results[1]['line'], 1)

    def test_cli_exits_one_for_the_reproduction(self):
        with tempfile.TemporaryDirectory() as directory:
            draft, source = Path(directory, 'draft.md'), Path(directory, 'source.md')
            draft.write_text(REPRO, encoding='utf-8')
            source.write_text('is ready today', encoding='utf-8')
            run = subprocess.run([sys.executable, str(ROOT / 'scripts/check_quotes.py'), str(draft),
                                  '--source', str(source), '--json'], capture_output=True, text=True)
            self.assertEqual(run.returncode, 1, run.stderr)
            self.assertEqual([r['status'] for r in json.loads(run.stdout)], ['ambiguous'])


class AdjacentAndShortQuotesStayChecked(unittest.TestCase):
    """Must-not-fire controls: ordinary quotes keep their verbatim result."""

    def assert_all_verbatim(self, draft, source, count):
        results = check(draft, source)
        self.assertEqual([r['status'] for r in results], ['verbatim'] * count, results)

    def test_adjacent_quotes_with_prose_between(self):
        source = PHRASE + '. Separately, ' + OTHER + '.'
        for draft in ('"' + PHRASE + '" and "' + OTHER + '"',
                      '"' + PHRASE + '", then "' + OTHER + '".',
                      '"' + PHRASE + '","' + OTHER + '"',
                      '"' + PHRASE + '" "' + OTHER + '"',
                      '("' + PHRASE + '") and ("' + OTHER + '")',
                      '"' + PHRASE + '"\n"' + OTHER + '"'):
            with self.subTest(draft=draft):
                self.assert_all_verbatim(draft, source, 2)

    def test_short_pairs_next_to_an_eligible_quote(self):
        for draft in ('He said "yes" and "no" and then "' + PHRASE + '".',
                      '"ok" "' + PHRASE + '" "fine"',
                      'Words like "a" or "an" precede "' + PHRASE + '".',
                      'An empty "" pair, then "' + PHRASE + '".'):
            with self.subTest(draft=draft):
                self.assert_all_verbatim(draft, PHRASE, 1)

    def test_closing_punctuation_and_apostrophes(self):
        for draft in ('She said, "' + PHRASE + '."', 'Did she say "' + PHRASE + '"?',
                      'The "' + PHRASE + '"\'s author', 'She said "' + PHRASE + '" — twice.',
                      'She said:"' + PHRASE + '"', 'She said "' + PHRASE.replace('never', 'never\n') + '".'):
            with self.subTest(draft=draft):
                self.assert_all_verbatim(draft, PHRASE + '.', 1)

    def test_quote_containing_apostrophes(self):
        quote = "it's the team's best release so far"
        self.assert_all_verbatim('She said "' + quote + '".', quote, 1)
        self.assert_all_verbatim('She said "' + quote.replace("'", '’') + '".', quote, 1)

    def test_curly_outer_with_single_inner_quotes_is_supported(self):
        quote = 'she called it ‘the best year’ for the team'
        self.assert_all_verbatim('“' + quote + '”', quote, 1)
        self.assert_all_verbatim('"' + quote + '"', quote, 1)


class Issue16RegressionGuards(unittest.TestCase):
    """Behavior fixed by #16 that the nesting change must keep."""

    def test_single_quoted_yaml_with_double_quoted_phrase(self):
        results = check("---\nexcerpt: 'She said \"" + PHRASE + "\"'\n---", PHRASE)
        self.assertEqual([r['status'] for r in results], ['verbatim'])

    def test_issue13_hidden_prose_examples_are_never_clean(self):
        for draft in ('---\nsummary: >\n  She said "' + PHRASE + '".\n---',
                      '---\nexcerpt: "She said “' + PHRASE + '”"\n---',
                      'The users` data is safe; she said "' + PHRASE + '" and that`s it.',
                      'It `s a live claim: "' + PHRASE + '" said she` today.'):
            with self.subTest(draft=draft):
                results = check(draft, 'A source.')
                self.assertTrue(results)
                self.assertNotIn('verbatim', [r['status'] for r in results])

    def test_explicit_exclusion_of_a_nested_line_stays_reported(self):
        draft = REPRO + '\nShe said "' + PHRASE + '".'
        results = check(draft, PHRASE, exclude_lines=[(1, 1)])
        self.assertEqual([r['status'] for r in results], ['verbatim', 'excluded'])
        self.assertEqual((results[1]['line'], results[1]['end_line']), (1, 1))
        self.assertEqual([r['status'] for r in check(draft, PHRASE)], ['verbatim', 'ambiguous'])

    def test_nested_run_cannot_pair_across_an_exclusion(self):
        draft = 'She said "the system "will never\nexcluded line\nlose your data" is ready today".'
        results = check(draft, 'is ready today', exclude_lines=[(2, 2)])
        self.assertNotIn('verbatim', [r['status'] for r in results])
        self.assertIn('excluded', [r['status'] for r in results])

    def test_short_pair_does_not_consume_the_following_quote(self):
        draft = 'He said "yes" and then he remarked "we achieved 100 percent growth".'
        self.assertEqual([q['quote'] for q in find_quotes(draft)], ['we achieved 100 percent growth'])

    def test_escaped_and_mixed_delimiters_still_need_review(self):
        for draft in ('She said \\"' + PHRASE + '\\".', '“' + PHRASE + '"'):
            with self.subTest(draft=draft):
                self.assertIn('ambiguous', [r['status'] for r in check(draft, PHRASE)])


if __name__ == '__main__':
    unittest.main()
