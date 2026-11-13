#!/usr/bin/env python3
"""Run representative quote-checker mutations in disposable repository copies."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
MUTATIONS = [
    (
        'lost Unicode mark boundary guard',
        ' or unicodedata.category(char).startswith("M")',
        '',
        'test_quote_scope.ScopeContract.test_combining_marks_cannot_be_dropped_at_quote_end',
    ),
    (
        'implicit inline-code masking',
        '    text = draft\n',
        '    text = re.sub(r"`[^`]+`", lambda m: " " * len(m.group(0)), draft)\n',
        'test_quote_scope.ScopeContract.test_issue13_hidden_prose_is_never_clean',
    ),
    (
        'lost exclusion receipt',
        '    for receipt in receipts:\n',
        '    for receipt in []:\n',
        'test_quote_scope.ScopeContract.test_explicit_metadata_and_code_exclusions_are_visible',
    ),
    (
        'cross-gap quote pairing',
        '        if masked[i]:\n            if opening is not None:',
        '        if masked[i]:\n            if False:',
        'test_quote_scope.ScopeContract.test_exclusion_does_not_pair_delimiters_across_a_gap',
    ),
    (
        'discarded exact-match punctuation',
        '    for i, char in enumerate(text):\n',
        '    for i, char in enumerate(text):\n        if char in ",.%$":\n            continue\n',
        'test_quote_scope.ScopeContract.test_character_comparison_keeps_internal_spacing_and_numeric_edges',
    ),
    (
        'lost numeric boundary guard',
        '        if not (word_left or word_right or number_left or number_right):',
        '        if not (word_left or word_right):',
        'test_quote_scope.ScopeContract.test_character_comparison_keeps_internal_spacing_and_numeric_edges',
    ),
    (
        'length filter steals a short pair',
        '        opening = None\n    if opening is not None:',
        '        if len(quote) >= 12:\n            opening = None\n    if opening is not None:',
        'test_quote_redesign.QuoteBoundaries.test_short_pair_does_not_consume_the_following_quote',
    ),
]


def main():
    original = (ROOT/'scripts/check_quotes.py').read_text(encoding='utf-8')
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    failed = False
    for name, old, new, test in MUTATIONS:
        if original.count(old) != 1:
            print(f'ERROR: mutation anchor for {name} occurs {original.count(old)} times')
            failed = True
            continue
        with tempfile.TemporaryDirectory(prefix='quote-mutation-') as directory:
            root = Path(directory)
            for path in ['scripts', 'tests', 'evals/drafts']:
                shutil.copytree(ROOT/path, root/path, ignore=shutil.ignore_patterns('__pycache__'))
            (root/'scripts/check_quotes.py').write_text(original.replace(old, new), encoding='utf-8')
            proc = subprocess.run([sys.executable, '-m', 'unittest', test], cwd=root/'tests',
                                  env=env, capture_output=True, text=True)
            killed = proc.returncode == 1 and 'FAIL:' in proc.stderr and 'ERROR:' not in proc.stderr
            print(f'{"KILLED" if killed else "FAILED CONTROL"}: {name}: {test}')
            if not killed:
                print(proc.stdout + proc.stderr)
                failed = True
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
