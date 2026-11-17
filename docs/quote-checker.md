# Quote checker scope contract

This checker helps a reader compare wording with a local source. It does not verify facts, speakers, attribution, or meaning. It never edits the draft.

## Why scan all text?

A backtick may delimit code or be a mistaken apostrophe. A front matter value may be a title or contain a publishable quotation. A dependency-free scanner cannot infer the author's intent safely from these markers. Earlier drafts (#8 and #12) masked text based on such guesses and could report a clean result while hiding a false quotation (#13).

This implementation makes scope an explicit input: **all text is scanned unless the caller names inclusive line ranges to exclude**. There is no Markdown or YAML parser. Fences, comments, backticks and metadata keys have no power to suppress scanning. Malformed Markdown without quotation marks is irrelevant to quote scanning and does not itself cause a warning.

## Quotes and embedded quotation marks

Straight `"` and curly `“…”` delimiters pair before the 12-character minimum is applied. Short pairs cannot steal the delimiters of a later eligible quote. Single quotation marks are literal content, so a valid YAML scalar such as `excerpt: 'She said "we never lost a single customer record"'` scans its double-quoted phrase normally.

A double-quoted metadata value containing curly quotes is nested input, not an automatic exclusion. Mixed straight/curly nesting, escaped and unbalanced delimiters produce `ambiguous` diagnostics and exit 1. Read the original input; a diagnostic is not a claim that the YAML or Markdown is invalid. An unmatched delimiter cannot pair across a blank line or an explicitly excluded range. Delimiters pair on a stack. A straight `"` is read by its neighbours, like Markdown emphasis flanking: preceded by space, punctuation or the line start and followed by text, it opens; preceded by text and followed by space, punctuation or the end, it closes; otherwise either. An opener-shaped straight quote inside an open quote starts a nested run. The whole run, from the outermost opener to its matching closer, is reported once as `ambiguous` with the unchecked span, and **no fragment of it is checked**, because sequential pairing cannot tell nested from adjacent quotations (#13). For example, `She said "the system "will never lose your data" is ready today".` is one ambiguous result, never a `verbatim` result for `is ready today`. Curly/straight mixtures are handled the same way. A closer-shaped straight quote with no open quote (an inch mark such as `12"`) is reported as an unmatched closing quote and cannot open a pair that captures the prose up to the next quotation.

Adjacent quotations (`"one" and "two"`, `"one","two"`), short pairs, and closing punctuation keep their ordinary results. Known costs of refusing to guess: a typo such as `"done,"he said` reads as nested, and a lone stray straight quote earlier in a paragraph (for example a `"` inside a code span) leaves the rest of the paragraph in one unclosed, ambiguous run, so a later well-formed quote there is reported rather than checked. Both still exit 1; neither produces a `verbatim` result. Use curly outer quotes and single inner quotes, or review such input manually. Only supported double-quoted spans are checked. Single-quoted prose, blockquotes without double quotes, and quotations shorter than 12 characters still need human inspection.

## Ordinary metadata and code

Given this draft:

````text
---
title: "A normal article title"
---
```python
print("a code string unrelated to the transcript")
```
She said "we never lost a single customer record".
````

The default scans all three double-quoted spans. If the header and code are intentionally out of scope, use:

```bash
python3 scripts/check_quotes.py draft.md --source transcript.md --exclude-lines 1:3 --exclude-lines 4:6
```

The report then includes the prose result at line 7 and two `excluded` records with the exact ranges and **NOT CHECKED** reasons. JSON includes those records too. The exit code evaluates checked content only: explicit exclusions are not verification. Even excluding the entire file produces an exclusion receipt, never an empty report claiming that everything was checked. Ranges outside the file, reversed ranges, and overlapping ranges are input errors (exit 2).

For genuine inline code, omit its line explicitly only if all content on that line is intentionally outside the check. If code and publishable prose share a line, keep the line in scope and review the code-string result manually. The scanner does not guess which backticks were intended as apostrophes.

## Matching and context

`verbatim` requires exactly one bounded character substring in a blank-separated source block, after collapsing whitespace and normalizing curly apostrophes to straight apostrophes and Unicode minus to ASCII minus. Case and all other punctuation and symbols remain significant. This deliberately asks for review of formatting changes such as `10 %` versus `10%` or `US , markets` versus `US, markets`. Word and numeric boundary guards prevent matches inside a larger word, decimal, signed amount or percentage. Unicode combining marks (nonspacing, spacing-combining and enclosing) are word characters at both ends of a match, so a match cannot omit a material accent or begin inside a marked word. The full decomposed spelling can match literally; composed and decomposed spellings are not normalized into each other. Across whitespace, adjacent digit groups are conservatively treated as a possible single figure: a quote cannot end at `100` inside `100 000`, or begin at `000`. The same rule covers soft wraps and nonbreaking or thin spaces after whitespace collapse. Numeric range endpoints joined by hyphen, en dash or em dash (with optional spacing and signs) cannot be truncated either. A complete grouped figure or range still matches literally. Ordinary sentence commas, periods and dashes before prose do not by themselves continue a number. Adjacent numeric values separated only by whitespace can therefore require manual review even if they were intended as separate values.

Source line prefixes such as `March 2024:` are ordinary text. There is no guessed speaker-header grammar. A quote omitting a speaker label cannot jump over that literal label; the checker does not establish that an unlabeled line is a speaker turn. Repeated exact passages are `ambiguous`, with up to 20 candidates plus a total count. Marked edits (ellipsis or brackets) always need review, even if the same marks appear in the source.

Fuzzy token windows only suggest a similar passage (`near`) and never create a `verbatim` result. `absent` is not proof that the quotation is absent from the full recording. A displayed sentence includes hard line wraps; sentence punctuation is a context heuristic, and abbreviations or transcript formats can affect its boundaries. Read the full source for attribution and meaning.

## Exit codes

- **0**: all checked results are `verbatim`, or there are no eligible supported spans. Exclusion receipts remain visible.
- **1**: at least one `near`, `absent`, or `ambiguous` result needs review.
- **2**: invalid arguments, unreadable UTF-8 input, empty source, or invalid exclusion range.

An exit 0 is never proof that every quotation was found or that any claim is true.

## Regression controls

Run the full repository suite with `python3 -m unittest discover -s tests -v`. Quote tests preserve the earlier matching, edit-marker, numeric and context controls while replacing assertions that depended on automatic Markdown exclusions. `tests/test_quote_scope.py` exercises #13's four hidden-prose examples, valid single-quoted YAML, explicit metadata/code exclusions, interrupted pairs, escaped delimiters, numeric edges and `March 2024:` wrapping. `tests/test_quote_nesting.py` checks that no fragment of a nested straight or mixed run is ever `verbatim`, with must-not-fire controls for adjacent quotes, short pairs, apostrophes and closing punctuation.

Run `PYTHONDONTWRITEBYTECODE=1 python3 scripts/mutate_quotes.py` for representative mutations in disposable copies. Each mutant must produce an assertion failure in its relevant regression control; import or syntax failures do not count.
