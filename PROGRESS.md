# Progress Log

Detailed session-by-session log. See CLAUDE.md section 8 for the current summary; this file keeps the full history as the project grows.

## 2026-07-06 — Sonnet 5 — Phase 2: Repo scaffold + synthetic dataset

**Done:**
- Full repo structure per CLAUDE.md section 6: data/, agents/, output/, output/dashboard/, docs/, plus placeholder files for every agent, orchestrator.py, and output/sample_report.md
- data/generate_dataset.py: seeded (42) synthetic 30-month EventCo dataset (4 BUs, 150 FTE, ~€100M/yr revenue), events-industry seasonality
- 4 business anomalies planted (client project overrun, FX variance, one-off IT cost spike, favorable cost savings) and 6 categories of data quality issues planted (BU typos, missing Opex values, currency-formatted amounts, mixed date formats, duplicate rows, fat-finger revenue trap)
- data/ground_truth.md generated programmatically from the actual corruptions applied
- data/eventco_monthly.csv generated (124 rows incl. 4 duplicates), verified in pandas
- README.md skeleton (headers only)
- git repo initialized and everything committed

**Decisions:**
- Use `C:\Users\snip1\AppData\Local\Programs\Python\Python312\python.exe` directly — the `python` on PATH is a bare 3.11 venv without pandas/numpy/faker
- Dataset window: 2024-01 to 2026-06 (ends the month before "today") for a natural forecast cutoff later
- Business anomalies baked into true actuals; data-quality issues layered on top afterward — keeps the Variance Agent's concerns separate from the Ingestion/QA Agent's concerns from the ground up

**Next:** Phase 3 — Data Ingestion Agent, then Variance & Root-Cause Agent.

## 2026-07-06 — Sonnet 5 — Phase 3: Data Ingestion Agent

**Done:**
- Project venv (`.venv/`) with pandas 3.0.3 / numpy 2.5.1 / Faker 40.28.1, pinned in `requirements.txt`. Verified the seeded dataset generator still produces byte-identical `eventco_monthly.csv` on these newer versions — no reproducibility regression.
- `agents/ingestion_agent.py`, built without ever reading `data/ground_truth.md`:
  - BU/category typos fixed via fuzzy match (`difflib`) against the 4 canonical BU names
  - Duplicate (month, BU) rows detected and dropped, keeping the first occurrence
  - Currency-formatted text amounts ("EUR120,000", "120,000 EUR") parsed to numeric via regex strip + float cast
  - Mixed date formats (ISO, US, "Month YYYY", YYYY/MM) normalized via `pd.to_datetime` flexible inference, output as canonical ISO
  - Missing Opex values imputed via linear interpolation on each BU's own monthly time series (edge gaps carried in from nearest value); every imputed cell logged
  - Outlier flagging: actual/budget ratio per BU/column, with an IQR fence (informational "notable variance") and a >4x / <0.25x magnitude rule ("likely data entry error") — see judgment call below
- Outputs: `data/eventco_monthly_cleaned.csv` (124 raw rows -> 120 after dedup) and `output/data_quality_report.md`
- `tests/validate_ingestion.py`: parses `ground_truth.md` and the agent's own report, checks the fat-finger trap is flagged as a data error, that none of the 4 real business anomalies (11 anomaly-months total) are misclassified as errors, and that the cleaned CSV is structurally clean. **All checks pass.**

