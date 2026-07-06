# FP&A Agent Team — EventCo Budget vs Actual & Rolling Forecast

## Problem

## Solution

## Architecture

Six steps, each reading the previous step's output rather than the raw data — the same
handoff a real FP&A team would use, just automated:

**Ingestion → Variance & Root-Cause → Forecast → Narrative → QA → Orchestrator**

### Why most of this is plain Python, and only one step calls an LLM

Every step through the Forecast Agent is deterministic code: fuzzy-matching business unit
names, applying a materiality threshold, deciding whether a variance is a one-off or a
sustained trend, normalizing history before projecting it forward. These are the decisions
that need to be **auditable and reproducible** — the same input has to produce the same
threshold check every time, and a reviewer has to be able to read the code and see exactly
why a number was flagged, explained, or adjusted. Handing that kind of judgment to an LLM
would make the pack's most important numbers non-reproducible and much harder to defend to
an auditor or a board.

Turning already-computed, already-cited conclusions into a clear executive narrative is a
different kind of problem — it's a language task, not an arithmetic one, and that's exactly
what an LLM is good at. So the **Narrative Agent is the only step in this pipeline that
calls Claude** (Sonnet 5). It is given the finished Variance and Forecast reports and
instructed never to introduce a number, cause, or conclusion that isn't already in them —
the reasoning that could hallucinate a root cause already happened upstream, in plain code
that only cites evidence it can point to (or says plainly that it found none). A separate
validation script checks this after the fact: every figure the narrative mentions is traced
back to a source figure, and it fails loudly if one doesn't match.

### Setup for the Narrative Agent

The Narrative Agent (`agents/narrative_agent.py`) constructs a bare `anthropic.Anthropic()`
client and never hardcodes a credential — it works with whichever of these you set up:

**Option A — API key** (a metered, pay-per-token credential):

```
export ANTHROPIC_API_KEY=sk-ant-...   # macOS/Linux
$env:ANTHROPIC_API_KEY = "sk-ant-..."  # Windows PowerShell
```

**Option B — OAuth via your Claude account** (no separate API key needed — this is the
path used for this project, consistent with the Claude Pro subscription constraint in
CLAUDE.md section 5). Install the [Anthropic CLI](https://github.com/anthropics/anthropic-cli)
(`ant`), then run:

```
ant auth login
```

This opens a browser, authenticates against your Claude account, and stores a short-lived
OAuth profile that the Python SDK picks up automatically — no environment variable required.

### Data governance and human control

This isn't a fully autonomous "black box" — and given financial data sensitivity, it isn't
meant to be:

- **Only one component ever touches an external AI provider.** Ingestion, Variance,
  Forecast, and QA are 100% deterministic Python — no data from those steps leaves the
  local machine. Only the Narrative Agent calls Claude, and it only ever receives the two
  *already-aggregated* summary reports (BU/month-level variance and forecast tables) —
  never the raw dataset, never anything below that aggregation level.
- **This is checked, not just claimed.** The QA/Reviewer Agent (`agents/qa_agent.py`)
  structurally verifies both of the above on every run: it scans every other agent's source
  for any reference to an external AI provider, and confirms the Narrative Agent's own file
  reads are scoped to the two report files. A regression here fails the QA report loudly,
  the same way a hallucinated figure does.
- **Nothing is sent to anyone automatically.** The Orchestrator (`orchestrator.py`) chains
  the pipeline end to end and assembles a single draft pack (`output/board_pack.md`), but
  that pack is explicitly marked **DRAFT — PENDING HUMAN SIGN-OFF** with a literal
  reviewed-by/approved-for-distribution line at the bottom. No step in this pipeline
  publishes, emails, or exports anything — a human always reviews the pack and the QA
  report before either goes anywhere.

## Results

## Tech Stack
