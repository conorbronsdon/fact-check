# Agent instructions: fact-check

This repo ships one skill, `SKILL.md`, plus an optional claim extractor in `scripts/`.

## Layout

- `SKILL.md`: the skill. The only file consumers need.
- `scripts/extract_claims.py`: stdlib-only extractor the skill runs as a floor before reading the draft.
- `tests/test_extract_claims.py`: must-fire and must-not-fire cases for the extractor. Run with `python3 -m unittest discover -s tests -v`.
- `scripts/check_quotes.py`: stdlib-only quote checker. Scans all text by default; explicit line exclusions appear in its report. Exit 1 for results needing review, 2 on bad input.
- `tests/test_check_quotes.py`, `tests/test_quote_redesign.py`, `tests/test_quote_scope.py`, `tests/test_quote_nesting.py`: quote matching, context, scope, and nested-delimiter regression controls.
- `scripts/mutate_quotes.py`: representative mutation checks for the quote checker, run in disposable copies.
- `scripts/score_log.py`: stdlib-only scorer that grades a fact-check log against an answer key. Exit 1 below `--min-recall`, 2 on bad input.
- `tests/test_score_log.py`: scorer tests, plus a check that every answer-key `match` string appears exactly once in its draft.
- `evals/`: drafts with planted errors (`drafts/`) and answer keys (`answers/`). Agents running an eval must not read `answers/`. Use only stable, well-documented facts so keys don't go stale.
- `PROOF.md`: every scored eval run, both arms, with one command that re-scores the saved logs. Update it when runs are added; never drop a row because it is unflattering.
- `examples/draft.md`: a sample draft for trying the skill and extractor. It contains deliberately unchecked claims; do not "fix" them.
- `docs/social-preview.png`: GitHub social preview, 1280x640. A static image; replace it by uploading a new PNG in repo Settings too.
- `.claude-plugin/marketplace.json`: single-plugin marketplace so `/plugin marketplace add conorbronsdon/fact-check` works.
- `.claude-plugin/plugin.json`: Claude Code plugin manifest. Its `version` must match the `SKILL.md` frontmatter `version`.

## Rules

- Every new extractor pattern ships with a must-fire test and a must-not-fire test. Checked by review, not tooling.
- Keep the extractor dependency-free and Python 3.9-compatible. CI runs 3.9 and 3.13 (`.github/workflows/ci.yml`).
- Keep the SKILL.md frontmatter complete (name, description, version, license, compatibility, metadata). CI validates it with agent-skill-builder's `validate_skill.py --profile agentskills`.
- The skill flags and never edits the user's draft. Do not add a mode that rewrites claims.
- A new verification rule should come with an eval draft that tests it (a planted error the rule should catch, and a true claim it must not flag).
- When mutation-testing a script, set `PYTHONDONTWRITEBYTECODE=1`, or a same-size edit restored within the same second can leave a stale `.pyc` that runs the mutant.
- Version bumps follow semver on skill content: rule or verdict changes are minor, wording fixes are patch. Update `SKILL.md`, `.claude-plugin/plugin.json`, and `CHANGELOG.md` together.
