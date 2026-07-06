# FP&A Agent Team — Project Brief & Working Memory

> This file is read automatically by Claude Code at the start of each session.
> It serves as persistent memory across sessions and across models (Fable -> Sonnet -> Opus).
> Update the "PROGRESS LOG" section at the end of every session before closing.

## 1. Project Goal

Build a multi-agent system that automates a full monthly FP&A cycle:
**Budget vs Actual variance analysis + rolling forecast update**, for a fictional
company "EventCo" (experiential marketing / events agency, ~€100M revenue, 150 FTE,
multiple business units) — sized to mirror the author's real Auditoire experience.

**End goal: portfolio project** aimed at finance recruiters (not developers).
The deliverable must be understandable without any AI/technical background: a clear
diagram, a demo, a before/after story ("what a manual FP&A cycle takes days to do,
this pipeline does with human-in-the-loop supervision").

Do NOT oversell agentic AI jargon in the final presentation — sell the business
outcome (automatically generated, consistent executive reports with root-cause
analysis).

## 2. Scope (do not exceed)

- One process only: monthly Budget vs Actual + Rolling Forecast, multi-BU
- One synthetic dataset (see section 4)
- No real Société Générale / Auditoire data — everything is fictional/generated
- All code, comments, docstrings, and documentation in English

## 3. Agent Team

| Agent | Role | Input | Output |
|---|---|---|---|
| Data Ingestion Agent | Cleans/structures raw data | Raw CSVs (GL, budget, actuals) | Normalized tables |
| Variance & Root-Cause Agent | Computes variances by BU, identifies plausible causes | Normalized tables | Variance table + explanations |
| Forecast Agent | Updates the rolling forecast | Actuals + historical trends | Forecast N+1 to N+3 |
| Narrative Agent | Writes executive commentary, board-deck style | Variances + forecast | Executive summary text |
| QA/Reviewer Agent | Checks consistency, catches errors | All outputs | QA report / flags |
| Orchestrator | Chains the agents above, manages the flow | — | Final assembled report |

## 4. Dataset (synthetic, generated — no real data)

Fictional company "EventCo":
- ~€100M revenue, 150 FTE, 4 business units (Production, Marketing, Digital, Back-Office)
- 30 months of monthly data: Revenue, COGS, Payroll, Opex (Travel, Marketing, IT,
  Facilities), by BU, with Budget / Actual / Prior Year columns
- Generated with Python (pandas + Faker/numpy), kept to a reasonable volume
  (monthly aggregate by BU, not transaction-level) — this keeps token usage down when
  agents process the data

Two distinct categories of planted issues, kept separate because they belong to
different agents:

**a) Business anomalies (Variance Agent's job — explain them):**
- One BU significantly over-budget in one quarter due to a large client project overrun
  (unfavorable)
- An FX-driven variance on an international client contract (unfavorable)
- A one-off cost spike tied to a plausible one-time event (unfavorable)
- One favorable variance — e.g. cost savings or under-spend in a BU beating budget —
  so the final report isn't one-sided ("everything is bad")

**b) Data quality issues (Ingestion/QA Agent's job — clean them, not explain them):**
- Typos in BU/category names (e.g. "Producton", inconsistent casing "digital" vs "Digital")
- Duplicate rows (same month/BU entered twice)
- Missing values in some Opex categories
- Inconsistent date formats across rows
- Amounts stored as text with currency formatting ("€120,000" instead of 120000)
- **One trap**: a data entry error (e.g. an extra digit) that LOOKS like a large
  business anomaly but is actually a fat-finger mistake. The Ingestion/QA Agent must
  catch and correct it before it reaches the Variance Agent — otherwise the Variance
  Agent will invent a plausible-sounding root cause for a typo. This distinction
  (real anomaly vs. data error) is the detail that demonstrates senior-level FP&A
  judgment, not just generic "data cleaning."

A ground-truth file (data/ground_truth.md) documents both categories separately —
business anomalies and data quality issues, including the trap and what the correct
resolution should be — so agent outputs can be checked against it later.

## 5. Model Strategy (constraint: Claude Pro subscription, not Max/API)

- **Fable 5**: reserved for the hard decisions only — the Variance/Root-Cause agent's
  reasoning logic, the Forecast agent's methodology, overall architecture calls.
  Short, targeted sessions — no long autonomous runs (Pro quota doesn't support that).
- **Sonnet 5**: repo scaffolding, dataset generation, routine code, dashboard,
  README writing.
- **Handoff**: at the end of every session, regardless of model, update the PROGRESS
  LOG below + commit to git. The next session (even on a different model) starts by
  reading this file + PROGRESS.md.

## 6. Repo Structure

```
fpa-agent-team/
├── CLAUDE.md              (this file)
├── PROGRESS.md             (detailed log, one entry per session)
├── README.md               (recruiter-facing: diagram + results)
├── data/
│   ├── generate_dataset.py
│   ├── eventco_monthly.csv
│   └── ground_truth.md
├── agents/
│   ├── ingestion_agent.py
│   ├── variance_agent.py
│   ├── forecast_agent.py
│   ├── narrative_agent.py
│   └── qa_agent.py
├── orchestrator.py
├── output/
│   ├── sample_report.md
│   └── dashboard/ (or Power BI/Plotly notebook)
└── docs/
    └── architecture_diagram.png
```

## 7. Expected Deliverables (portfolio)

1. Simple architecture diagram (the 6 agents + data flow)
2. One automatically generated executive report (concrete example, real numbers
   from the synthetic dataset) — this is THE piece to show in interviews
3. Recruiter-friendly README: problem -> solution -> business impact (not code-first)
4. Ideally: a short demo (GIF/video) showing the pipeline running

## 8. PROGRESS LOG (update every session)

**Last session:** 2026-07-06 — Fable 5 (Phase 4)
**Done:**
- New supporting data source `data/business_notes.csv`: 21 dated, BU-tagged internal business notes — 6 genuinely correlate with the 4 planted anomalies, 15 are realistic noise so evidence matching isn't trivial. Documented in ground_truth.md section 3 (appended blind via shell; the file's contents were never read in-session). Rationale: numbers say WHERE/HOW MUCH, only business context says WHY.
- `agents/variance_agent.py` (never reads ground_truth.md): EUR + % variance for all 840 BU/line/month combos from the cleaned CSV, three-rule materiality (see decisions), sustained-drift episode grouping with one-month noise bridging, and explanations grounded ONLY in cited notes (BU + tight date window + per-line keyword lexicon) — otherwise an explicit "no clear driver identified". Rows breaching the >4x/<0.25x data-error rule are excluded up front, so the fat-finger trap stays a data issue, never a business story.
- Outputs: `output/variance_report.md` (20 material items: 4 evidence-grounded incl. the favorable Marketing savings, 16 honest no-driver flags, trap excluded) + `output/variance_table.csv` (full grain).
- `tests/validate_variance.py` (same post-hoc pattern as Phase 3): all 11 anomaly-months flagged material, every anomaly explained via its own signal notes, zero false attributions, zero noise notes cited, zero invented causes, favorable marked F, trap not narrated. **All 7 checks pass**; re-ran validate_ingestion.py — still green.
- Updated PROGRESS.md (full judgment-call detail there) and committed
**In progress:**
- Nothing — Phase 4 (Variance & Root-Cause Agent) is complete
**Next step:**
- Phase 5: Forecast Agent — rolling forecast 2026-07..09 (N+1..N+3; data ends 2026-06) from the cleaned CSV. Must (1) exclude/correct the STILL-uncorrected Production revenue 2025-11 trap before fitting trends (ingestion flags it but deliberately doesn't auto-correct), and (2) not extrapolate known one-offs (Falcon overrun, IT spike) while arguably persisting the Marketing savings programme (notes N12/N16 say it continues through year-end) — that's this phase's judgment-demonstrating detail.
**Decisions made (and why):**
- Materiality is three rules, not one: monthly dual threshold (≥10% of budget AND ≥EUR20k), monthly absolute trigger (≥EUR150k AND ≥7% — a EUR150k miss ~2% of monthly group revenue matters regardless of the 10% tolerance, and 7% sits just above the business's routine ±6% revenue-noise band), and episode cumulative (runs of same-direction ≥8% months, cumulative ≥EUR40k and ≥10%, bridging one quiet month if the drift resumes). The absolute trigger and bridging were added after validation caught real misses (the planted FX dip came in at -9.3%, under the 10% leg; one noise-masked month split the savings episode). First absolute-trigger calibration (EUR100k/5%) flooded the report with 25 routine-noise rows — the row count, not the validator, showed that was wrong.
- Evidence windows are tight (10 days back / 20 days ahead): a 45-day lookback initially produced a textbook false attribution (January FX note cited for an unrelated March COGS overspend).
- The notes were first placed by reading the cleaned data alone, and the FX note landed on Digital 2025-01 — which ground truth revealed to be pure noise, LARGER than the planted 2025-09 FX anomaly. Re-dated the note to the real event; the January dip now honestly reads "no clear driver identified". Accidental but valuable stress test: the report visibly declines to explain its biggest tempting-but-unevidenced variance.
- 16 of 20 material rows say "no clear driver identified" — realistic for a monthly pack, and the behavioral core of this agent: material-but-unexplained is a follow-up item, never a story to invent.
- (Phase 3 essentials, kept for handoff) `python` on PATH is a bare 3.11 venv — always use `.venv/Scripts/python.exe`. Business anomalies live in true actuals with data-quality issues layered on top. Ingestion outlier check uses actual/budget ratio with the >4x/<0.25x error cutoff; its IQR tier catches only 5/11 anomaly-months (documented informational-only limitation).
