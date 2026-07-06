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
