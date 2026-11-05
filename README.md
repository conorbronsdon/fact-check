<div align="center">

# fact-check

**Catch the wrong number before your readers do.**

[![GitHub stars](https://img.shields.io/github/stars/conorbronsdon/fact-check?style=social)](https://github.com/conorbronsdon/fact-check/stargazers)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Podcast](https://img.shields.io/badge/Podcast-Chain_of_Thought-purple?style=flat-square)](https://chainofthought.show/?utm_source=github&utm_medium=referral&utm_campaign=repo-readme&utm_content=fact-check)
[![X](https://img.shields.io/badge/X-@ConorBronsdon-1DA1F2?logo=x)](https://x.com/ConorBronsdon)

</div>

## TL;DR

A portable agent skill ([SKILL.md](SKILL.md)) that runs a truth pass on a draft before you publish it. Install:

```bash
git clone https://github.com/conorbronsdon/fact-check ~/.claude/skills/fact-check
```

Then: `/fact-check path/to/draft.md`, or just ask "fact-check this before I post."

What it does:

- Pulls out every checkable claim: names, titles, products, numbers, dates, biography, superlatives, quotes
- Tries to **refute** each one against a primary source, instead of looking for a page that agrees
- Returns one headline sentence and a numbered table, with a verdict and a source for every claim
- Flags and never edits. A wrong figure comes with the correct figure and its source, so each fix is one step

Works with Claude Code, Cursor, Codex, OpenClaw, Hermes Agent, and anything that reads the [agentskills.io](https://agentskills.io) format. Companion to [avoid-ai-writing](https://github.com/conorbronsdon/avoid-ai-writing?utm_source=github&utm_medium=referral&utm_campaign=repo-readme&utm_content=fact-check): check the facts first, then clean up the prose.

---

## Why this exists

AI drafting makes a specific kind of error that careful readers miss. It joins real parts into a false whole: a real person, a real company, and a real number in one sentence that was never true. You recognize every part, so it reads as right.

The case that shaped this skill: launch copy for a podcast episode said the guest "scaled it at Netflix across 300M subscribers." He did work at Netflix, from 2018 to 2020. Netflix did reach 300M subscribers, in late 2024. The two never overlapped. The line went out in a post and a launch email because the host had said it on the recording, and every check that compared the copy to the transcript passed it.

So the skill has two rules that a plain "please fact-check this" prompt doesn't have. A claim and its context are checked together, and the draft and your notes never count as evidence.

## What you get back

> **9 claims: 6 ✅, 1 🕰️, 2 ❌. Both ❌ are in paragraph two: the survey figure (#2) and "first lab to ship" (#5).**

| # | Claim (as written) | Verdict | Source / correction |
|---|---|---|---|
| 2 | "84% of developers now use AI tools" | ❌ | The survey reports 84% use *or plan to use*. Link + date. |
| 4 | "the largest now hold over a million tokens" | 🕰️ | True when written; a newer figure exists. Link + date. |
| 5 | "the first lab to ship a memory tool" | ❌ | Another lab shipped one earlier. Link + date. |

*Illustrative output format, not a graded run. Try it on [`examples/draft.md`](examples/draft.md).*

Verdicts: ✅ verified, 🏷️ self-reported (fine with attribution), 🕰️ stale, ⚠️ unverified, ❌ incorrect, 🔀 inconsistent within the draft.

## Modes

- `check` (default): extract, verify, log.
- `extract`: list claims only, for checking by hand or without web access.
- `quick`: verify only Tier A claims (people, titles, product names, anything going to a named recipient, superlatives).

## The claim extractor

`scripts/extract_claims.py` is a dependency-free Python script that lists every sentence containing a number, money, a date, a superlative, an attribution, or a quote. The skill runs it first so obvious claims can't be skipped, then reads the draft for what patterns can't see (a wrong job title, a misspelled product).

```bash
python3 scripts/extract_claims.py draft.md
python3 scripts/extract_claims.py --json draft.md
```

It skips front matter, code, URLs, list numbering, and version strings. Tests: `python3 -m unittest discover -s tests -v`.

## Install elsewhere

- **Claude Code plugin:** this repo is a plugin (`.claude-plugin/plugin.json`). It is listed in the `conorbronsdon-skills` marketplace alongside avoid-ai-writing.
- **Cursor, Codex, other agents:** copy the folder into your agent's skills directory, or paste `SKILL.md` into your rules or instructions.

## Limits

It reports what sources say on the day it runs, with dates. It does not judge arguments, predictions, or opinions, and it needs web access to verify anything. Without web access it still extracts claims and marks them unverified.

## More from me

- [avoid-ai-writing](https://github.com/conorbronsdon/avoid-ai-writing?utm_source=github&utm_medium=referral&utm_campaign=repo-readme&utm_content=fact-check): audit and rewrite AI writing patterns.
- [What I'm building](https://conorbronsdon.com/builds/?utm_source=github&utm_medium=referral&utm_campaign=repo-readme&utm_content=fact-check): agent skills, MCP servers, creator tools.
- [Chain of Thought](https://chainofthought.show/?utm_source=github&utm_medium=referral&utm_campaign=repo-readme&utm_content=fact-check): conversations with the people shipping AI systems.

Authored by [Conor Bronsdon](https://conorbronsdon.com/?utm_source=github&utm_medium=referral&utm_campaign=repo-readme&utm_content=fact-check) · [GitHub](https://github.com/conorbronsdon) · [X](https://x.com/ConorBronsdon) · [LinkedIn](https://www.linkedin.com/in/conorbronsdon/)

---

## Disclaimer

*This is an independent personal project, not affiliated with, sponsored by, or endorsed by any company. All views expressed are my own.*

## License

MIT
