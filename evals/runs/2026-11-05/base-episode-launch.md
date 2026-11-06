# Fact-check: episode-launch.md

Draft: /home/user/fact-check/evals/drafts/episode-launch.md
Reference transcript: /home/user/fact-check/evals/drafts/episode-launch.transcript.md (it notes that the guest and company are invented, so the transcript is the only source for guest-specific claims)

| # | Claim (as written, verbatim from the draft) | Verdict | Source / correction |
|---|---|---|---|
| 1 | "Dana Reyes, CTO of Lattice Forge" | ✅ verified | Transcript: host says "you're the CTO at Lattice Forge" and Dana does not dispute it. |
| 2 | "who spent six years at Stripe" | ✅ verified | Transcript: "Six, yeah. Almost seven." "Six years" holds; "nearly seven years" would be more precise. |
| 3 | "before founding the company" | ⚠️ unverified | The transcript never says Dana founded Lattice Forge. It only says she is CTO. Confirm with the guest, or write "before joining Lattice Forge." |
| 4 | "She scaled Kubernetes at Google in 2005" | ❌ incorrect | Kubernetes did not exist in 2005. Google announced it and open-sourced it in June 2014 (first GitHub commit 6 June 2014; Google Cloud Platform blog, 10 June 2014). The 2005 date came from the host's question, and Dana only laughed it off ("Something like that"), so she never confirmed it. At most she could have worked on Google's internal Borg system, Kubernetes' predecessor. Remove the claim or confirm with the guest what she actually worked on. |
| 5 | "long before most teams had heard of containers" | ⚠️ unverified | This is loose framing, and it depends on claim 4, which is wrong. Containers went mainstream with Docker in 2013. The phrase is not in the transcript. |
| 6 | "Lattice Forge now runs with 40 engineers" | ❌ incorrect | Transcript: "We're about 14 engineers." Change to "about 14 engineers." |
| 7 | "Most outages start in config, not code," Dana told us. | ❌ incorrect (misquote) | The quote marks wrap words Dana did not say. She said: "Honestly, most of our outages started in config changes, not in the code itself." She was talking about her own company's outages in the past tense, not making a general claim about all outages. Quote her exactly, or paraphrase without quote marks and keep "our." The headline "why outages start in config" generalizes in the same way. |
| 8 | "Netflix open-sourced Chaos Monkey in 2012" | ✅ verified | Netflix Tech Blog, "Chaos Monkey Released Into The Wild," 30 July 2012. Netflix built it internally around 2010–2011 and open-sourced it in 2012. |
| 9 | "Google open-sourced Kubernetes in 2014" | ✅ verified | Google announced Kubernetes as open source in June 2014 (Google Cloud Platform blog, 10 June 2014; first commit on github.com/kubernetes/kubernetes, 6 June 2014). The transcript excerpt does not include this line. |

**Summary:** 9 claims: 4 verified, 2 unverified, 3 incorrect. The three errors are the 2005 Kubernetes-at-Google claim, the headcount (40 vs. the 14 Dana gave), and the quote, which is reworded and turned into a general statement.
