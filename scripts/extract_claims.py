#!/usr/bin/env python3
"""List sentences in a draft that contain checkable claims.

Deterministic floor for the fact-check skill: it finds surface patterns
(numbers, dates, money, superlatives, attributions, quotes) so no obvious
claim is skipped. It does not judge truth, and it misses claims with no
surface marker (a wrong job title, a misspelled product). Read the draft too.

Usage:
  python3 scripts/extract_claims.py draft.md
  python3 scripts/extract_claims.py --json draft.md
  cat draft.md | python3 scripts/extract_claims.py -

Exit codes: 0 = ran (with or without candidates), 2 = bad usage or unreadable input.
"""
from __future__ import annotations

import argparse
import json
import re
import sys

MONTHS = (
    "January|February|March|April|May|June|July|August|September|October|"
    "November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec"
)

PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("money", re.compile(r"(?:[$€£¥]\s?\d[\d,.]*\s?(?:[kKmMbBtT]n?\b|thousand|million|billion|trillion)?)|\b\d[\d,.]*\s?(?:dollars|euros|USD|EUR)\b")),
    ("percent", re.compile(r"\b\d[\d,.]*\s?(?:%|percent\b|percentage points?\b|pp\b|bps\b)")),
    ("multiplier", re.compile(r"\b\d[\d,.]*\s?[x×]\b|\b(?:doubled|tripled|quadrupled|halved)\b", re.I)),
    ("scale", re.compile(r"\b\d[\d,.]*\s?(?:thousand|million|billion|trillion|[kKMB])\b(?!-)")),
    ("date", re.compile(rf"\b(?:{MONTHS})\.?\s+\d{{1,2}}(?:st|nd|rd|th)?(?:,\s*\d{{4}})?\b|\b(?:{MONTHS})\s+\d{{4}}\b|\b(?:in|since|by|until|from|of|during)\s+(?:early\s+|mid-|late\s+)?(?:19|20)\d{{2}}\b|\b(?:19|20)\d{{2}}s?\b(?=\s|[,.;:)])|\bQ[1-4]\s+(?:19|20)?\d{{2}}\b")),
    ("count", re.compile(r"\b\d{1,3}(?:,\d{3})+\b|\b(?!(?:19|20)\d{2}\b)\d{2,}\s+(?!%)[A-Za-z][A-Za-z-]+")),
    ("superlative", re.compile(r"\b(?:first|only|largest|biggest|fastest|slowest|smallest|highest|lowest|oldest|newest|most|least|leading|top|best|worst|record|unprecedented|never before|number one|no\. ?1)\b|#1\b", re.I)),
    ("attribution", re.compile(r"\b(?:according to|a (?:recent |new )?(?:study|survey|report|paper|poll|analysis)|(?:study|survey|report|research|data|paper) (?:found|shows?|showed|finds|suggests?)|(?:said|says|told|wrote|announced|reported|estimates?|estimated))\b", re.I)),
    ("quote", re.compile(r"[\"“][^\"”]{12,}[\"”]")),
]

FENCE = re.compile(r"^\s*(```|~~~)")
STRIP = [
    re.compile(r"`[^`]*`"),                       # inline code
    re.compile(r"\]\([^)]*\)"),                   # markdown link targets
    re.compile(r"https?://\S+"),                  # bare URLs
    re.compile(r"<!--.*?-->"),                    # HTML comments
    re.compile(r"^\s{0,3}(?:#{1,6}\s+)?\d+[.)]\s+"),   # list/heading numbering
    re.compile(r"\bv?\d+\.\d+(?:\.\d+)+\b"),      # version strings
]
SENTENCE = re.compile(r"(?<=[.!?])[\"”']?\s+(?=[\"“'A-Z0-9$€£#*_(])")


def clean(line: str) -> str:
    for pat in STRIP:
        line = pat.sub(" ", line)
    return line


def sentences(text: str):
    """Yield (line_number, sentence) pairs, skipping front matter and code."""
    lines = text.splitlines()
    in_code = False
    start = 0
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                start = i + 1
                break
    for idx in range(start, len(lines)):
        raw = lines[idx]
        if FENCE.match(raw):
            in_code = not in_code
            continue
        if in_code or raw.startswith("    ") and raw.strip():
            continue
        body = clean(raw).strip()
        if not body:
            continue
        for part in SENTENCE.split(body):
            part = part.strip(" >-*|")
            if part:
                yield idx + 1, part


def extract(text: str) -> list[dict]:
    out = []
    for lineno, sent in sentences(text):
        kinds, spans = [], []
        for kind, pat in PATTERNS:
            hits = [m.group(0).strip() for m in pat.finditer(sent)]
            if hits:
                kinds.append(kind)
                spans.extend(h for h in hits if h not in spans)
        if kinds:
            out.append({"id": len(out) + 1, "line": lineno, "kinds": kinds,
                        "markers": spans, "sentence": sent})
    return out


def to_markdown(claims: list[dict]) -> str:
    if not claims:
        return "No candidate claims found by surface patterns. Read the draft for names, titles, and products."
    rows = ["| # | Line | Kinds | Sentence |", "|---|---|---|---|"]
    for c in claims:
        sent = c["sentence"].replace("|", "\\|")
        rows.append(f"| {c['id']} | {c['line']} | {', '.join(c['kinds'])} | {sent} |")
    rows.append("")
    rows.append(f"{len(claims)} candidate sentences. Surface patterns only: also check names, titles, products, and biography by reading.")
    return "\n".join(rows)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="List sentences with checkable claims.")
    ap.add_argument("path", help="file to scan, or - for stdin")
    ap.add_argument("--json", action="store_true", help="emit JSON")
    args = ap.parse_args(argv)
    try:
        # utf-8-sig drops a byte-order mark, so front matter after one is still skipped.
        if args.path == "-":
            text = sys.stdin.buffer.read().decode("utf-8-sig")
        else:
            with open(args.path, encoding="utf-8-sig") as fh:
                text = fh.read()
    except (OSError, UnicodeDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    claims = extract(text)
    print(json.dumps(claims, indent=2, ensure_ascii=False) if args.json else to_markdown(claims))
    return 0


if __name__ == "__main__":
    sys.exit(main())
