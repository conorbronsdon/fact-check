#!/usr/bin/env python3
"""Check every quote in a draft against a transcript or other source.

For "X said Y," the recording or transcript is the primary source. This
script finds each double-quoted span in the draft (straight or curly
quotes, 12+ characters, the same threshold as extract_claims.py) and looks
for it in the source after normalizing case, punctuation, and whitespace.

  verbatim  the words appear in the source, in order, with nothing changed
  near      the closest source passage is similar but not the same; it is
            printed with a word-level diff
  absent    nothing in the source is close

Each match is printed with the source sentence before and after it, since
context can change what a quote means. It checks wording only: it does not
say who is speaking or whether what they said is true. A quote with an
ellipsis or a bracketed insertion reports as near; read the diff.

Usage:
  python3 scripts/check_quotes.py draft.md --source transcript.md
  python3 scripts/check_quotes.py draft.md --source transcript.md --json
  cat draft.md | python3 scripts/check_quotes.py - --source transcript.md

Exit codes: 0 = every quote is verbatim (or there are none),
1 = at least one quote is near or absent, 2 = bad usage or unreadable input.
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
import sys

QUOTE = re.compile(r"[\"“]((?:[^\"“”\n]|\n(?![ \t]*\n)){12,}?)[\"”]")
WORD = re.compile(r"[^\W_]+(?:['’][^\W_]+)*")
FENCE = re.compile(r"^\s*(```|~~~)")
INLINE_CODE = re.compile(r"`[^`\n]*`")
HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)
SENTENCE_END = re.compile(r"[.!?]+[\"”'’)]*(?=\s)|\n")
DEFAULT_THRESHOLD = 0.6


def blank(match: re.Match) -> str:
    return re.sub(r"[^\n]", " ", match.group(0))


def strip_markup(text: str) -> str:
    """Blank out front matter, code, and HTML comments, keeping offsets."""
    lines = text.split("\n")
    end = 0
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                end = i + 1
                break
    in_code = False
    for i, line in enumerate(lines):
        fence = FENCE.match(line)
        if i < end or in_code or fence:
            lines[i] = " " * len(line)
        if fence:
            in_code = not in_code
    text = "\n".join(lines)
    text = HTML_COMMENT.sub(blank, text)
    return INLINE_CODE.sub(blank, text)


def tokens(text: str) -> list[tuple[str, int, int]]:
    """(normalized word, start, end) for each word in text."""
    out = []
    for m in WORD.finditer(text):
        norm = m.group(0).lower().replace("’", "").replace("'", "")
        out.append((norm, m.start(), m.end()))
    return out


def find_quotes(draft: str) -> list[dict]:
    text = strip_markup(draft)
    found = []
    for m in QUOTE.finditer(text):
        quote = " ".join(m.group(1).split())
        if tokens(quote):
            found.append({"line": text.count("\n", 0, m.start()) + 1, "quote": quote})
    return found


def sentence_spans(text: str) -> list[tuple[int, int]]:
    spans, start = [], 0
    for m in SENTENCE_END.finditer(text):
        if text[start:m.end()].strip():
            spans.append((start, m.end()))
        start = m.end()
    if text[start:].strip():
        spans.append((start, len(text)))
    return spans


def find_contiguous(needle: list[str], hay: list[str]) -> int:
    n = len(needle)
    for i in range(len(hay) - n + 1):
        if hay[i:i + n] == needle:
            return i
    return -1


def best_window(q: list[str], s: list[str]) -> tuple[float, int, int]:
    """Best (ratio, start, end) over source word windows.

    A word-level pass with a fixed window finds candidate regions; each is
    then refined over nearby starts and lengths with a character-level
    ratio, which forgives inflection ("start" vs "started").
    """
    n = len(q)
    q_text = " ".join(q)
    words = difflib.SequenceMatcher(autojunk=False)
    words.set_seq2(q)
    width = n + n // 2
    coarse = []
    for i in range(max(1, len(s) - n + 1)):
        words.set_seq1(s[i:i + width])
        coarse.append((words.ratio(), i))
    coarse.sort(key=lambda c: (-c[0], c[1]))
    chars = difflib.SequenceMatcher(autojunk=False)
    chars.set_seq2(q_text)
    best = (0.0, 0, 0)
    seen = set()
    for _, i in coarse[:5]:
        for start in range(max(0, i - n // 2), min(len(s), i + n // 2 + 1)):
            for length in range(max(1, n - n // 2), n + n // 2 + 1):
                end = min(len(s), start + length)
                if (start, end) in seen:
                    continue
                seen.add((start, end))
                chars.set_seq1(" ".join(s[start:end]))
                ratio = chars.ratio()
                if ratio > best[0] or (ratio == best[0] and end - start < best[2] - best[1]):
                    best = (ratio, start, end)
    return best


def widen(q: list[str], s: list[str], lo: int, hi: int) -> tuple[int, int]:
    """Grow the window while that matches more quote words, so a passage
    the draft cut ("most of our outages" -> "most outages") is shown whole."""
    def matched(a: int, b: int) -> int:
        sm = difflib.SequenceMatcher(a=s[a:b], b=q, autojunk=False)
        return sum(block.size for block in sm.get_matching_blocks())

    reach = max(2, len(q) // 2)
    current = matched(lo, hi)
    grew = True
    while grew:
        grew = False
        for side in ("left", "right"):
            best_k, best_m = 0, current
            for k in range(1, reach + 1):
                a, b = (lo - k, hi) if side == "left" else (lo, hi + k)
                if a < 0 or b > len(s):
                    break
                m = matched(a, b)
                if m > best_m:
                    best_k, best_m = k, m
            if best_k:
                lo, hi = (lo - best_k, hi) if side == "left" else (lo, hi + best_k)
                current, grew = best_m, True
    return lo, hi


def word_diff(source_words: list[str], quote_words: list[str]) -> str:
    """Source to draft: [-x-] is in the source and missing from the quote,
    {+x+} is in the quote and not in the source."""
    sm = difflib.SequenceMatcher(a=[w.lower() for w in source_words],
                                 b=[w.lower() for w in quote_words], autojunk=False)
    out = []
    for op, a1, a2, b1, b2 in sm.get_opcodes():
        if op == "equal":
            out.append(" ".join(quote_words[b1:b2]))
            continue
        if a2 > a1:
            out.append("[-" + " ".join(source_words[a1:a2]) + "-]")
        if b2 > b1:
            out.append("{+" + " ".join(quote_words[b1:b2]) + "+}")
    return " ".join(out)


def context(source: str, spans: list[tuple[int, int]], start: int, end: int) -> dict:
    first = next(i for i, (a, b) in enumerate(spans) if b > start)
    last = next(i for i, (a, b) in enumerate(spans) if b >= end)
    clip = lambda i: " ".join(source[spans[i][0]:spans[i][1]].split())
    return {
        "before": clip(first - 1) if first > 0 else None,
        "sentence": " ".join(clip(i) for i in range(first, last + 1)),
        "after": clip(last + 1) if last + 1 < len(spans) else None,
    }


def check(draft: str, source: str, threshold: float = DEFAULT_THRESHOLD) -> list[dict]:
    src_tokens = tokens(source)
    src_words = [t[0] for t in src_tokens]
    spans = sentence_spans(source)
    results = []
    for idx, item in enumerate(find_quotes(draft), 1):
        q_tokens = tokens(item["quote"])
        q_words = [t[0] for t in q_tokens]
        res = {"id": idx, "line": item["line"], "quote": item["quote"]}
        at = find_contiguous(q_words, src_words)
        if at >= 0:
            res.update(status="verbatim", score=1.0)
            lo, hi = at, at + len(q_words)
        else:
            score, lo, hi = best_window(q_words, src_words)
            res["score"] = round(score, 3)
            if score < threshold or hi <= lo:
                res["status"] = "absent"
                results.append(res)
                continue
            res["status"] = "near"
            lo, hi = widen(q_words, src_words, lo, hi)
        a, b = src_tokens[lo][1], src_tokens[hi - 1][2]
        res["source_line"] = source.count("\n", 0, a) + 1
        res["source_text"] = " ".join(source[a:b].split())
        if res["status"] == "near":
            res["diff"] = word_diff([source[t[1]:t[2]] for t in src_tokens[lo:hi]],
                                    [item["quote"][t[1]:t[2]] for t in q_tokens])
        res["context"] = context(source, spans, a, b)
        results.append(res)
    return results


def to_text(results: list[dict]) -> str:
    if not results:
        return "No quotes of 12+ characters found in the draft."
    out = []
    for r in results:
        out.append(f"#{r['id']} line {r['line']}: {r['status'].upper()}  \"{r['quote']}\"")
        if r["status"] == "absent":
            out.append(f"  no source passage is close (best similarity {r['score']:.2f})")
        else:
            if r["status"] == "near":
                out.append(f"  closest source text (line {r['source_line']}, similarity {r['score']:.2f}):")
                out.append(f"    \"{r['source_text']}\"")
                out.append(f"  diff (source -> draft): {r['diff']}")
            ctx = r["context"]
            out.append(f"  before: {ctx['before'] or '(start of source)'}")
            out.append(f"  match:  {ctx['sentence']}")
            out.append(f"  after:  {ctx['after'] or '(end of source)'}")
        out.append("")
    counts = {s: sum(r["status"] == s for r in results) for s in ("verbatim", "near", "absent")}
    out.append(f"{len(results)} quotes: {counts['verbatim']} verbatim, {counts['near']} near, "
               f"{counts['absent']} absent. Wording only: check who said it and whether it is true.")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Check draft quotes against a transcript.")
    ap.add_argument("path", help="draft to scan, or - for stdin")
    ap.add_argument("--source", required=True, help="transcript or other source text")
    ap.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD,
                    help=f"similarity at or above which a quote is near, not absent (default {DEFAULT_THRESHOLD})")
    ap.add_argument("--json", action="store_true", help="emit JSON")
    args = ap.parse_args(argv)
    if not 0 < args.threshold <= 1:
        print("error: --threshold must be in (0, 1]", file=sys.stderr)
        return 2
    try:
        draft = sys.stdin.read() if args.path == "-" else open(args.path, encoding="utf-8").read()
        source = open(args.source, encoding="utf-8").read()
    except (OSError, UnicodeDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if not tokens(source):
        print(f"error: source has no words: {args.source}", file=sys.stderr)
        return 2
    results = check(draft, source, args.threshold)
    print(json.dumps(results, indent=2, ensure_ascii=False) if args.json else to_text(results))
    return 1 if any(r["status"] != "verbatim" for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
