# Agent instructions: fact-check

This repo ships one skill, `SKILL.md`, plus an optional claim extractor in `scripts/`.

## Layout

- `SKILL.md`: the skill. The only file consumers need.
- `scripts/extract_claims.py`: stdlib-only extractor the skill runs as a floor before reading the draft.
- `tests/test_extract_claims.py`: must-fire and must-not-fire cases for the extractor. Run with `python3 -m unittest discover -s tests -v`.
- `examples/draft.md`: a sample draft for trying the skill and extractor. It contains deliberately unchecked claims; do not "fix" them.
- `.claude-plugin/plugin.json`: Claude Code plugin manifest. Its `version` must match the `SKILL.md` frontmatter `version`.

## Rules

- Every new extractor pattern ships with a must-fire test and a must-not-fire test. Checked by review, not tooling.
- Keep the extractor dependency-free and Python 3.9-compatible. CI runs 3.9 and 3.13 (`.github/workflows/ci.yml`).
- Keep the SKILL.md frontmatter complete (name, description, version, license, compatibility, metadata). CI validates it with agent-skill-builder's `validate_skill.py --profile agentskills`.
- The skill flags and never edits the user's draft. Do not add a mode that rewrites claims.
- Version bumps follow semver on skill content: rule or verdict changes are minor, wording fixes are patch. Update `SKILL.md`, `.claude-plugin/plugin.json`, and `CHANGELOG.md` together.
