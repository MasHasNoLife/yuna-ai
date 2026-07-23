# The 1–100 Guide to Writing the Paper

A concrete, ordered checklist from "drafts exist" to "arXiv live". Specific to
this paper (Yuna / agentic memory / LoCoMo). Tick as you go. Steps marked 👤 need
you (a human); the rest I can do or help with.

---

## Phase A — Set up the machinery (1–12)

1. Create an Overleaf project (or local LaTeX). Use the arXiv-friendly template
   for a workshop paper (e.g. the ACL/EMNLP style or a neutral article class).
2. Pick target length: 6–8 pages body + references. Set the template to match.
3. Make a `paper/` LaTeX skeleton: `main.tex` + one `.tex` per section.
4. Port each drafted markdown section (`results.md`, `method.md`, …) into its
   `.tex` file — content first, formatting later.
5. Create `references.bib` (empty for now).
6. Set up a figures folder; decide format (PDF/SVG for vectors, PNG for raster).
7. Add a `\todo{}` macro so every open item is visible in the compiled PDF.
8. Commit the skeleton so LaTeX changes are version-controlled alongside code.
9. Decide authorship line now (solo, or leave room for a coauthor). 👤
10. Write the title on the title page (working title is fine; finalize at step 88).
11. Confirm the numbers you'll cite are frozen: the judged tables in
    `RESEARCH_PLAN.md` §3.5 are the single source of truth.
12. Make a one-line "claim ledger": every number that appears in the paper → the
    file it came from. Prevents drift between text and data.

## Phase B — Lock results and figures (13–30)

13. Re-run nothing unless a number is uncertain; you have the data.
14. **Figure 1 (length-invariance)** — the signature figure. Plot judged accuracy
    for full_history vs agentic vs raw_rag, in-window vs truncated.
15. Make Fig 1 a simple 2-point line per strategy: a flat line (agentic) crossing
    a falling line (full_history). Label the −76% drop and the 2.0× gap.
