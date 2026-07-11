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
fpa-project/
├── CLAUDE.md               (2-line stub; imports dev/CLAUDE.md — do not delete)
├── README.md               (recruiter-facing: problem/solution/results + diagram)
├── orchestrator.py         (chains the agents; assembles output/board_pack.md)
├── make_charts.py          (regenerates docs/*.png from pipeline outputs)
├── requirements.txt
├── dev/                    (internal working docs — moved out of root 2026-07-10)
│   ├── CLAUDE.md           (this file: project brief + progress log)
│   ├── PROGRESS.md         (detailed log, one entry per session)
│   ├── AUDIT.md            (pre-publication audit findings, 2026-07-06)
│   ├── NOTES.md            (v2 rebuild: running decisions + validator catches)
│   └── DEMO_SCRIPT.md      (60-90s demo video: script + storyboard, user films)
├── data/
│   ├── generate_dataset.py
│   ├── generate_drivers.py (v2: seeded FTE + volume×price drivers, P&L-consistent)
│   ├── eventco_monthly.csv / eventco_monthly_cleaned.csv
│   ├── eventco_drivers.csv
│   ├── business_notes.csv
│   └── ground_truth.md     (answer key — agents never read it; tests/ do)
├── agents/
│   ├── ingestion_agent.py, variance_agent.py, forecast_agent.py,
│   ├── narrative_agent.py, qa_agent.py, bu_report_agent.py (v2)
│   └── grounding_check.py  (shared narrative-grounding logic)
├── tests/
│   └── validate_{ingestion,variance,forecast,narrative,drivers,bu_reports}.py
├── output/
│   ├── data_quality_report.md, variance_report.md, variance_table.csv,
│   ├── forecast_report.md, forecast.csv, executive_summary.md,
│   ├── qa_report.md, pipeline_log.md, board_pack.md
│   └── bu_reports/         (v2: per-BU one-pager, .md + .pdf)
├── showcase/               (v2: single-page site deployed to Vercel)
└── docs/
    ├── variance_bridge_2025.png   (flagship: FY2025 budget→actual waterfall)
    ├── variance_highlights.png
    └── forecast_outlook.png
```

## 7. Expected Deliverables (portfolio)

1. Simple architecture diagram (the 6 agents + data flow)
2. One automatically generated executive report (concrete example, real numbers
   from the synthetic dataset) — this is THE piece to show in interviews
3. Recruiter-friendly README: problem -> solution -> business impact (not code-first)
4. Ideally: a short demo (GIF/video) showing the pipeline running

## 8. PROGRESS LOG (update every session)

**Last session:** 2026-07-10/11 — Fable 5 (v2 rebuild: legibility + shopfront for a non-technical finance audience). Full detail in PROGRESS.md; running decisions in NOTES.md — read both before changing anything.
**Done (all verified in-session; 6/6 validators green, orchestrator end-to-end green):**
- **Repo hygiene:** PROGRESS/AUDIT/CLAUDE moved to `dev/`; root CLAUDE.md is a 2-line import stub (do not delete). `dev/NOTES.md` = v2 decision log, `dev/DEMO_SCRIPT.md` = video storyboard (user films it).
- **Driver dataset:** `data/generate_drivers.py` replays the main generator's seeded path to recover TRUE actuals in memory, derives monthly FTE + projects per BU (`data/eventco_drivers.csv`, clean by design), documents in `data/ground_truth_drivers.md`. All v1 committed outputs stayed byte-identical (this was the point; `tests/validate_drivers.py` is the tripwire). FX month = pure price (volume at budget, corroborates N08); trap month drivers reflect TRUE revenue, exposing the corrupted figure at 9.7x implied project value.
- **BU one-pagers (the new hero artifact):** `agents/bu_report_agent.py` (deterministic, no LLM) writes per-BU md + single-page PDF (fpdf2) + bridge PNG into `output/bu_reports/`: FY2025 scorecard + waterfall, payroll headcount/rate split, revenue volume/price split (reconcile exactly, asserted), material variances with grounded one-liners or "no clear driver identified", follow-ups, Q3 2026 outlook. Wired into orchestrator between Forecast and Narrative; board pack gained section 3 linking them. `tests/validate_bu_reports.py` recomputes every figure shown.
- **Showcase (LIVE):** `showcase/index.html`, deployed at **https://alanvourch.com/fpa-project/** via a `gh-pages` branch (Vercel connector had no project-create permission — see NOTES.md for the redeploy procedure). Outcome-first copy in Alan's voice (humanizer-checked), real raw rows vs generated outputs, the EUR52M trap story, one-pager PDFs downloadable, LinkedIn (linkedin.com/in/alan-vourch — USER MUST CONFIRM this is his profile), quiet GitHub footer link.
- **README re-thesis:** top now leads with "AI applied to the finance function, auditable and CFO-runnable" + the user-picked personal story (option B, employer generic); showcase linked; six agents documented; new Known limitation added (driver splits reconcile only because synthetic-consistent by construction).
**User decisions this session (do not re-litigate):** deploy publicly now; name + LinkedIn only (no email) on the page; story option B "concrete first"; employer stays generic (never name Auditoire in public artifacts).
**Next step:**
- User: confirm the LinkedIn URL on the showcase; film the demo per dev/DEMO_SCRIPT.md (set up `ant auth login` first and re-run narrative_agent.py + orchestrator.py for an authoritative LLM-generated summary — the committed one is still the hand-written provenance-noted version); optionally import the repo into Vercel dashboard if he prefers that URL.
**Earlier sessions (v1, condensed):** see the block below and PROGRESS.md.

**v1 summary (2026-07-06):**
**Done:**
- Pre-publication audit (AUDIT.md, committed on its own before any fix — read it for the full findings list). Verified with pandas that every figure in the executive summary traces to the variance/forecast reports; scanned all git history for secrets (clean, nothing to rotate); re-ran the pipeline end to end (byte-identical outputs except timestamps). Then fixed everything flagged: exec-summary time framing ("this year" → the actual 30-month window; cutoff is June 2026, not July), the Marketing savings episode window now disclosed as wider than the programme, orchestrator board pack now labels a carried-over narrative instead of claiming "included below" after a failed narrative step, `.gitignore` covers `.env`, deleted `output/sample_report.md` placeholder + stale `.gitkeep`s + empty `output/dashboard/`, duplicate typo-log entry deduped in ingestion.
- Writing pass per explicit user style rules, now enforced in the GENERATOR templates (agents/*.py, orchestrator.py), not just the outputs: zero em dashes and zero buzzwords in README.md and all output/*.md ("robust growth" → "median year-over-year growth"; report titles use colons). The narrative system prompt now bans em dashes/filler too. Validators updated where they parsed old headers (validate_ingestion section 6/7). CLAUDE.md/PROGRESS.md are internal and keep their style.
- Charts rebuilt via committed `make_charts.py` (was: no script in repo, PNGs irreproducible). New flagship `docs/variance_bridge_2025.png`: FY2025 budget→actual net-result waterfall (EUR52.0M → EUR48.9M, reconciles exactly, asserted in the script), named driver blocks + a hatched "no documented driver" block, trap row held at budget with a footnote. `variance_highlights.png` re-encoded as P&L impact (favorable always right, green/red per finance convention, CVD-validated palette); `forecast_outlook.png` adds normalized PY revenue markers. README fully rewritten (2-minute pitch, deterministic-vs-LLM rationale, Known limitations section covering the IQR 5/11 tier, episode over-detection, keyword trap-check gap, hand-written summary provenance, synthetic data; per-OS run instructions). `ant` CLI link verified live.
**Earlier (Phases 4-7, same day):**
- Phases 4-6 (Variance, Forecast, Narrative): full pipeline Ingestion → Variance → Forecast → Narrative built and chained via real file handoffs (`output/variance_table.csv` → `output/forecast_report.md` → `output/executive_summary.md`). Narrative Agent (`agents/narrative_agent.py`, `claude-sonnet-5`) is the ONE deliberate LLM call in the whole pipeline; every other agent is deterministic Python. Auth resolves automatically via a bare `anthropic.Anthropic()` client (API key OR `ant auth login` OAuth profile — no hardcoded credential). `output/executive_summary.md` was hand-written in an interactive session (not via an actual script run) because the user only has a Claude subscription and `ant` CLI install was sandbox-blocked this session; header documents this, re-run the real script once OAuth/API credentials are set up locally for the authoritative version.
- Phase 7 (QA/Reviewer Agent + Orchestrator): **reframed by explicit user correction mid-project — read this before touching the pipeline again.** The point of this whole repo is a portfolio piece proving the author can run a *supervised, multi-agent* FP&A process, NOT a fully autonomous one — and proving sensitive data isn't leaked to AI providers. Two concrete, checked (not just claimed) mechanisms now exist for this:
  - `agents/qa_agent.py` structurally verifies (a) no agent file other than `narrative_agent.py` references an external AI provider, and (b) `narrative_agent.py`'s actual `open()` calls are scoped to the two aggregated report files only (never the raw dataset or ground truth) — a source-code scan, not a comment someone could quietly invalidate. It also cross-checks pipeline-internal consistency (every material variance evidence-cited or explicitly unexplained; every flagged month accounted for in the forecast audit trail) without ever touching `data/ground_truth.md`.
  - `orchestrator.py` chains all steps as subprocesses and assembles `output/board_pack.md` — but every run ends with a literal **DRAFT — PENDING HUMAN SIGN-OFF** banner and a Reviewed-by/Approved-for-distribution sign-off block. Nothing in this pipeline sends anything anywhere on its own.
  - `agents/grounding_check.py`: the narrative hallucination-check logic (money/percent parsing, honesty checks) was extracted from `tests/validate_narrative.py` into a shared module both the QA Agent and the test script import — it never needed ground truth, so it's legitimately reusable in production.
  - Full 4-validator suite (ingestion/variance/forecast/narrative) re-run green after the orchestrator regenerated every file from scratch — the whole pipeline is reproducible end to end.
- README polish (stayed on Sonnet 5 — no architecture decision required, per the user's standing instruction to flag before switching): filled Problem/Solution/Results (previously empty), added a Mermaid architecture diagram embedded in README.md (renders on GitHub, colors the one LLM-calling node and the human sign-off gate), and two chart images in `docs/` (`variance_highlights.png` — the flagship visual, hatched vs solid distinguishing "no clear driver identified" from evidence-grounded; `forecast_outlook.png` — Q3 2026 P&L). Built following the dataviz skill's procedure.
**In progress:**
- Nothing — audit + fixes pass is complete; repo is in publish-ready state.
**Next step:**
- A demo (GIF/video of `orchestrator.py` running) is the one remaining open item — recording a terminal session isn't achievable from this environment, so it's a task for the user locally. Once `ant auth login` or an API key is set up, re-run `agents/narrative_agent.py` for the authoritative script-generated narrative (the committed one is hand-written per its header; note the new system prompt bans em dashes so a fresh run stays style-compliant), then `orchestrator.py` once more for a fully-real end-to-end run to use in that demo.
**Decisions made (and why) — see PROGRESS.md for full reasoning on each:**
- Project positioning (Phase 7 reframe): human-in-the-loop control and provable data non-leakage are the two things this portfolio must demonstrate, not full automation — every Phase 7 design choice serves one or both of these.
- Narrative Agent model: Sonnet 5 (writing-quality step-up over Haiku is worth it for the one deliverable recruiters read closely; Fable 5 is reserved for hard architecture calls per §5, not needed here).
- Money-hallucination tolerance is tight (0.5% relative AND EUR15,000 absolute) — demonstrated twice that looser tolerances let fabricated round numbers coincidentally match unrelated real figures out of ~280 candidates in the two reports.
- Variance materiality is three rules (dual threshold, absolute trigger, episode cumulative with one-quiet-month bridging) — each addition was driven by a validator catching a real miss, not designed upfront.
- Forecast normalization: one-offs (explained or not) never recur → normalized; episodes carried forward ONLY if still active at cutoff. Data over notes when they conflict (the Marketing savings programme's own notes said "through year-end" but 2026 actuals showed it had already concluded).
- 16 of 20 material variance rows and 16 of 34 flagged forecast rows have "no clear driver identified" / normalized-as-unexplained — realistic for a monthly pack; material-but-unexplained is a follow-up item, never a story to invent, and this discipline is the throughline across every agent in this pipeline.
- (Phase 3 essentials, kept for handoff) `python` on PATH is a bare 3.11 venv — always use `.venv/Scripts/python.exe`. Business anomalies live in true actuals with data-quality issues layered on top. The fat-finger trap (Production revenue 2025-11) is STILL uncorrected in the cleaned CSV — every downstream agent must handle it itself (variance excludes it, forecast normalizes it, QA agent confirms coverage).
