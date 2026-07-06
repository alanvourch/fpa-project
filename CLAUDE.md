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

**Last session:** 2026-07-06 — Sonnet 5
**Done:**
- Created the full repo structure from section 6 (data/, agents/, output/, output/dashboard/, docs/) plus placeholder files for every agent, orchestrator.py, and output/sample_report.md
- Wrote data/generate_dataset.py: seeded (42), synthetic 30-month EventCo dataset (4 BUs, 150 FTE, ~€100M/yr revenue) with events-industry seasonality (Q2/Q4 peaks)
- Planted and documented the 4 required business anomalies (Production Q2 2025 client overrun, Digital FX variance, Back-Office one-off IT cost spike, Marketing favorable cost savings) and all required data quality issues (BU typos, missing Opex values, currency-formatted text amounts, mixed date formats, duplicate rows, plus the fat-finger revenue trap)
- data/ground_truth.md is generated programmatically from the actual corruptions applied, so it can't drift from the CSV
- Generated data/eventco_monthly.csv (124 rows incl. 4 planted duplicates); verified it loads cleanly in pandas and totals look realistic (~€263M revenue actual across 30 months x 4 BUs)
- Created README.md skeleton (section headers only, no content yet)
- Initialized git (no repo existed before this session) and committed everything
**In progress:**
- Nothing — Phase 2 (scaffold + dataset) is complete
**Next step:**
- Phase 3: build the Data Ingestion Agent first (clean the planted DQ issues in eventco_monthly.csv, self-checking against ground_truth.md), then the Variance & Root-Cause Agent
**Decisions made (and why):**
- The `python` on PATH resolves to a bare 3.11 venv without pandas/numpy/faker; used `C:\Users\snip1\AppData\Local\Programs\Python\Python312\python.exe` directly instead. Worth setting up a proper project venv in Phase 3.
- Dataset window is 2024-01 through 2026-06 (ends the month before "today") instead of an arbitrary historical window, so the Rolling Forecast Agent gets a natural "forecast from here" cutoff later
- Business anomalies are baked into the "true" actuals (they're real economic events); data-quality corruptions are layered on top afterward, so the generator code keeps the two concerns mechanically separate — mirrors the separation between the Variance Agent's job and the Ingestion/QA Agent's job
