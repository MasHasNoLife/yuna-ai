# 3. Method

We describe the agentic memory system as implemented in the open-source
reference application (Yuna). The design goal is a *persistent* conversational
agent — one that remembers across sessions and weeks — running entirely on a
single consumer GPU, with no cloud model in the loop. The same code path runs
the live application and the benchmark; the evaluation drives it headlessly.

## 3.1 Overview

Each turn proceeds in three stages:

1. **Recall.** The user message (plus the previous one, for pronoun context) is
   embedded and used to retrieve the most relevant stored memories, which are
   injected into the prompt alongside the agent's own persona facts and a
   date/time preamble.
2. **Generation.** The chat model produces the reply, streamed to the user.
3. **Extraction.** *After* the reply is sent, a background call to the extractor
   model converts the exchange into typed memory operations and applies them to
   the store. Because this runs after streaming, it never delays the reply.

Memory is a single vector store (ChromaDB) with typed metadata; there is no
separate symbolic database. *(Figure 2: the three-stage per-turn pipeline.)*

## 3.2 The typed memory protocol

The core mechanism is a structured extraction protocol. Given the new exchange,
the recent context, and the currently recalled facts, the extractor model emits
zero or more typed operations:

- **[FACT]** — a durable truth about the user or world ("Mas's favorite dish is
  carbonara").
- **[EVENT]** — a dated happening ("Mas started a new job").
- **[SELF]** — a durable fact the agent revealed about *itself*, routed to a
  separate self-partition so the agent maintains a stable autobiography rather
  than improvising a contradictory one each turn.
- **[UPDATE]** old → new — a correction to an existing fact.
- **[FORGET]** — deletion, triggered only when the user denies or retracts
  something already stored.

Two safeguards keep the store clean. **Denial handling:** when the user negates
something ("there is no such project"), the extractor issues a FORGET against a
matching stored fact if one exists, and otherwise emits nothing — critically,
the denial itself is never stored as a fact. **A junk filter:** a regex backstop
rejects conversational meta-states ("the user is asking about X", "is in a good
mood") that the model occasionally emits despite instructions, so no caller can
persist them. Parsing is a pure function, unit-tested independently of any model.

## 3.3 Temporal grounding

Relative time expressions ("last Saturday", "last year") are meaningless once
divorced from the moment they were spoken. The extractor is therefore given the
current date and instructed to **absolutize** relative dates inline when it
writes an EVENT ("ran a charity race *(on 20 May 2023)*"), and each memory is
**timestamped with the date of the session it came from**, not the wall-clock
time of ingestion. This single mechanism is responsible for the temporal-reasoning
result in §5.2: the answerer reads a resolved date directly instead of
attempting date arithmetic over a long transcript.

## 3.4 Recall and storage

**Query construction.** The embedding query concatenates the current and
previous user message, so pronoun-heavy follow-ups ("no, the *one I told you
about*") still retrieve the right memory.

**Age-aware results.** Retrieved EVENT and session memories are annotated with a
human-readable age ("(3 days ago) …") derived from their stored timestamp, giving
the model a sense of recency at answer time.

**Deduplication on insert.** A new memory is rejected if its embedding distance
to an existing memory in the same partition falls below a threshold (0.15).
Paraphrase duplicates measure 0.06–0.10 in this space while genuinely distinct
facts sit at 0.23 and above, so the threshold suppresses re-storage of restated
facts without collapsing distinct ones. Retrieval returns the top *k* = 4
threshold-filtered memories per turn.

**Self-partition.** The agent's own [SELF] facts live in a dedicated partition
and are injected every turn (sampled, not fixed) so the character has a stable,
non-repetitive autobiography.

## 3.5 Asynchronous, non-blocking design

Extraction is the expensive step (a full model call), but it is not on the
interactive path: it is dispatched as a background task after the reply streams,
so time-to-first-token depends only on recall and generation. On session end,
the conversation is compressed into a one-to-two-sentence summary stored as a
session memory and injected at the start of the next session, giving continuity
across sessions without replaying full transcripts.

## 3.6 Memory strategies as experimental conditions

The same harness supports four memory pathways, which form the independent
variable in §5.1:

- **none** — no memory; the model answers from the current turn only.
- **full_history** — the entire transcript is placed in the context window
  (capped at the most recent 60k characters ≈ 15k tokens).
- **raw_rag** — every dialogue turn is stored verbatim and retrieved by
  embedding similarity; no extraction.
- **agentic** (ours) — the typed protocol above: only distilled, dated,
  deduplicated memories are stored and retrieved.

Holding everything else fixed, these isolate the contribution of *extraction*
(agentic vs. raw_rag) and of *retrieval* (both vs. full_history and none).
