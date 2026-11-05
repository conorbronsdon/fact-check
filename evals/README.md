# Evals

Drafts with planted errors, an answer key for each, and a scorer. Use them to check whether a change to `SKILL.md` makes the skill catch more errors, and to compare the skill against a plain "fact-check this" prompt.

| Draft | Planted errors | What they test |
|---|---|---|
| `drafts/tech-history.md` | 5 of 9 claims | A wrong year, a real date paired with the wrong employer, a misattributed quote, a false superlative, a survey figure with the wrong population |
| `drafts/leaders-promo.md` | 2 of 6 claims, plus one internal contradiction | A real founding year paired with the wrong prior employer, and a date the draft states two ways |
| `drafts/episode-launch.md` + `episode-launch.transcript.md` | 3 of 7 claims, plus 2 that only the guest supports | A misquote checked against the transcript, a host-said-it error (Kubernetes in 2005) that the transcript "confirms", a headcount the transcript contradicts, and bio claims about an invented guest that must not be marked ✅ |

The true claims are there on purpose. Flagging one of them as ❌ counts as a false alarm. Marking a claim ✅ when the key says only the subject or the writer's notes support it counts as an **overclaim**. That is the failure the episode-launch draft is built to catch, and memory can't help with it.

The facts chosen are stable and well documented, so the key should not go stale. If a source changes, fix the key and say why in its `why` field.

## Run

1. Give an agent the skill and one draft, plus any `companions` the key lists (as the writer's supplied files). Do not let it see `answers/`. Save its log (the markdown table) to a file.
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

## Second run (2026-11-05): episode-launch, with the transcript

| | Planted errors caught | Overclaims | Agreement with key | Verdicts with a source link |
|---|---|---|---|---|
| Plain prompt | 3/3 | 2 | 5/7 | 0/7 |
| With the skill | 3/3 | 0 | 7/7 | 3/7 |

This is the draft memory can't help with, and it is where the skill made a difference. The plain run marked the guest's title and her Stripe tenure ✅ because the transcript said so. The skill run kept both ⚠️ ("a transcript is not evidence that a bio is true"), checked the quote word for word against the transcript, and split it into an attribution row and a content row. Both runs caught the Kubernetes-in-2005 line, and only the skill run linked a dated source for it. One run each: a direction, not a measurement.

## Limits

Two short drafts are a smoke test, not a benchmark. Strong models catch famous errors without help, so most of the difference between skill and baseline shows up in the harder cases: number plus context, population, attribution, and internal consistency. Add drafts in that style when you add rules.
