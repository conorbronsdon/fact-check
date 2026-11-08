# Proof: what the evals show so far

This page reports every scored eval run, both arms, including the drafts where the skill made no difference. Everything here comes from saved logs, so the scores reproduce without calling a model.

Reproduce it in one command, no dependencies:

```bash
for arm in base skill; do for d in tech-history leaders-promo episode-launch; do printf '%-5s %-15s ' $arm $d; python3 scripts/score_log.py evals/answers/$d.json evals/runs/2026-11-05/$arm-$d.md | head -1; done; done
```

## Result (runs from 2026-11-05, one run per arm)

`base` is a plain prompt ("fact-check this, one row per claim, ✅/⚠️/❌"). `skill` is the same model given `SKILL.md`. Neither could read `evals/answers/`.

| Draft | Arm | Planted errors caught | False alarms | Overclaims | Agreement with key | Verdicts with a source link |
|---|---|---:|---:|---:|---:|---:|
| `tech-history` | base | 5/5 | 0 | 0 | 1.0 | 1/9 |
| `tech-history` | skill | 5/5 | 0 | 0 | 1.0 | 9/9 |
| `leaders-promo` | base | 2/2 | 0 | 0 | 1.0 | 0/6 |
| `leaders-promo` | skill | 2/2 | 0 | 0 | 1.0 | 6/6 |
| `episode-launch` | base | 3/3 | 0 | 2 | 0.714 | 0/7 |
| `episode-launch` | skill | 3/3 | 0 | 0 | 1.0 | 3/7 |

## What this does and does not show

- **No lift on famous facts.** On `tech-history` and `leaders-promo` both arms caught every planted error with no false alarms. A strong model knows these facts. The only difference is evidence: the skill run linked a source for every verdict; the plain run linked one of 15.
- **The skill's one measured difference is overclaims.** On `episode-launch`, the plain run marked two claims ✅ that only the guest's own words support. The skill run kept them ⚠️.
- **One run per arm is a direction, not a measurement.** No spread is reported because there is none to report. This page will not state a lift until each arm has at least 3 runs per draft.
- **The logs' source URLs were not re-checked** after the run. A link counts as present, not as correct.

## Not yet run

`career-years`, `funding-roundup`, `survey-stats` and `episode-recap` were built to separate the arms: changing figures, tenure arithmetic, dropped populations, misheard names and title drift, where memory is weak or no help. They have answer keys and no runs. `evals/README.md` ("Next runs") has the run and scoring steps. When runs land, add their rows here with the min, median and max across runs.
