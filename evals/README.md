# Evals

Drafts with planted errors, an answer key for each, and a scorer. Use them to check whether a change to `SKILL.md` makes the skill catch more errors, and to compare the skill against a plain "fact-check this" prompt.

| Draft | Planted errors | What they test |
|---|---|---|
| `drafts/tech-history.md` | 5 of 9 claims | A wrong year, a real date paired with the wrong employer, a misattributed quote, a false superlative, a survey figure with the wrong population |
| `drafts/leaders-promo.md` | 2 of 6 claims, one of them an internal contradiction | A real founding year paired with the wrong prior employer, and a date the draft states two ways |
| `drafts/episode-launch.md` + `episode-launch.transcript.md` | 3 of 7 claims, plus 2 that only the guest supports | A misquote checked against the transcript, a host-said-it error (Kubernetes in 2005) that the transcript "confirms", a headcount the transcript contradicts, and bio claims about an invented guest that must not be marked ✅ |
| `drafts/career-years.md` | 3 of 6 claims, plus 1 that only the writer supports | Two wrong tenures (including a right CEO year paired with a wrong span), a real subscriber figure tied to the wrong years, and an invented speaker's bio that must not be marked ✅ |
| `drafts/funding-roundup.md` | 2 of 5 claims | Two changing figures presented as current (a 2021 valuation, a 2023 user count), next to a valuation dated to its own round that must not be marked 🕰️ |
| `drafts/survey-stats.md` | 2 of 4 claims | A survey figure with the population and wording dropped, a forecast reported as a finding, and a same-survey figure quoted correctly that must not be flagged |
| `drafts/episode-recap.md` + `episode-recap.transcript.md` + `episode-recap.notes.md` | 4 of 8 claims, plus a title drift (🔀 only, so it counts toward agreement, not recall) and 2 that only the guest supports | Title drift against the tracker, a guest title written two ways, a guest's figure ten times the company's own published one, two names copied from an automatic transcript, and one name the draft spelled right where the transcript did not |

The last four drafts come from defect types found in a podcast's real pre-publish fact-check logs: wrong employer years in a speaker bio, a subscriber count from after the guest's tenure, a valuation from an old round, a survey denominator dropped, a misheard company name copied from the transcript, a guest's figure larger than the employer's own, and an episode title that drifted between the tracker and the copy. Names, companies and figures are swapped for invented ones wherever the error doesn't depend on a real public fact. Where it does, the key uses a well-documented public figure instead of the original.

The true claims are there on purpose. Flagging one of them as ❌ counts as a false alarm. Marking a claim ✅ when the key says only the subject or the writer's notes support it counts as an **overclaim**. That is the failure the episode-launch draft is built to catch, and memory can't help with it.

The facts chosen are stable and well documented, so the key should not go stale. If a source changes, fix the key and say why in its `why` field.

## Run

1. Give an agent the skill and one draft, plus any `companions` the key lists (as the writer's supplied files). Do not let it see `answers/`. Save its log (the markdown table) to a file.
2. Score it:

```bash
python3 scripts/score_log.py evals/answers/tech-history.json log.md
```

It prints planted errors caught, recall, false alarms, and agreement with the key, then one line for each claim that disagrees with the key.

3. For new baseline runs, give the same draft and companion files with the plain prompt saved in `baseline-prompt.txt`; it lists the same six verdict labels as the skill without supplying the skill rules. Score the log the same way. The 2026-11-05 historical baseline used a three-label prompt, so those scores are not directly comparable to new runs using the six-label prompt.

`--min-recall 0.8` makes the scorer exit 1 below that recall, so it can gate a change. The claim cell must quote the draft text; the scorer matches each key entry by substring.

## First run (2026-11-05)

One run each on both drafts; the run author reports the same model in both arms. The saved logs do not record model identity, full prompts or tool traces:

| | Planted errors caught | False alarms | Verdicts with a source link | Web searches |
|---|---|---|---|---|
| Plain prompt | 7/7 | 0 | 1/15 | 1 |
| With the skill | 7/7 | 0 | 15/15 | 15, plus about 20 page fetches and 6 archive links |

Both runs caught everything. These drafts use famous facts, so a strong model gets them right from memory. The saved logs differ in source links: the plain run linked one of 15 verdicts, while the skill run linked all 15. The historical plain prompt did not explicitly request source URLs, so the comparison is confounded by prompt format and does not establish source quality. A verdict from memory is right until the day it isn't, and the writer has no way to tell which day that is. The next drafts should use errors that memory gets wrong: recent figures, less famous people, numbers that changed.

## Second run (2026-11-05): episode-launch, with the transcript

| | Planted errors caught | Overclaims | Agreement with key | Verdicts with a source link |
|---|---|---|---|---|
| Plain prompt | 3/3 | 2 | 5/7 | 0/7 |
| With the skill | 3/3 | 0 | 7/7 | 3/7 |

This is the draft memory can't help with, and it is where the skill made a difference. The plain run marked the guest's title and her Stripe tenure ✅ because the transcript said so. The skill run kept both ⚠️ ("a transcript is not evidence that a bio is true"), checked the quote word for word against the transcript, and split it into an attribution row and a content row. Both runs caught the Kubernetes-in-2005 line, and only the skill run linked a dated source for it. One run each: a direction, not a measurement.

## Next runs

The four newer drafts have no runs yet. Use `baseline-prompt.txt` for the baseline arm; give both arms the same model, tools, web access, draft and companions, and record their exact prompts, model IDs and tool access. The title-drift key accepts only `inconsistent`: `incorrect` is counted as a false alarm because the supplied files do not establish which title is right. Before the README states any lift, run each arm at least 3 times per draft and report the spread (min, median, max), not the best run. Save logs as `evals/runs/<date>/<arm>-<draft>-<n>.md`, then score them all. This loop is for numbered future runs; use the command in `PROOF.md` for the unnumbered historical files:

```bash
# Set this to the actual run directory; filenames must be <arm>-<draft>-<n>.md.
run_dir=evals/runs/YYYY-MM-DD
found=0
failed=0
for f in "$run_dir"/*.md; do
  [ -f "$f" ] || continue
  found=1
  stem=${f##*/}; stem=${stem%.md}
  arm=${stem%%-*}; number=${stem##*-}
  case "$arm:$number" in
    base:*|skill:*) ;;
    *) printf 'Invalid run name: %s\n' "$f" >&2; failed=1; continue ;;
  esac
  case "$number" in
    ''|*[!0-9]*) printf 'Invalid run number: %s\n' "$f" >&2; failed=1; continue ;;
  esac
  draft=${stem#*-}; draft=${draft%-*}
  key="evals/answers/$draft.json"
  if [ ! -f "$key" ]; then
    printf 'Missing key for %s: %s\n' "$f" "$key" >&2
    failed=1
    continue
  fi
  printf '%s\n' "$f"
  python3 scripts/score_log.py "$key" "$f" || failed=1
done
[ "$found" -eq 1 ] || { printf 'No runs in %s\n' "$run_dir" >&2; failed=1; }
[ "$failed" -eq 0 ]
```

## Limits

Seven short drafts are a smoke test, not a benchmark. Strong models catch famous errors without help, so most of the difference between skill and baseline shows up in the harder cases: number plus context, population, attribution, and internal consistency. Add drafts in that style when you add rules.
