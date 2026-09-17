# Canonical figures

Every number quoted outside this repository (portfolio site, case study page, README,
link previews) comes from the list below. Each line gives the figure and the file it is
read from, so a later pass can recompute rather than copy. All amounts are EUR. The
dataset is synthetic and seeded; rerunning `orchestrator.py` and `make_charts.py`
reproduces every figure byte for byte apart from timestamps.

## FY2025 walk (group, budget to actual)

- FY2025 budgeted operating result: 4,776,802 (EUR4.8M). Source: `output/variance_table.csv`, 2025 rows, revenue budget minus all cost budgets; printed by `make_charts.py`.
- FY2025 actual operating result: 1,730,637 (EUR1.7M), with the Brand Events November 2025 revenue row held at budget pending correction. Source: same, printed by `make_charts.py`.
- FY2025 gap: -3,046,166 (EUR3.0M under budget). Source: `docs/og.png` headline, computed by `make_charts.py`.
- FY2025 budgeted revenue: 106,004,086; actual revenue with the held row: 105,146,835. Source: `output/variance_table.csv`.
- FY2025 margin: 1.6% actual against 4.5% budgeted. Source: the four figures above.
- Named driver, Brand Events external-production (COGS) overrun, April to June 2025: -2,132,923 (+22.4% on the period budget). Source: `output/variance_report.md`, first material row; evidence notes N11 and N13.
- Named driver, FX on a USD-invoiced contract, Digital/Influence revenue, September 2025: -196,953 (-9.3%). Source: `output/variance_report.md`; evidence note N08.
- Named driver, Corporate Events marketing in-housing savings, April 2025 to February 2026: +68,927 favorable in FY2025 (the full episode is -81,464, -16.4%, and spans into 2026). Source: `make_charts.py` for the FY2025 share; `output/variance_report.md` for the episode.
- Fourth documented item, Government & Institutions IT opex, November 2024: +24,116 (+158.1%); evidence note N06. Not in the FY2025 walk (it is a 2024 month). Source: `output/variance_report.md`.
- Items routed to the analyst inside FY2025: +333,356 net across 9 items (hatched block). Source: `make_charts.py`.
- Revenue below materiality, FY2025, net: -818,175. Source: `make_charts.py`.
- Costs below materiality, FY2025, net: -300,398. Source: `make_charts.py`.
- Brand Events FY2025 operating result: -1,411,587 actual against 1,133,155 budget (-2,545k); operating margin -3.0%. Source: `output/bu_reports/brand_events.md`.

## Material variances and provenance

- Variance tests run: 1,200 (120 cleaned rows times 10 P&L lines). Source: `output/pipeline_log.md`, variance step output.
- Material items: 27 (2 sustained episodes, 25 single months). Source: `output/variance_report.md`, material variances table; `output/pipeline_log.md`.
- Corroborated by a dated business note: 4. Analyst input (labeled): 20. Still open, no clear driver identified: 3. Source: `output/pipeline_log.md`, variance step output; `output/qa_report.md`.
- The three open items: Brand Events freelance March 2026 (-56,960, -12.9%, favorable); Corporate Events freelance December 2025 (+41,709, +19.2%); Brand Events allocated G&A June 2026 (-20,846, -11.0%, favorable). Source: `output/variance_report.md`.
- Materiality rules: monthly dual threshold 10% of budget and EUR20,000; monthly absolute trigger EUR150,000 and 7% of budget; sustained episodes of at least 2 consecutive months each at least 8% off budget with a cumulative gap of at least EUR40,000 and 10% of the period budget. Source: `agents/variance_agent.py` constants, restated in `output/variance_report.md`.

## The data-entry trap

- Recorded value: 52,243,584 (Brand Events revenue, November 2025). Budget that month: 5,238,445. True value: 5,224,358 (the recorded value is exactly 10x). Source: `data/ground_truth.md`; the recorded and budget figures also appear in `output/variance_report.md`, excluded rows table.
- Corroboration from operations data: 17 projects delivered against 17 planned that month; the recorded figure implies 3,073,152 per project against a 300,000 budgeted project value. Source: `data/ground_truth_drivers.md`, `output/bu_reports/brand_events.md`.
- Ingestion flagged 1 likely data error and 27 informational notable variances. Source: `output/pipeline_log.md`, ingestion step output.

## The dataset

- Fictional company: EventCo, events agency, about EUR100M annual revenue, 150 FTE (130 in the four business lines, 20 in central functions carried in the allocated G&A line). Source: `data/generate_dataset.py` (`BU_PARAMS`, module docstring).
- Base-year (2024) revenue on true actuals: 102,571,474. Source: `data/generate_dataset.py` console output.
- Base-year cost structure, share of revenue: external production 62.6%; freelance and project staff 11.3%; permanent payroll, fully loaded, 11.6%; travel 0.7%; marketing and new business 1.1%; IT 0.8%; facilities 2.0%; allocated central G&A 4.7%; depreciation 0.8%; operating result 4.5% (4,571,070). Source: `data/generate_dataset.py` console output.
- Business lines and annual revenue in the base year: Brand Events 45M, Corporate Events 20M, Digital/Influence 25M, Government & Institutions 10M. Source: `data/generate_dataset.py` (`BU_PARAMS`).
- Rows: 124 in the raw export (4 planted duplicates), 120 cleaned; 30 months, January 2024 to June 2026. Source: `output/pipeline_log.md`, ingestion step output.
- Planted data-quality issues: 7 business-line name typos, 4 duplicate rows, 9 missing overhead cells, 10 currency-formatted text amounts, 4 date formats, 1 fat-fingered revenue figure. Source: `data/ground_truth.md`.

## One-pagers (Brand Events example)

- Payroll variance -41k: headcount effect -37k (average 51.6 FTE against 52 planned), rate effect -4.0k. Source: `output/bu_reports/brand_events.md`.
- Revenue variance -254k (excluding the held month): volume effect +1,494k (146 projects delivered against 141 planned), price/mix effect -1,748k. Source: `output/bu_reports/brand_events.md`.

## Rolling forecast, Q3 2026 (July to September)

- Revenue 22,613,628 (EUR22.6M); total costs 22,343,471; operating result 270,158; margin 1.2%. Source: `output/forecast_report.md`, group P&L summary.
- By month: July +53,117; August -421,190 (operating loss); September +638,231. Source: `output/forecast_report.md`.
- Revenue growth against the same quarter last year: Government & Institutions +6.4%, Brand Events +6.1%, Corporate Events +5.1%, Digital/Influence +4.6%. Source: `output/forecast_report.md`, forecast by BU and line item.
- History adjustments: 40 month-values normalized out of the forecast base, 0 kept as active episodes. Source: `output/forecast_report.md`.

## Pipeline

- Six steps, one of which calls a language model (`claude-sonnet-5`); QA checks: 8 passed, 0 failed. Source: `output/qa_report.md`, `output/pipeline_log.md`.
- Narrative grounding tolerance: 0.5% relative and EUR15,000 absolute for money figures, 1.0 percentage point for percentages. Source: `agents/grounding_check.py`.
- Ingestion's informational outlier tier surfaced 5 of the 11 planted anomaly-months; the variance step found all 11. Source: `tests/validate_ingestion.py` and `tests/validate_variance.py` output.
