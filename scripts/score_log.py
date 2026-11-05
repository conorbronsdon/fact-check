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

VERDICTS = [
    ("incorrect", ("❌", "incorrect", "refuted", "false")),
    ("stale", ("🕰", "stale", "outdated")),
    ("inconsistent", ("🔀", "inconsistent")),
    ("self-reported", ("🏷", "self-reported", "self reported")),
    ("unverified", ("⚠", "unverified", "unverifiable", "inconclusive")),
    ("verified", ("✅", "verified", "accurate", "correct", "true")),
]
ERRORS = {"incorrect", "stale"}
WEAK = {"self-reported", "unverified"}


def verdict_of(cell: str) -> str | None:
    low = cell.lower()
    for name, marks in VERDICTS:
        if any(m in cell if not m.isascii() else re.search(rf"\b{re.escape(m)}\b", low)
               for m in marks):
            return name
    return None


def parse_log(text: str) -> list[dict]:
    """Rows of a markdown table whose first cell is a claim number."""
    rows = []
    for line in text.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 3 and re.fullmatch(r"#?\d+", cells[0]):
            source = " | ".join(cells[3:])
            rows.append({"claim": cells[1], "verdict": verdict_of(cells[2]), "raw": cells[2],
                         "linked": bool(re.search(r"https?://", source))})
    return rows


def score(key: dict, rows: list[dict]) -> dict:
    results = []
    for c in key["claims"]:
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
        with open(args.key, encoding="utf-8") as fh:
            key = json.load(fh)
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