16. Caption Fig 1 with the takeaway, not just a description ("Retrieval-based
    memory is length-invariant; context-stuffing collapses past its window").
17. **Figure 2 (architecture)** — the 3-stage per-turn pipeline: recall → generate
    → async extract, with the vector store and the typed ops.
18. Keep Fig 2 clean: boxes + arrows, one path highlighted (the async extraction
    that doesn't block the reply).
19. **Figure 3 (temporal ablation)** — bar chart: temporal accuracy grounding-off
    vs grounding-on. You need the "off" number (step 20).
20. Re-run the agentic condition once with temporal grounding disabled to get the
    real "before" number (currently asserted ~0.00 from the pilot). One GPU run.
21. Build **Table 1** (strategies, judged) from the frozen numbers.
22. Build **Table 2** (length-invariance split, judged).
23. Build **Table 3** (extractor ladder, judged).
24. Build the small **context-efficiency table** (889 vs 59,585 chars, 67×).
25. Decide which go in-body vs appendix (Tables 1–3 + Figs 1–3 in body).
26. Double-check every table number against the claim ledger (step 12).
27. Add per-category breakdowns (c1–c5) to an appendix table for completeness.
28. Note the c5/abstain caveat directly under Table 1 so no reader misreads
    `none = 0.228`.
29. Export all figures at final resolution; embed in the skeleton.
30. Compile the PDF once — confirm figures/tables render before writing prose.

## Phase C — Related work reading (31–42) 👤 (mostly you)

31. Read **MemGPT**: note its memory mechanism and what model it assumes.
32. Read **Mem0**: extraction method, local vs API, how it updates/dedupes.
33. Read **Generative Agents**: retrieval scoring (recency/importance/relevance),
    reflection.
34. Read **LoCoMo paper**: exact size, category definitions, original metrics —
    so you can state precisely what you changed (judged + abstain + length split).
35. Skim **MSC**: setup + persona-consistency metric (for §4.1 and future work).
36. One sentence each for **RAG** and **Self-RAG**.
37. Find 2–3 refs on small-model / quantisation capability gaps.
38. For each paper, write the "unlike them, we…" sentence immediately.
39. Add each to `references.bib` as you read it (never batch this later).
40. Replace every `⟨verify⟩` marker in `related_work.md` with a checked claim.
41. Cut any paper you can't tie to your argument in one sentence.
42. Target ~15 references total; quality over quantity for a short paper.

## Phase D — Write/polish section by section (43–72)

*(Order matters: body first, intro/abstract last. Drafts already exist — this is
refinement, not blank-page writing.)*

43. **Method §3**: verify every mechanism described matches the code exactly.
44. Confirm the typed-ops list (FACT/EVENT/SELF/UPDATE/FORGET) is complete + correct.
45. Make sure temporal grounding (§3.3) is described as the isolable mechanism it is.
46. State the dedup threshold (0.15), k=4 recall, async design precisely.
47. Reference Fig 2 from §3.1.
48. **Setup §4**: confirm LoCoMo size, categories, and your metric changes.
49. State hardware (RTX 4070 12 GB), Ollama, ChromaDB, nomic-embed, sampling params.
50. Explain the judge setup + why judge ≠ answerer (bias control).
51. Explain abstain scoring + the c5 floor caveat here too.
52. **Results §5**: make every sentence point to a table/figure number.
53. §5.1 — present Table 1; state the honest "full_history wins overall" up front.
54. §5.2 — temporal win + the grounding ablation (needs Fig 3 / step 20).
55. §5.3 — length-invariance (Table 2, Fig 1). This is the climax; write it carefully.
56. §5.4 — the 67× efficiency point.
57. §5.5 — extractor ladder (Table 3); the "≈7–14B floor, temporal breaks first".
58. §5.6 — cost/interactivity (TTFT, tok/s, VRAM).
59. Add extraction-precision subsection once gold annotation is done (step 63).
60. **Discussion §6**: keep the honest scoping ("we do not claim universal recall").
61. Make the length-invariance reframe explicit ("the regime stuffing wins is the
    one a companion grows out of").
62. Keep the threats-to-validity list (judge bias, abstain floor, single benchmark).
63. 👤 **Gold annotation**: label the 200 ops in `data/gold/annotation_sheet.tsv`
    (OK/BAD/VAGUE/DUP/META). 2–3 evenings.
64. Compute extraction precision from the labels; add to §5.5b and Discussion.
65. **Intro §1**: tighten the drafted version; ensure it previews every result.
66. Decide on the opening line ("sequence of strangers") — keep or fall back. 👤
67. Make the 4 contributions match exactly what the body delivers.
68. **Abstract**: ensure every number matches the final tables (claim ledger).
69. **Conclusion**: 3 sentences — memory beats stuffing where it counts, cheaply,
    locally.
70. Write figure/table captions to stand alone (a skimmer reads only these).
71. Add a short "Reproducibility" paragraph (repo link, seeds, judge prompts).
72. Add a "Limitations" section if the venue requires it (ACL-style) — you can
    lift from §6.3.

## Phase E — Integrate the full draft (73–82)

73. Compile the whole thing; read it start to finish once, out loud. 👤
74. Fix the seams: transitions between sections, repeated sentences, undefined terms.
75. Ensure the spine sentence (small local memory, length-invariant, cheap) is
    visible in Abstract, Intro, Results, and Conclusion.
76. Check every claim has a citation or a table/figure behind it.
77. Verify no orphan `\todo{}` remains (compile shows them).
78. Check figure/table references resolve (no "Table ??").
79. Trim to length: kill any sentence that doesn't serve the spine.
80. Confirm the paper reads as "here's an honest, sharp finding" not "we win
    everything" — reviewers reward the former.
81. Second full read for flow only (ignore content). 👤
82. Freeze the draft; tag the commit `draft-v1`.

## Phase F — Review and revise (83–92)

83. Send `draft-v1` to 1–2 readers: a coauthor/professor, or a sharp peer. 👤
84. If doing supervisor outreach, this is the artifact you attach. 👤
85. Collect feedback; triage into must-fix / nice-to-have / won't-do.
86. Address must-fix: usually clarity, a missing baseline, or an overclaim.
87. If a reviewer questions generality → run **MSC** as the second benchmark
    (one GPU run) and add §5.7.
88. Finalize the title (descriptive + a hook; e.g. "Memory That Doesn't Expire").
89. Re-verify every number one last time against the claim ledger.
90. Proofread for typos/grammar (a pass with fresh eyes, or a tool). 👤
91. Check formatting: margins, font, page limit, reference style.
92. Tag `draft-v2` (submission candidate).

## Phase G — Ship to arXiv (93–100)

93. Make an arXiv account; get endorsement if required for cs.CL (may need a
    referral — ask a published contact, or it may auto-clear from affiliation). 👤
94. Prepare the arXiv package: `main.tex`, all `.tex`, `references.bib`, figures,
    and the compiled `.bbl` (arXiv wants the bbl, not live BibTeX sometimes).
95. Test-compile the exact upload package in a clean folder to catch missing files.
96. Write the arXiv abstract (plain text, ≤1920 chars) — trim from step 68.
97. Pick categories: primary **cs.CL**, secondary **cs.AI** / **cs.LG**.
98. Upload, preview the generated PDF on arXiv, fix any compile issues.
99. Submit; note the arXiv ID once it clears (usually next business day). 👤
100. Add the arXiv link to your CV/SOP and the repo README; you're citable. 🎉

---

### The critical path (if you only do the essentials)
Figures (14–20) → finish Results/Method/Setup prose (43–58) → Related Work
(31–42) → Intro/Abstract (65–69) → full read (73–82) → arXiv (93–100).
Gold annotation (63) and MSC (87) are strengthening, not blocking — the paper
ships without them if time is tight.

### What I can do vs what needs you
- **I can do:** all figures, all LaTeX porting/skeleton, every prose section
  draft/polish, tables, captions, the claim ledger, the arXiv package assembly.
- **Only you (👤):** read the related-work papers, do the gold annotation, judge
  the stylistic calls, choose authorship, send outreach, hold the arXiv account.
