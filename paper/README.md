# Paper: *Memory That Doesn't Expire*

Working guide for taking this paper from "compiles" to "on arXiv".
Supersedes the old `WRITING_GUIDE.md` (retired — see git history).

**Target: arXiv by end of August 2026.**
Steps marked 👤 need a human; the rest can be delegated.

---

## 1. Current status

| Area | State |
|---|---|
| System (safety, persona, multi-user, TTS) | ✅ done |
| Main benchmark — 4 strategies × 10 convs × 1,986 QA, judged | ✅ done |
| Extractor ladder — qwen2.5 3B/7B/14B | ✅ done |
| Figure 3 temporal-grounding ablation | ✅ done (ON 0.364 vs OFF 0.081) |
| Extraction precision audit — 200 hand-checked | ✅ done (199/200) |
| Bootstrap CIs + paired significance tests | ✅ done (§5.7) |
| Figures 1–3 rendered | ✅ done |
| All sections drafted (`.md`) and ported (`.tex`) | ✅ done |
| LaTeX compiles cleanly on Overleaf | ✅ done |
| Authorship + repo link set | ✅ done |
| Reading pass — author lists verified, MemGPT result folded in | ✅ done |
| Number audit — all tables cross-checked against sources | ✅ done |
| **Add 2–3 secondary refs (quantisation, Reflexion)** | ⬜ **next** |
| Polish passes (6 of them) | ⬜ |
| arXiv submission | ⬜ 👤 |

**No GPU runs remain.** Every number in the paper is frozen.

---

## 2. File map

```
paper/
  main.tex              preamble, title, abstract, section includes
  sections/*.tex        the six body sections (what actually compiles)
  *.md                  original markdown drafts (reference only — .tex is canonical)
  references.bib        7 entries, all cited, all resolving
  figures/
    make_fig1.py        length-invariance (the signature figure)
    make_fig2.py        architecture diagram
    fig*.pdf/.png       rendered output
  README.md             this file
scripts/
  robustness_ci.py      regenerates every CI and significance test
```

⚠️ **`.tex` is canonical, not `.md`.** The markdown drafts are historical. Edit
the `.tex` files; the `.md` files will drift and that is fine.

---

## 3. Claim ledger

Every number in the paper and where it comes from. **Check this before every
polish pass** — number drift between abstract and tables is the most common
thing reviewers catch. (We already hit this once: Table 2 said `0.163` while
§5.7 said `0.170` for the same quantity; both now derive from
`robustness_ci.py`.)

| Claim | Value | Source |
|---|---|---|
| Judged accuracy, 4 strategies | .228 / .434 / .544 / .457 | `data/bench_results/run_20260719_*/summary_judged.json` |
| Temporal: agentic vs full_history | 0.368 vs 0.237 | same |
| Length split, in-window | .702 / .330 / .306 | `robustness_ci.py` |
| Length split, truncated | .170 / .343 / .329 | `robustness_ci.py` |
| Collapse / crossover | −76% / 2.0× | `robustness_ci.py` |
| Split sizes | n=927 in-window, n=601 truncated | `robustness_ci.py` |
| Extractor ladder overall | .309 / .348 / .470 | `data/bench_results/ladder/run_*/summary_judged.json` |
| Ladder temporal (breaks first) | .06 / .19 / .34 | same |
| Context per question | 889 / 1,428 / 59,585 chars → 67× | raw-F1 run |
| Grounding ablation, temporal | ON 0.364, OFF 0.081 (4.5×) | `data/bench_results/fig3/{on,off}/*/summary_judged.json` |
| Grounding ablation, overall | ON 0.453, OFF 0.392 | same |
| Paired Δ temporal (agentic−full_history) | +0.131 [+0.065,+0.196], p<0.001 | `robustness_ci.py` |
| Paired Δ grounding (ON−OFF) | +0.283 [+0.227,+0.340], p<0.001 | `robustness_ci.py` |
| Extraction precision | 199/200 (198/200 strict) | `data/gold/annotation_sheet.tsv` |
| Benchmark size | 10 convs, 1,986 QA | LoCoMo |
| Hardware / latency | RTX 4070 12 GB, TTFT ≈0.9 s, 40+ tok/s | live instrumentation |

Regenerate all statistics:

```bash
.venv/bin/python scripts/robustness_ci.py
```

⚠️ `data/` is gitignored, so these result files exist **only on this machine**.
Back them up, and see step 86 about publishing them.

---