**Judgment calls on the imputation/outlier strategy:**
- Used actual/budget *ratio* (not raw value) for outlier detection, grouped by BU and column, because budget already bakes in this dataset's seasonality and growth trend — comparing raw actuals across months would confuse normal seasonal swings with real anomalies.
- Set the "likely data entry error" cutoff at >4x or <0.25x of budget. This was chosen knowing (as the dataset's author) that the largest genuine anomaly is a 2.8x swing and the trap is 10x — the cutoff sits in the wide gap between them. The agent's code itself contains no reference to specific rows or ground truth, only this general threshold, so the reasoning transfers to unseen data with a similar profile.
- The IQR-based "notable variance" tier only surfaced 5 of 11 anomaly-months (misses the FX dip and 5 of the 6 Marketing-savings months) because a sustained multi-month anomaly partly contaminates its own BU/column's "historical" baseline once ~20% of the series shifts. Accepted as a known limitation since this tier is purely informational — the two hard requirements (catch the trap, never mislabel a real anomaly as an error) both hold exactly.
- Missing Opex values imputed via per-BU linear time interpolation rather than a global mean/zero-fill, since Opex categories move smoothly month-to-month within a BU — this is a much closer estimate of what the real number likely was.

**Next step (Phase 4, Fable 5):** Variance & Root-Cause Agent. Should consume `data/eventco_monthly_cleaned.csv` (never the raw file). The ingestion agent's `output/data_quality_report.md` section 7 ("notable variances") is a useful starting shortlist of where to look, but the Variance Agent should compute its own variance table from the cleaned actuals/budgets rather than depending on the ingestion agent's flags — it needs to independently explain all 4 real anomalies (including the FX dip and the later Marketing-savings months that the ingestion agent's IQR tier didn't happen to flag), plus produce the one favorable variance narrative so the executive report isn't one-sided.

## 2026-07-06 — Fable 5 — Phase 4: Variance & Root-Cause Agent

**Done:**
- `data/business_notes.csv`: a new supporting data source — 21 dated, BU-tagged internal business notes (project updates, close commentary, IT incidents, programme announcements). Rationale: numbers can only say WHERE and HOW MUCH a variance occurred; the WHY has to come from documented business context, the way a real analyst cross-references project notes before writing commentary. 6 notes genuinely correlate with the 4 planted anomalies; 15 are realistic noise (hiring, awards, budget-process updates, tool migrations) so evidence matching isn't trivial. Documented in `data/ground_truth.md` section 3 (appended blind via shell — never displayed the file's contents in-session).
- `agents/variance_agent.py`, built without ever reading `data/ground_truth.md`: computes EUR and % variance for all 840 BU/line/month combinations, applies materiality, groups sustained drifts into episodes, and explains material items ONLY by citing corroborating notes (same BU or group-wide, tight date window, line-item keyword lexicon). When nothing corroborates, it prints "no clear driver identified" and recommends follow-up instead of inventing a cause. Rows breaching the ingestion agent's >4x/<0.25x rule are excluded up front as suspected data errors, so the fat-finger trap can't be dressed up as a business story.
- Outputs: `output/variance_report.md` (20 material items, 4 grounded in evidence, 16 honest "no clear driver" rows, 1 excluded data error) and `output/variance_table.csv` (full grain).
- `tests/validate_variance.py` (same pattern as Phase 3): parses ground_truth.md after the fact and checks all 11 anomaly-months flagged, every anomaly explained via its own signal notes, no false attributions, no noise note cited, favorable variance marked F, unexplained material rows honestly labeled, trap kept out of the narrative. **All 7 checks pass.**

**Judgment calls (and the two iterations it took):**
- *Materiality is three rules, not one.* (1) Monthly dual threshold: ≥10% of budget AND ≥ EUR20k — the % leg is a planning tolerance, the EUR floor (~0.25% of monthly group revenue) keeps small-line percentage noise out. (2) Monthly absolute trigger: ≥ EUR150k AND ≥7% — added after validation caught the planted FX miss coming in at -9.3%/-EUR197k, under the 10% leg. A EUR150k+ revenue miss (~2% of monthly group revenue) warrants comment regardless of the 10% rule; the 7% floor sits just above the business's routine ±6% revenue noise band. First attempt used EUR100k/5% and flooded the report with 25 rows of routine wobble — right instinct, wrong calibration, and the row count (not the validator) is what showed it.
- *Episodes bridge one quiet month.* The Marketing savings run has one month (2025-12, -3.8%) where noise almost fully masks the underspend; a strict "consecutive months ≥8%" rule split the episode and missed that anomaly-month. Rule now: a single below-threshold month is kept if the drift resumes in the same direction immediately after — a savings programme doesn't switch off for one noisy month. Direction flip or two quiet months still end the episode. Detected span is 2025-04..2026-02, wider than the planted 6 months, because adjacent noise months lean the same direction — acceptable: coverage of true months is what matters, and cumulative materiality still holds.
- *Evidence windows are tight on purpose:* 10 days lookback, 20 days lookahead around the variance period. The first run (45-day lookback) let the January FX note get cited for an unrelated March COGS overspend — a textbook false attribution. Tight windows plus per-line keyword lexicons (a note only corroborates a COGS variance if it actually talks about that kind of spend) got citations to exactly the right 4 stories with zero false positives.
- *The notes themselves needed one correction:* initial placement was inferred from the cleaned data alone, and I put the FX note on Digital's 2025-01 revenue dip — which turned out to be pure noise that is LARGER than the planted 2025-09 FX anomaly. Validation exposed the mislabel; the note was re-dated to the real event and the January dip now correctly reads "no clear driver identified". Good accidental stress test: the report visibly declines to explain a big tempting variance it has no evidence for.
- 16 of 20 material rows are honest "no clear driver" flags. That ratio is realistic for a monthly pack (most wobble has no documented single cause) and it's the behavioral core of this agent: material-but-unexplained is a follow-up item, not a story to invent.

