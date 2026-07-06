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

**Last session:** 2026-07-06 — Fable 5 (Phases 4 + 5)
**Done:**
- Phase 4: `data/business_notes.csv` (21 notes: 6 signal / 15 noise, mapped in ground_truth.md §3, appended blind via shell) + `agents/variance_agent.py` — EUR/% variance for all 840 BU/line/month combos, three-rule materiality, episode grouping with one-month noise bridging, explanations grounded ONLY in cited notes else "no clear driver identified", trap excluded via the >4x/<0.25x rule. `output/variance_report.md` (20 material items, 4 evidence-grounded incl. the favorable savings) + `output/variance_table.csv` (now carries `materiality` and `evidence_notes` columns for downstream agents). `tests/validate_variance.py`: all 7 checks pass.
- Phase 5: `agents/forecast_agent.py` — rolling forecast 2026-07..09 for all 28 series, seasonal base (same month last year, from a NORMALIZED history) × robust growth (median YoY over trailing 12 months), consuming `output/variance_table.csv` (real pipeline chaining: Ingestion → Variance → Forecast). Normalization: data errors and one-off material months replaced by budget × typical achievement ratio; episodes kept only if still active within 2 months of cutoff. Full audit trail with evidence citations in `output/forecast_report.md` + grain in `output/forecast.csv`. `tests/validate_forecast.py`: all 8 checks pass, first run. Full 3-validator suite green.
**In progress:**
- Nothing — Phases 4 and 5 are complete
**Next step:**
- Phase 6: Narrative Agent — executive commentary from `output/variance_report.md` + `output/forecast_report.md` (variance story incl. the favorable one, forecast outlook, explicit "unexplained items for follow-up" list). First prose-producing agent: decide template-driven Python (consistent with pipeline) vs. showcasing an LLM call. Then QA/Reviewer Agent + orchestrator, then recruiter-facing README/diagram/demo.
**Decisions made (and why):**
- Variance materiality is three rules, not one: monthly dual threshold (≥10% of budget AND ≥EUR20k), monthly absolute trigger (≥EUR150k AND ≥7%, just above the business's routine ±6% revenue-noise band), and episode cumulative (same-direction ≥8% runs, cumulative ≥EUR40k and ≥10%, bridging one quiet month if the drift resumes). Absolute trigger + bridging were added after validation caught the FX dip (-9.3%) sliding under the 10% leg and a noise-masked month splitting the savings episode; the first calibration (EUR100k/5%) flooded the report with 25 routine-noise rows — the row count, not the validator, showed it.
- Evidence windows are tight (10 days back / 20 days ahead) with per-line keyword lexicons: a 45-day lookback initially produced a textbook false attribution (January FX note cited for an unrelated March COGS overspend).
- Digital's 2025-01 revenue dip is pure noise LARGER than the planted 2025-09 FX anomaly — the variance report's "no clear driver identified" row for it is intentional and validated; don't "fix" it.
- Forecast: normalization is where the judgment lives — a forecast is only as good as the history it extrapolates. One-offs (explained or not) never recur → normalized to budget × typical ratio; episodes carried forward ONLY if still running at cutoff. The handoff's "arguably persist the savings programme" resolved AGAINST persisting: N12/N16 promised savings through year-END 2025, and 2026 actuals are back at plan (episode ended 2026-02) — data over notes. Method is seasonal-naive × median-YoY because no future budgets exist in the dataset and it's explainable to a finance audience in two sentences.
- 16 of 20 material variance rows say "no clear driver identified" — realistic for a monthly pack, and the behavioral core of that agent: material-but-unexplained is a follow-up item, never a story to invent.
- (Phase 3 essentials, kept for handoff) `python` on PATH is a bare 3.11 venv — always use `.venv/Scripts/python.exe`. Business anomalies live in true actuals with data-quality issues layered on top. The trap is STILL uncorrected in the cleaned CSV — every downstream agent must handle it (variance excludes it, forecast normalizes it; the future QA agent should assert this).