## What is left: a 1–100 of remaining work

Everything below is **not yet done**. Steps marked 👤 need you.
Estimated total: **3–5 working days**, plus endorsement waiting time.

### A. Finish the citations (1–10) — ~30 min

1. Open arXiv 2210.17323 (GPTQ) or 2306.00978 (AWQ); pick one.
2. Copy its BibTeX from the arXiv "Export" panel, not Google Scholar.
3. Add it to `references.bib` as `frantar2022gptq` (or `lin2023awq`).
4. Open arXiv 2303.11366 (Reflexion) or 2210.03629 (ReAct); pick one.
5. Add it as `shinn2023reflexion` (or `yao2022react`).
6. Optional: RULER 2404.06654 for long-context evaluation.
7. Check no note in the file contains an at-sign (BibTeX parses one as an entry).
8. Cite the quantisation ref where Q4 is justified (Setup, hardware subsection).
9. Cite the agentic ref in Related Work, "Small-model capability".
10. Recompile; confirm the bibliography grew and no `[?]` appears.

### B. Confirm the current build (11–18) — ~30 min 👤

11. Recompile on Overleaf three times (LaTeX, BibTeX, LaTeX again).
12. Record the true page count. Target is 8 including references.
13. If over 9 pages, the cut pass (51–60) must be aggressive.
14. Search the PDF for `??` — should be zero.
15. Search for `[?]` — should be zero.
16. Confirm the affiliation line renders under your name.
17. Confirm all three figures render and are legible at 100% zoom.
18. Confirm no table runs past the right margin.

### C. Polish pass 1 — structure (19–30)

*One concern per pass. Combining them means catching nothing.*

19. Read only the section headings in order; confirm they tell the story alone.
20. Read only the first sentence of every paragraph; each must carry its point.
21. Any paragraph over ~8 lines: split it.
22. Confirm Results §5.1 leads with the honest "full-history wins overall".
23. Confirm §5.3 (length-invariance) reads as the climax, not a footnote.
24. Confirm §5.5's MemGPT contrast is stated as interface width, not capability.
25. Confirm the Discussion opens by narrowing the claims, not widening them.
26. Check every forward reference (`\S\ref`) points where you expect.
27. Check the Conclusion introduces no new information.
28. Confirm the abstract previews every result the body delivers.
29. Confirm the four contributions in the intro match what the body proves.
30. Commit.

### D. Polish pass 2 — language (31–42)

31. Tense: present for the paper's actions, past for the experiments.
32. Delete every *obviously, clearly, as expected, of course*.
33. Delete every *very, quite, really, extremely*.
34. Replace *a lot / a bit / somewhat* with numbers or cut them.
35. Scope every claim to LoCoMo; never "all memory systems".
36. Pick one form for prose ("full-history") vs code (`full\_history`); be uniform.
37. Pick one of "agentic memory" / "our method"; be uniform.
38. Expand every acronym on first use (TTFT, KV, NF4, QAT).
39. Confirm British/American spelling is consistent throughout.
40. Read the abstract alone; it must stand without the body.
41. Spellcheck (Overleaf has one built in). 👤
42. Commit.

### E. Polish pass 3 — floats and captions (43–50)

43. Every caption states a takeaway, not a description.
44. Fig 1 caption names the −76% collapse and the flat line.
45. Fig 3 caption names the 4.5× temporal gap.
46. Every table caption says what the reader should conclude.
47. Confirm each figure/table is referenced in the text before it appears.
48. Confirm float placement does not orphan a caption onto its own page.
49. Confirm figures are vector PDF, not raster, at final size.
50. Commit.

### F. Polish pass 4 — cut (51–60)

51. Target: remove 10% of words. It always improves the paper.
52. Cut any sentence that restates the previous one.
53. Cut hedges that duplicate the threats-to-validity section.
54. Cut method detail a reader does not need to reimplement.
55. Cut any related-work sentence not tied to your delta.
56. Collapse any two-sentence pair that could be one.
57. Re-check the page count after cutting.
58. If still over 8 pages, move the per-category appendix table out.
59. Confirm nothing load-bearing was cut (re-run the number audit).
60. Commit.

### G. Polish pass 5 — fresh eyes (61–70) 👤

61. Leave the paper alone for 24 hours. Do not skip this.
62. Read the whole PDF aloud. Rhythm problems surface nowhere else.
63. Mark every sentence you stumble on; rewrite those.
64. Re-read as a hostile reviewer: where would you attack?
65. Confirm the three honesty items survive: full-history wins overall,
    judge limitations, precision-not-recall.