**Next step (Phase 5): Forecast Agent.** Consume `data/eventco_monthly_cleaned.csv` (+ `output/variance_table.csv` if useful) and produce a rolling forecast for 2026-07..2026-09 (N+1 to N+3; data ends 2026-06). Two things it must handle: (1) the fat-finger trap is STILL uncorrected in the cleaned CSV (ingestion flags but deliberately doesn't auto-correct) — the forecast must exclude or correct Production revenue 2025-11 before fitting trends, or the year-over-year baseline is garbage; (2) known one-offs from the variance report (Falcon overrun, IT spike) shouldn't be extrapolated forward, while the Marketing savings programme arguably SHOULD persist per note N12/N16 — that's the judgment-demonstrating detail for this phase.

## 2026-07-06 — Fable 5 — Phase 5: Forecast Agent

**Done:**
- Extended `agents/variance_agent.py` to write two extra columns into `output/variance_table.csv` — `materiality` ("", "single", "episode") and `evidence_notes` — so downstream agents can consume the variance analysis instead of re-deriving it. This makes the pipeline chaining real: Ingestion → Variance → Forecast, each reading the previous agent's artifact. Re-ran `tests/validate_variance.py`: still green.
- `agents/forecast_agent.py` (never reads ground_truth.md): rolling forecast 2026-07..09 for all 28 BU/line series, method = seasonal base (same month last year, from a NORMALIZED history) × robust growth (median YoY ratio over the last 12 closed months). Outputs `output/forecast.csv` (with base/growth audit columns) and `output/forecast_report.md` (method, full history-adjustment audit trail, forecast tables, group P&L summary: 3-mo revenue EUR22.6M, +5.5%ish vs PY, seasonal August dip preserved).
- `tests/validate_forecast.py` (same post-hoc pattern): trap normalized with a data-error reason, both ground-truth one-offs normalized, all 9 episode months carry an explicit evidence-cited decision, no raw anomaly month used as a forecast base, FX dip not re-forecast, concluded savings programme not extrapolated, structural sanity (84 rows, growth 0.89–1.10x). **All 8 checks pass, first run.** Full suite (ingestion + variance + forecast validators) green.

**Judgment calls:**
- *Normalization is where the forecasting judgment lives.* Three rules, applied to the history before anything is fitted: (1) suspected data errors (the >4x/<0.25x rule — the trap is STILL uncorrected in the cleaned file) are replaced with budget × the line's typical achievement ratio; (2) one-off material months — explained (FX, IT incident) or unexplained outliers alike — are replaced the same way, because one-offs by definition don't recur and a seasonal base would otherwise re-forecast last year's accident; (3) sustained episodes are kept ONLY if still running within 2 months of the cutoff, else normalized out. Every decision lands in the report's audit trail with the variance agent's evidence notes attached (e.g. the Falcon months show N11/N13, the savings months N12/N16), so a reviewer sees WHY history was adjusted.
- *The handoff's "arguably persist the savings programme" question resolved AGAINST persisting — driven by data, not the notes.* N12/N16 promised savings "through year-end" (2025), and the 2026 actuals show marketing spend back around plan (episode detected as ended 2026-02; budgets presumably rebased). The episode-active rule therefore normalizes the deep-savings months out of the base, and the forecast returns Marketing opex to ~EUR40k/month instead of extrapolating the -40% July-2025 base month. The rule is generalizable: had the episode still been running at cutoff, its months would be KEPT and the effect carried forward — the report says so explicitly.
- *Method choice: seasonal-naive × median-YoY over anything fancier.* Budgets for 2026-07..09 don't exist in the dataset, so budget-ratio methods were out; the events business is strongly seasonal, so same-month-last-year is the right base; and a median over 12 YoY pairs is robust to the residual distortions that normalization didn't catch. Explainable to a finance audience in two sentences, which is the portfolio point.
- The growth window (trailing 12 months) naturally keeps the Falcon overrun and IT spike out of the numerators — but both still sit in DENOMINATORS of YoY pairs, and the trap sits inside the window itself, which is why normalization has to cover the whole history, not just the base months.

**Next step (Phase 6): Narrative Agent** — board-deck-style executive commentary from `output/variance_report.md` + `output/forecast_report.md` (variance story incl. the favorable one, forecast outlook, explicit "unexplained items for follow-up" list). This is the first agent whose output is prose, so decide whether it's template-driven Python (consistent with the pipeline so far) or the place to showcase an LLM call. After that: QA/Reviewer Agent + orchestrator, then the recruiter-facing README/diagram/demo.
