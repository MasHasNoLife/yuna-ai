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
| **Reading pass — verify 3 author lists, add 2–3 refs** | ⬜ **next, 👤** |
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

## Phase 1 — Compile (1–14) 👤

1. Create an Overleaf account and a new project.
2. Zip the paper folder: `cd paper && zip -r paper.zip .`
3. New Project → Upload Project → pick the zip.
4. Set `main.tex` as the main document (☰ menu → Main document).
5. Set compiler to **pdfLaTeX** (☰ menu → Compiler). Usually already correct.
6. Recompile. Errors on the first attempt are normal.
7. Read only the **first** error — the rest are usually cascades.
8. `File not found` → check `figures/` uploaded and `\graphicspath{{figures/}}` is set.
9. `Missing $ inserted` → an unescaped `_` outside math mode.
10. `Option clash` → a package loaded twice with different options; use
    `\PassOptionsToPackage{opt}{pkg}` before the first load.
11. BibTeX `missing field name` / `empty year` → a `%` or an at-sign inside a
    `.bib` entry. **BibTeX has no `%` comment character** — notes go *between*
    entries, and must contain no at-signs.
12. Once it builds, **recompile twice more** — refs and citations need extra passes.
13. Search the PDF for `??` (broken ref) and `[?]` (broken citation). Should be none.
14. Read the PDF end to end. Note the page count.

## Phase 2 — Length and front matter (15–22)

15. Target **8 pages** body + references.
16. Confirm the author line and email in `main.tex`.
17. Affiliation: "Independent Researcher" is honest and acceptable.
18. Confirm the repo URL renders under the byline.
19. Confirm the title. Current: *Memory That Doesn't Expire: Agentic Long-Term
    Memory for Conversational Agents on a Single Consumer GPU*. "Single" is
    deliberate — it preempts the multi-GPU question and frames the constraint as
    a thesis rather than a hardware note.
20. Check every figure is legible at printed size.
21. Check no table overflows the margin.
22. Commit the compiling version.

## Phase 3 — The reading pass (23–42) 👤 — *the real remaining work, ~1 day*

23. Download **MemGPT** (arXiv 2310.08560).
24. Read abstract, intro, method; skim results.
25. Write one sentence on how you differ: *they page context with a large model;
    we extract typed facts with a small local one.*
26. Download **Mem0** (arXiv 2504.19413).
27. Read carefully — **this is your closest competitor.**
28. Your delta: *they assume API-scale models; we measure the minimum local size
    and add temporal grounding.*
29. ⚠️ Verify the Mem0 author list against the PDF — currently filled in from an
    unverified source and marked `TODO(reading pass)` in `references.bib`.
30. Download **LoCoMo** (arXiv 2402.17753).
31. Read its evaluation section; you must describe the benchmark correctly.
32. Confirm 10 conversations / 1,986 questions / 5 categories against your own counts.
33. ⚠️ Verify the LoCoMo author list (same `TODO` flag).
34. Note their reported baselines — cite for context.
35. Download **Generative Agents** (arXiv 2304.03442).
36. Read the memory-stream section (recency / importance / relevance).
37. Note the parallel to your age-aware retrieval.
38. ⚠️ Verify the **RAG** author list (arXiv 2005.11401, same `TODO` flag).
39. Get author lists from each paper's own PDF or arXiv BibTeX export —
    **not** Google Scholar, which truncates.
40. Delete each `TODO(reading pass)` note as you confirm it.
41. Cut any paper you cannot tie to your argument in one sentence.
42. Recompile; check the bibliography renders correctly.

## Phase 4 — Strengthen related work (43–52)

43. Add a quantisation citation (justifies Q4): GPTQ 2210.17323 or AWQ 2306.00978.
44. Add an agentic-reasoning citation: Reflexion 2303.11366 or ReAct 2210.03629.
45. Optionally add a long-context eval benchmark: RULER 2404.06654.
46. Add complete entries to `references.bib` — no at-signs in the notes.
47. Cite them in the "Small-model capability" subsection.
48. Ensure **every** related-work subsection ends with an explicit delta sentence.
49. Related Work should reach 500–700 words (currently ~490).
50. Confirm no citation is uncited and no bib entry unused.
51. Recompile.
52. Commit.

## Phase 5 — Number audit (53–62)

53. Open the claim ledger (§3 above).
54. Abstract: verify 76%, 2.0×, 67×, 7–14B.
55. Table 1 against the four judged summaries.
56. Table 2 against `robustness_ci.txt`.
57. Table 3 against the ladder summaries.
58. §5.7 CIs against `robustness_ci.txt`.
59. 199/200 against the annotation sheet.
60. **Confirm intro numbers match results numbers exactly.** Most common catch.
61. Confirm figure numbers match table numbers.
62. Commit.

## Phase 6 — Six polish passes (63–80)

*One concern per pass. Combining them means catching nothing.*

63. **Numbers** — every figure against the ledger.
64. **Citations** — every named system cited on first mention.
65. **Consistency** — pick one form: `full\_history` for the literal config
    value, "full-history" in prose. Be uniform. (Also avoids overfull hboxes,
    since LaTeX cannot hyphenate words containing `\_`.)