66. Confirm the dropped-MSC rationale reads as a decision, not an omission.
67. Ask: "would I believe this if a stranger wrote it?"
68. Ask: "can a reader reproduce every number from what is written?"
69. Fix what those questions expose.
70. Tag the commit `draft-v1`.

### H. Reproducibility package (71–82)

71. Add a "Reproducing the paper" section to the repo README.
72. Document the LoCoMo download command.
73. Document the benchmark command for each of the four strategies.
74. Document the judge command (`yuna.bench.judge`, qwen2.5:14b, temp 0).
75. Document `scripts/robustness_ci.py` and what it regenerates.
76. Record exact model tags and quantisation (Gemma4-12B-QAT Q4_K_M, qwen2.5 3b/7b/14b).
77. Record the hardware (RTX 4070 12 GB) and CUDA/torch versions.
78. Verify the instructions work from a fresh clone. 👤
79. **Publish the raw `results_judged.jsonl` files** — strongest credibility signal.
80. Use a GitHub release asset or Zenodo; Zenodo also mints a DOI.
81. Add that link to the paper's reproducibility sentence.
82. Commit and tag `draft-v2`.

### I. Getting it published (83–100) 👤

**Read the endorsement note below first — this is the long pole.**

83. Create an arXiv account with your gmail.
84. Start a cs.CL submission to trigger the endorsement request.
85. Copy the unique endorsement code arXiv emails you.
86. Build a shortlist of candidate endorsers: active cs.CL authors whose work
    you cite, or faculty from your university who publish in NLP.
87. Write a short, specific request: who you are, one-line paper summary,
    the arXiv code, a link to the PDF and repo. No mass mailing.
88. Send to 3–5 candidates, individually. Expect most not to reply.
89. In parallel, post an endorsement request on the Hugging Face forums —
    there is an active independent-researcher community doing exactly this.
90. **In parallel, pick a workshop** (see note). Do not serialise these.
91. While waiting: prepare the submission package.
92. Overleaf → Menu → Download → Source (this is the zip arXiv wants).
93. Include the compiled `.bbl`; arXiv does not always run live BibTeX.
94. Test-compile that exact zip in a clean folder to catch missing files.
95. Write the arXiv abstract field: plain text, no LaTeX macros, ≤1920 chars.
96. Choose primary cs.CL, cross-list cs.AI.
97. Choose a licence; CC BY 4.0 is the standard permissive choice.
98. Once endorsed, upload, preview the arXiv-generated PDF, fix any errors.
99. Submit. Announcement takes about one business day.
100. Add the link to your CV, repo README, and Masters applications. 🎉

---

## On arXiv endorsement — yes, you need it

arXiv **changed this policy on 21 January 2026**, and the change works against you.
Previously an institutional email alone was enough. Now a first-time submitter
must satisfy **both** conditions:

1. an institutional email from an academic or research organisation, **and**
2. prior authorship on an arXiv paper in the relevant domain.

You have neither. So **personal endorsement is your only route** — there is no
way around it, and it is harder than it was six months ago.

**What endorsement is not:** it is not peer review. An endorser confirms only
that the work belongs in the category and that you understand the field. They
are explicitly not vouching for correctness and are not expected to read the
paper closely. Saying this in your request lowers the bar you are asking someone
to clear.

**Endorser requirements:** they must have authored a minimum number of papers in
the domain, submitted between three months and five years ago — so an active
mid-career researcher, not an emeritus one.

**Endorsement is per-category, not per-paper.** Once endorsed for cs.CL, every
future cs.CL submission is unblocked. You pay this cost once.

### arXiv is not the only path — and may not be the best one

Your goal is Masters applications, not arXiv specifically. Worth weighing:

- **A workshop paper is arguably worth more than a preprint.** It is peer
  reviewed, it is a real venue on your CV, you get reviewer feedback, and
  coauthors or contacts made there can endorse you later. An unreviewed preprint
  from an unaffiliated author carries less weight than an accepted workshop paper.
- **Zenodo** gives you a permanent DOI with no endorsement gate — a fine fallback
  for citability while arXiv is pending.
- **OpenReview** hosts many workshop submissions publicly.

The pragmatic play is to run steps 83–89 (endorsement) and step 90 (workshop
submission) **at the same time**. Whichever lands first, you have a result; if
both land, better still.
