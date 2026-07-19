# Gold annotation — extraction quality (RQ1)

`annotation_sheet.tsv`: 200 memories sampled (seed 42, ~20/conversation) from
the July 19 full agentic run (Gemma4-12B-QAT extractor, all 10 LoCoMo
conversations, 1,530 memories total). Open in any spreadsheet app, fill the
`verdict` column, keep it tab-separated.

## Labels for `verdict`

| label | meaning |
|---|---|
| `OK` | faithful to the conversation, correctly attributed, worth remembering |
| `BAD` | wrong: hallucinated, misattributed (wrong speaker), or contradicts the transcript |
| `VAGUE` | true but useless — too generic to ever answer a question ("X enjoys life") |
| `DUP` | (near-)duplicate of another stored memory you've seen in the sheet |
| `META` | conversation-state junk that slipped the filter ("X is asking about…") |

Rule of thumb: *would this line help answer a question about the speaker weeks
later?* OK if yes and accurate; otherwise the closest failure label.

Use `notes` for anything odd (e.g. "date wrong by a week", "should be EVENT
not FACT"). Check the matching transcript in `transcripts/<conv>.txt`
(Ctrl+F a keyword) whenever you're unsure — accuracy beats speed; this is the
paper's extraction-precision number.

When done: commit the TSV. `precision = OK / total`; per-kind and per-label
breakdowns get computed by a script once labels exist.
