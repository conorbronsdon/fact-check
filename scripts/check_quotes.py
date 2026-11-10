#!/usr/bin/env python3
"""Check every quote in a draft against a transcript or other source.

Matches eligible straight or curly double-quoted spans against the supplied
source. Verbatim matching preserves case, punctuation, and numeric symbols;
line wrapping, apostrophe style, Unicode minus, and spacing before percent
signs are normalized. Similar passages are advisory, not proof of a match.

  verbatim  exactly one matching passage was found
  near      a similar passage or marked edit needs review
  absent    no sufficiently similar passage was found
  ambiguous malformed input or multiple matches need review

The source is split on blank lines and simple speaker headers. Other
transcript formats may not identify speaker boundaries. Check attribution,
meaning, and the original recording yourself.

Usage:
  python3 scripts/check_quotes.py draft.md --source transcript.md
  python3 scripts/check_quotes.py draft.md --source transcript.md --json
  cat draft.md | python3 scripts/check_quotes.py - --source transcript.md

Exit codes: 0 = every quote is verbatim (or there are none),
1 = at least one result needs review, 2 = bad usage or unreadable input.
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
import unicodedata

# Preserve punctuation and symbols: they can change a quotation's meaning.
WORD = re.compile(r"(?<![\w.])[+\-\u2212]?(?:\d+(?:[.,]\d+)*|\.\d+)(?:[ \t\u00a0]*%)?|[^\W\d_]+(?:['\u2019][^\W\d_]+)*|[^\s]", re.UNICODE)
FENCE = re.compile(r"^[ \t]*(`{3,}|~{3,})(.*)$")
EDIT_MARK = re.compile(r"\.(?:[ \t]*\.){2}|\u2026|\[[^\]]*\]")
SPEAKER = re.compile(r"(?m)^[ \t]*[A-Z][A-Za-z0-9_.'-]*(?:[ \t]+[A-Z][A-Za-z0-9_.'-]*){0,2}:[ \t]+")
SENTENCE_END = re.compile(r"[.!?]+[\"\u201d'\u2019)]*(?=\s|$)|\n[ \t]*\n")
DEFAULT_THRESHOLD = 0.6


def blank(match: re.Match) -> str:
    return re.sub(r"[^\n]", " ", match.group(0))


def strip_markup(text: str, diagnostics: list | None = None) -> str:
    """Mask supported Markdown without changing offsets; report unfinished markup."""
    diagnostics = diagnostics if diagnostics is not None else []
    lines = text.splitlines(keepends=True)
    if lines and lines[0].strip() == "---":
        close = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
        if close is None:
            diagnostics.append({"line": 1, "reason": "Unclosed front matter."})
        else:
            content = [line.strip() for line in lines[1:close]
                       if line.strip() and not line.lstrip().startswith("#")]
            if content and not re.match(r"^[A-Za-z_][\w.-]*\s*:", content[0]):
                diagnostics.append({"line": 1, "reason": "Initial horizontal rule may not be front matter."})
            for i in range(close + 1):
                lines[i] = blank(re.match(r"[\s\S]*", lines[i]))
    fence = None
    fence_line = None
    for i, line in enumerate(lines):
        content = line.rstrip("\r\n")
        m = FENCE.match(content)
        if fence is None and m:
            fence, fence_line = m.group(1), i + 1
            lines[i] = blank(re.match(r"[\s\S]*", line))
        elif fence is not None:
            lines[i] = blank(re.match(r"[\s\S]*", line))
            if re.fullmatch(r"[ \t]*" + re.escape(fence[0]) + "{" + str(len(fence)) + r",}[ \t]*", content):
                fence = None
    if fence is not None:
        diagnostics.append({"line": fence_line, "reason": "Unclosed code fence."})
    text = "".join(lines)
    chars = list(text)
    pos = 0
    while True:
        a = text.find("<!--", pos)
        if a < 0:
            break
        b = text.find("-->", a + 4)
        if b < 0:
            diagnostics.append({"line": text.count("\n", 0, a) + 1, "reason": "Unclosed HTML comment."})
            b = len(text)
        else:
            b += 3
        for i in range(a, b):
            if chars[i] != "\n":
                chars[i] = " "
        pos = b
    text = "".join(chars)
    chars = list(text)
    pos = 0
    while pos < len(text):
        m = re.search(r"`+", text[pos:])
        if not m:
            break
        a, opener_end = pos + m.start(), pos + m.end()
        marker = text[a:opener_end]
        paragraph_end = re.search(r"\n[ \t\r]*\n", text[opener_end:])
        limit = opener_end + paragraph_end.start() if paragraph_end else len(text)
        close = re.search(r"(?<!`)" + re.escape(marker) + r"(?!`)", text[opener_end:limit])
        if not close:
            diagnostics.append({"line": text.count("\n", 0, a) + 1, "reason": "Unclosed inline code."})
            pos = opener_end
            continue
        b = opener_end + close.end()
        for i in range(a, b):
            if chars[i] != "\n":
                chars[i] = " "
        pos = b
    return "".join(chars)


def tokens(text: str) -> list[tuple[str, int, int]]:
    """Conservative normalized token and original character offsets."""
    out = []
    for m in WORD.finditer(text):
        raw = unicodedata.normalize("NFC", m.group(0)).replace("\u2019", "'").replace("\u2212", "-")
        norm = re.sub(r"[ \t\u00a0]+(?=%$)", "", raw)
        out.append((norm, m.start(), m.end()))
    return out


def scan_quotes(draft: str) -> tuple[list[dict], list[dict]]:
    """Pair every delimiter before the length filter; report malformed pairs."""
    diagnostics = []
    text = strip_markup(draft, diagnostics)
    found = []
    opening = None
    for i, ch in enumerate(text):
        if opening is not None and ch == "\n" and re.match(r"\n[ \t\r]*\n", text[i:]):
            diagnostics.append({"line": text.count("\n", 0, opening[0]) + 1,
                                "reason": "Quote crosses a blank paragraph."})
            opening = None
        if ch not in ('"', '\u201c', '\u201d'):
            continue
        backslashes = 0
        j = i - 1
        while j >= 0 and text[j] == '\\':
            backslashes += 1
            j -= 1
        if backslashes % 2:
            continue
        if opening is None:
            if ch == '\u201d':
                diagnostics.append({"line": text.count("\n", 0, i) + 1, "reason": "Unmatched closing quote."})
            else:
                opening = (i, ch)
            continue
        a, delim = opening
        expected = '"' if delim == '"' else '\u201d'
        if ch != expected:
            diagnostics.append({"line": text.count("\n", 0, a) + 1, "reason": "Mixed or nested quote delimiters."})
            opening = None
            continue
        raw = draft[a + 1:i]
        masked = text[a + 1:i]
        if any(not original.isspace() and hidden == " " for original, hidden in zip(raw, masked)):
            diagnostics.append({"line": text.count("\n", 0, a) + 1,
                                "reason": "Markup inside a quote requires review."})
            opening = None
            continue
        quote = " ".join(masked.split())
        if len(quote) >= 12 and tokens(quote):
            found.append({"line": text.count("\n", 0, a) + 1, "quote": quote})
        opening = None
    if opening is not None:
        diagnostics.append({"line": text.count("\n", 0, opening[0]) + 1, "reason": "Unmatched opening quote."})
    return found, diagnostics


def find_quotes(draft: str) -> list[dict]:
    return scan_quotes(draft)[0]


def source_regions(source: str) -> list[tuple[int, int]]:
    """Keep searches inside explicit speaker turns and blank-separated blocks."""
    starts = {0, len(source)}
    starts.update(m.start() for m in SPEAKER.finditer(source))
    starts.update(m.end() for m in re.finditer(r"\n[ \t\r]*\n", source))
    ordered = sorted(starts)
    return [(a, b) for a, b in zip(ordered, ordered[1:]) if source[a:b].strip()]


def sentence_spans(text: str) -> list[tuple[int, int]]:
    """Single line wraps are not sentence breaks; speaker headers are boundaries."""
    bounds = {0, len(text)}
    bounds.update(m.end() for m in SENTENCE_END.finditer(text))
    bounds.update(m.start() for m in SPEAKER.finditer(text))
    ordered = sorted(bounds)
    return [(a, b) for a, b in zip(ordered, ordered[1:]) if text[a:b].strip()]


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
    sm = difflib.SequenceMatcher(a=source_words, b=quote_words, autojunk=False)
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
    quotes, diagnostics = scan_quotes(draft)
    regions = []
    for a, b in source_regions(source):
        ts = [(word, a + start, a + end) for word, start, end in tokens(source[a:b])]
        if ts:
            regions.append(ts)
    spans = sentence_spans(source)
    results = []
    for item in quotes:
        q_tokens = tokens(item["quote"])
        q_words = [t[0] for t in q_tokens]
        res = {"id": len(results) + 1, "line": item["line"], "quote": item["quote"]}
        edited = bool(EDIT_MARK.search(item["quote"]))
        if edited:
            res["edited"] = True
        candidates = []
        count = 0
        for ts in regions:
            words = [t[0] for t in ts]
            for i in range(len(words) - len(q_words) + 1):
                if words[i:i + len(q_words)] == q_words:
                    count += 1
                    if len(candidates) < 20:
                        a, b = ts[i][1], ts[i + len(q_words) - 1][2]
                        candidates.append({"source_line": source.count("\n", 0, a) + 1,
                                           "source_text": " ".join(source[a:b].split()),
                                           "context": context(source, spans, a, b)})
        if count > 1:
            res.update(status="ambiguous", reason="Multiple exact passages require attribution review.",
                       candidate_count=count, candidates=candidates, candidates_truncated=count > len(candidates))
            results.append(res)
            continue
        if count == 1:
            res.update(status="near" if edited else "verbatim", score=1.0, **candidates[0])
            if edited:
                res["diff"] = "An edit marker requires review against the source context."
            results.append(res)
            continue
        best = None
        for ts in regions:
            words = [t[0] for t in ts]
            # Fuzzy matching is advisory only; case-folding here never creates
            # a verbatim result, but helps expose the whole nearby passage.
            score, lo, hi = best_window([w.casefold() for w in q_words], [w.casefold() for w in words])
            if best is None or score > best[0]:
                best = (score, lo, hi, ts, words)
        if best is None:
            res.update(status="absent", score=0.0)
            results.append(res)
            continue
        score, lo, hi, ts, words = best
        res["score"] = round(score, 3)
        if score < threshold or hi <= lo:
            res["status"] = "absent"
            results.append(res)
            continue
        res["status"] = "near"
        lo, hi = widen([w.casefold() for w in q_words], [w.casefold() for w in words], lo, hi)
        a, b = ts[lo][1], ts[hi - 1][2]
        res["source_line"] = source.count("\n", 0, a) + 1
        res["source_text"] = " ".join(source[a:b].split())
        res["diff"] = word_diff([source[t[1]:t[2]] for t in ts[lo:hi]],
                                [item["quote"][t[1]:t[2]] for t in q_tokens])
        res["context"] = context(source, spans, a, b)
        results.append(res)
    for diagnostic in diagnostics:
        results.append({"id": len(results) + 1, "line": diagnostic["line"], "quote": "",
                        "status": "ambiguous", "reason": diagnostic["reason"]})
    return results


def to_text(results: list[dict]) -> str:
    if not results:
        return "No eligible quotes found in a well-formed draft."
    out = []
    for r in results:
        out.append(f"#{r['id']} line {r['line']}: {r['status'].upper()}  \"{r['quote']}\"")
        if r["status"] == "ambiguous":
            out.append(f"  review required: {r['reason']}")
            if "candidate_count" in r:
                out.append(f"  {r['candidate_count']} exact passages; showing {len(r['candidates'])}")
                for candidate in r["candidates"]:
                    out.append(f"  line {candidate['source_line']}: {candidate['context']['sentence']}")
        elif r["status"] == "absent":
            out.append(f"  no sufficiently similar passage found (best similarity {r['score']:.2f}); inspect the source")
        else:
            if r.get("edited"):
                out.append("  the draft marks an edit (ellipsis or brackets): check the cut keeps the meaning")
            if r["status"] == "near":
                out.append(f"  closest source text (line {r['source_line']}, similarity {r['score']:.2f}):")
                out.append(f"    \"{r['source_text']}\"")
                out.append(f"  diff (source -> draft): {r['diff']}")
            ctx = r["context"]
            out.append(f"  before: {ctx['before'] or '(start of source)'}")
            out.append(f"  match:  {ctx['sentence']}")
            out.append(f"  after:  {ctx['after'] or '(end of source)'}")
        out.append("")
    counts = {s: sum(r["status"] == s for r in results) for s in ("verbatim", "near", "absent", "ambiguous")}
    out.append(f"{len(results)} results: {counts['verbatim']} verbatim, {counts['near']} near, "
               f"{counts['absent']} absent, {counts['ambiguous']} ambiguous. "
               "Wording only: check attribution, meaning and the original source.")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Check draft quotes against a transcript.")
    ap.add_argument("path", help="draft to scan, or - for stdin")
    ap.add_argument("--source", required=True, help="transcript or other source text")
    ap.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD,
                    help=f"similarity at or above which a quote is near, not absent (default {DEFAULT_THRESHOLD})")
    ap.add_argument("--json", action="store_true", help="emit JSON")
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if not 0 < args.threshold <= 1:
        print("error: --threshold must be in (0, 1]", file=sys.stderr)
        return 2
    try:
        draft = sys.stdin.buffer.read().decode("utf-8") if args.path == "-" else open(args.path, encoding="utf-8").read()
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
