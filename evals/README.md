# Evals

Drafts with planted errors, an answer key for each, and a scorer. Use them to check whether a change to `SKILL.md` makes the skill catch more errors, and to compare the skill against a plain "fact-check this" prompt.

| Draft | Planted errors | What they test |
|---|---|---|
| `drafts/tech-history.md` | 5 of 9 claims | A wrong year, a real date paired with the wrong employer, a misattributed quote, a false superlative, a survey figure with the wrong population |
| `drafts/leaders-promo.md` | 2 of 6 claims, plus one internal contradiction | A real founding year paired with the wrong prior employer, and a date the draft states two ways |

The true claims are there on purpose. Flagging one of them as ❌ counts as a false alarm.

The facts chosen are stable and well documented, so the key should not go stale. If a source changes, fix the key and say why in its `why` field.

## Run

1. Give an agent the skill and one draft. Do not let it see `answers/`. Save its log (the markdown table) to a file.
2. Score it:

```bash
python3 scripts/score_log.py evals/answers/tech-history.json log.md
```

It prints planted errors caught, recall, false alarms, and agreement with the key, then one line for each claim that disagrees with the key.

3. For a baseline, run the same draft with a plain prompt ("fact-check this, one row per claim, ✅/⚠️/❌") and score that log the same way.

`--min-recall 0.8` makes the scorer exit 1 below that recall, so it can gate a change. The claim cell must quote the draft text; the scorer matches each key entry by substring.

## First run (2026-11-05)

One run each, same model, both drafts:

| | Planted errors caught | False alarms | Verdicts with a source link | Web searches |
|---|---|---|---|---|
| Plain prompt | 7/7 | 0 | 1/15 | 1 |
| With the skill | 7/7 | 0 | 15/15 | 15, plus about 20 page fetches and 6 archive links |

Both runs caught everything. These drafts use famous facts, so a strong model gets them right from memory. What the skill changed is the evidence: the plain run named sources it never opened, and the skill run linked a source for every verdict. A verdict from memory is right until the day it isn't, and the writer has no way to tell which day that is. The next drafts should use errors that memory gets wrong: recent figures, less famous people, numbers that changed.

## Limits

Two short drafts are a smoke test, not a benchmark. Strong models catch famous errors without help, so most of the difference between skill and baseline shows up in the harder cases: number plus context, population, attribution, and internal consistency. Add drafts in that style when you add rules.