66. Same for "agentic memory" vs "our method" — pick one.
67. **Tense** — present for what the paper does, past for what the experiments did.
68. **Hedging** — every claim scoped to LoCoMo, not "all memory systems".
69. Delete every *obviously, clearly, as expected, very, quite*.
70. **Captions** — each states a takeaway, not a description.
71. **Cut** — remove 10% of words. It always improves.
72. **Read aloud** — catches broken rhythm nothing else finds. 👤
73. Check each paragraph's first sentence carries its point.
74. Check no paragraph exceeds ~8 lines.
75. **Fresh eyes** — wait 24h, reread as a hostile reviewer. 👤
76. Ask: "would I believe this if a stranger wrote it?" 👤
77. Verify the three honesty items are present (§ below).
78. Verify the dropped-MSC rationale reads as a decision, not an omission.
79. Spellcheck (Overleaf has one built in).
80. Commit.

## Phase 7 — Reproducibility (81–88)

81. Add a repo README section: how to reproduce each table.
82. Include exact commands (`yuna bench`, `yuna.bench.judge`, `robustness_ci.py`).
83. Document model versions and quantisation tags.
84. State the LoCoMo download command.
85. Confirm `robustness_ci.py` runs from a fresh clone.
86. **Publish the raw `results_judged.jsonl` files** — your strongest credibility
    signal. They live in gitignored `data/`, so use a GitHub release asset or
    Zenodo (Zenodo also gives a DOI).
87. Confirm the repo URL in the paper resolves.
88. Commit.

## Phase 8 — arXiv (89–100) 👤

89. Create an arXiv account.
90. Check whether **cs.CL requires an endorsement** for you. As an unaffiliated
    first-time submitter, likely yes.
91. ⚠️ **Start this early.** Endorsement means emailing a published researcher
    with your abstract and PDF, then waiting. Budget a week; it is the single
    biggest schedule risk. Run it in parallel with Phase 6, not after.
92. Primary category **cs.CL**; cross-list **cs.AI**.
93. Overleaf → ☰ menu → Download → **Source** (this is the zip arXiv wants).
94. Include the compiled `.bbl` — arXiv does not always run live BibTeX.
95. Test-compile the exact upload package in a clean folder to catch missing files.
96. Upload source, not just the PDF — arXiv compiles it itself.
97. Fix any arXiv-specific errors (it runs its own TeX Live).
98. Preview the generated PDF; confirm it matches Overleaf's.
99. Write the arXiv abstract field — plain text, no LaTeX macros, ≤1920 chars.
100. Pick **CC BY 4.0**, submit, then add the link to your CV, repo, and
     Masters applications. Announcement takes ~1 business day. 🎉

---

## The three honesty traps

Where a reviewer will probe — and where being straight buys credibility.

**1. full_history beats us overall (0.544 vs 0.457).**
Do not bury this; you would be caught immediately. Lead with it, then reframe:
it wins *because* LoCoMo's conversations are short enough that answers survive
the window, and you *prove* the advantage expires (−76%). Reporting a baseline
beating you, and explaining exactly why, is the strongest credibility move
available.

**2. LLM-as-judge is the primary metric.**
Acknowledge a 14B judge is imperfect. Mitigations: temperature 0, judge ≠
answerer, deterministic abstain scoring for c5, token-F1 reported alongside.
Human agreement study = future work.

**3. Precision without recall (199/200).**
You measured whether stored facts are *faithful*, not whether the extractor
*missed* facts. Downstream QA accuracy is the recall proxy. Also disclose
self-annotation (no second annotator, so no inter-annotator agreement).

Also disclose: MSC was **deliberately** not run — its sessions fit inside the
context window, so full_history would never truncate and length-invariance
could not appear.

---

## Writing conventions

- **Tense**: present for the paper's actions ("we evaluate"), past for
  experiments ("the extractor produced").
- **"We"** is standard and correct, even solo.
- **Never** *obviously, clearly, as expected* — if it's obvious, cut it; if not,
  you're bluffing.
- **Hedge precisely**: "length-invariant on LoCoMo", not "memory systems are
  length-invariant".
- **Captions state takeaways**: "Retrieval is length-invariant; stuffing
  collapses" ✓ / "Accuracy by condition" ✗.
- **One claim per subsection**, stated in the first sentence, then the table,
  then interpretation. Never make the reader infer your point from a table.
- Kill every *very, quite, really*.

---

## Critical path

**Phase 1 (compile) → Phase 3 (reading) → Phase 6 (polish) → Phase 8 (arXiv).**
Phases 2, 4, 5, 7 are support and can be compressed if time is short.

Biggest schedule risk is **step 91** (arXiv endorsement) — start it early and in
parallel.

## Division of labour

- **Delegable**: figures, LaTeX, prose drafting and polish, tables, captions,
  the claim ledger, arXiv package assembly, all analysis scripts.
- **👤 Only you**: reading the related work, judging stylistic calls, the
  read-aloud and fresh-eyes passes, authorship decisions, endorsement outreach,
  holding the arXiv account.
