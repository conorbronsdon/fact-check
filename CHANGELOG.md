# Changelog

## 0.1.0 (unreleased)

- First public version: claim extraction in six buckets, internal-consistency pass, refute-first verification with a subagent brief, six verdicts (verified, self-reported, stale, unverified, incorrect, inconsistent), and a headline-first log.
- `scripts/extract_claims.py`: dependency-free extractor that lists sentences containing numbers, money, dates, superlatives, attributions, and quotes. Tested with must-fire and must-not-fire cases.
