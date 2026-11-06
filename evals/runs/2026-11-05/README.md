# Eval run, 2026-11-05

Raw logs behind the tables in [`../../README.md`](../../README.md). One run per arm, same model.

- `skill-*.md`: an agent given `SKILL.md` in `check` mode.
- `base-*.md`: an agent given a plain prompt ("fact-check this", one row per claim, ✅/⚠️/❌).

Neither arm could read `answers/`. Re-score any log:

```bash
python3 scripts/score_log.py evals/answers/episode-launch.json evals/runs/2026-11-05/base-episode-launch.md
```

The logs are model output, kept as evidence. Their source URLs were not re-checked after the run.
