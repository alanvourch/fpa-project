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
