#!/usr/bin/env python3
"""Score a fact-check log against an answer key.

Usage:
  python3 scripts/score_log.py evals/answers/tech-history.json log.md [--min-recall 0.8] [--json]

The log is the skill's markdown table (| # | Claim | Verdict | Source |). Each
answer-key claim is matched to the first log row whose claim cell contains
its `match` text (case-insensitive). A planted error (expect includes
"incorrect" or "stale") is caught when the row's verdict is one the key
accepts. A clean claim is a false alarm when the log marks it incorrect or
stale and the key does not accept that. An overclaim is a claim the key
says only the subject or the writer's notes support, marked verified. It also counts verdicts whose source
cell carries a link: a verdict from memory, with no link, is right by luck.

Exit codes: 0 = scored (and recall >= --min-recall, if given),
1 = recall below --min-recall, 2 = bad usage or unreadable input.
"""
from __future__ import annotations

import argparse
import json
import re
import sys

# (verdict, pattern). The verdict is the match that starts earliest in the
# cell, so "Not verified" is unverified and "⚠️ Unverified (may be outdated)"
# is unverified, not stale. At the same position the longer match wins.
VERDICT_PATTERNS = [
    ("incorrect", r"❌|✗|\b(?:not|partially|partly|half|mostly) (?:correct|true|accurate)\b"
                  r"|\b(?:incorrect|inaccurate|refuted|false|wrong|misattributed|misquoted)\b"),
    ("unverified", r"⚠|\bnot (?:verified|confirmed)\b|\b(?:unverified|unverifiable|inconclusive)\b"),
    ("stale", r"🕰|\b(?:stale|outdated)\b"),
    ("inconsistent", r"🔀|\binconsistent\b"),
    ("self-reported", r"🏷|\bself[- ]reported\b"),
    ("verified", r"✅|✓|\b(?:verified|confirmed|accurate|correct|true)\b"),
]
ERRORS = {"incorrect", "stale"}
WEAK = {"self-reported", "unverified"}
ROW_ID = re.compile(r"\**#?\d+[a-z]?(?:\s*[-–]\s*\d+[a-z]?)?\**")
CELL_SPLIT = re.compile(r"(?<!\\)\|")


def verdict_of(cell: str) -> str | None:
    """The verdict named first in the cell. An emoji directly followed by a
    verdict word defers to the word ("⚠ Outdated" is stale)."""
    found = []
    for name, pat in VERDICT_PATTERNS:
        for m in re.finditer(pat, cell, re.I):
            found.append((m.start(), -(m.end() - m.start()), m.end(), name, m.group(0)))
    if not found:
        return None
    found.sort()
    first = found[0]
    if not first[4].isascii():
        word = [f for f in found if f[4].isascii() and first[2] <= f[0] <= first[2] + 3]
        if word:
            return word[0][3]
    return first[3]


def parse_log(text: str) -> list[dict]:
    """Rows of a markdown table whose first cell is a claim number.

    Accepts split rows (5a, 5b), grouped rows (3-4), bold numbers, and
    escaped pipes inside cells.
    """
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip().replace("\\|", "|") for c in CELL_SPLIT.split(line.strip("|"))]
        if len(cells) >= 3 and ROW_ID.fullmatch(cells[0]):
            source = cells[3] if len(cells) > 3 else ""
            rows.append({"claim": cells[1], "verdict": verdict_of(cells[2]), "raw": cells[2],
                         "linked": bool(re.search(r"https?://", source))})
    return rows


def load_key(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        key = json.load(fh)
    claims = key.get("claims") if isinstance(key, dict) else None
    if not claims or not all(isinstance(c, dict) and c.get("match") and c.get("expect")
                             and c.get("key") for c in claims):
        raise ValueError(f"{path}: needs a non-empty 'claims' list, each with key, match, and expect")
    return key


def score(key: dict, rows: list[dict]) -> dict:
    results = []
    for c in key["claims"]:
        # A claim split across rows (5a attribution, 5b content) or grouped
        # with others: the first matching row is the one scored.
        row = next((r for r in rows if c["match"].lower() in r["claim"].lower()), None)
        got = row["verdict"] if row else None
        planted = bool(ERRORS & set(c["expect"]))
        results.append({"key": c["key"], "planted_error": planted, "expect": c["expect"],
                        "got": got, "found": row is not None, "ok": got in c["expect"],
                        "linked": bool(row and row["linked"]),
                        "false_alarm": (not planted) and got in ERRORS and got not in c["expect"],
                        "overclaim": got == "verified" and set(c["expect"]) <= WEAK})
    planted = [r for r in results if r["planted_error"]]
    caught = sum(1 for r in planted if r["ok"])
    return {"planted_errors": len(planted), "caught": caught,
            "recall": round(caught / len(planted), 3) if planted else 1.0,
            "false_alarms": sum(1 for r in results if r["false_alarm"]),
            "overclaims": sum(1 for r in results if r["overclaim"]),
            "missing": [r["key"] for r in results if not r["found"]],
            "agreement": round(sum(1 for r in results if r["ok"]) / len(results), 3) if results else 1.0,
            "linked": sum(1 for r in results if r["linked"]),
            "claims": results}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Score a fact-check log against an answer key.")
    ap.add_argument("key")
    ap.add_argument("log", help="log file, or - for stdin")
    ap.add_argument("--min-recall", type=float)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    try:
        key = load_key(args.key)
        text = sys.stdin.read() if args.log == "-" else open(args.log, encoding="utf-8").read()
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    res = score(key, parse_log(text))
    if args.json:
        print(json.dumps(res, indent=2, ensure_ascii=False))
    else:
        print(f"planted errors caught: {res['caught']}/{res['planted_errors']} (recall {res['recall']}); "
              f"false alarms: {res['false_alarms']}; overclaims: {res['overclaims']}; agreement with key: {res['agreement']}; "
              f"verdicts with a source link: {res['linked']}/{len(res['claims'])}")
        for r in res["claims"]:
            if not r["ok"]:
                print(f"  {r['key']}: expected {'/'.join(r['expect'])}, got {r['got'] or 'no matching row'}")
    if args.min_recall is not None and res["recall"] < args.min_recall:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
