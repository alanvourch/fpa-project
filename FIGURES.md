# Canonical figures

Every number quoted outside this repository (portfolio site, case study page, README,
link previews) comes from the list below. Each line gives the figure and the file it is
read from, so a later pass can recompute rather than copy. All amounts are EUR. The
dataset is synthetic and seeded; rerunning `orchestrator.py` and `make_charts.py`
reproduces every figure apart from timestamps.

Terms: net billings are what clients are invoiced; cost of sales is what is bought for
client projects, freelance crews included; gross margin is net billings less cost of
sales, the agency's net revenue; operating result is gross margin less staff costs and
overheads.

## FY2025 walk (group, budget to actual)

- FY2025 budgeted operating result: 4,795,396 (EUR4.8M), 18.3% of gross margin, 4.5% of net billings. Source: `output/variance_table.csv`, 2025 rows; printed by `make_charts.py`.
- FY2025 actual operating result: 2,366,045 (EUR2.4M), 10.0% of gross margin, 2.3% of net billings, with the Brand Events November 2025 billings row held at budget pending correction. Source: same.
- FY2025 gap: -2,429,350 (EUR2.4M under budget). Source: `docs/og.png` headline, computed by `make_charts.py`.
- FY2025 net billings: budget 106,004,086; actual 105,146,835 with the held row. Source: `output/variance_table.csv`.
- FY2025 cost of sales: budget 79,768,075; actual 81,451,450. Source: same.
- FY2025 gross margin: budget 26,236,011 (24.7% of billings); actual 23,695,386 (22.5%). Source: same.
- FY2025 staff costs and overheads: budget 21,440,615; actual 21,329,340. Source: same.
- Named driver, Brand Events cost-of-sales overrun on the Falcon launch, April to June 2025: -1,639,708 (+14.2% on the period budget). Source: `output/variance_report.md`, first material row; evidence notes N11 and N13.
- Named driver, FX on a USD-invoiced contract, Digital/Influence net billings, September 2025: -196,953 (-9.3%). Source: `output/variance_report.md`; evidence note N08.
- Named driver, Corporate Events marketing in-housing savings: +68,927 favorable inside FY2025. The full episode, April 2025 to February 2026, is -81,464 (-16.4%). Source: `make_charts.py` for the FY2025 share; `output/variance_report.md` for the episode.
- Items routed to the analyst inside FY2025: +251,680 net across 5 items (hatched block). Source: `make_charts.py`.
- Gross margin below materiality, FY2025, net: -955,645 (3.6% of budgeted gross margin). Source: `make_charts.py`.
- Staff costs and overheads below materiality, FY2025, net: +42,348. Source: `make_charts.py`.
- Brand Events FY2025 operating result: -391,972 actual against 1,573,921 budget (-1,966k). Source: `output/bu_reports/brand_events.md`.
- FY2025 budgeted operating result by business line, % of gross margin: Brand Events 17.4%, Corporate Events 15.6%, Digital/Influence 20.9%, Government & Institutions 18.4%. Source: the four scorecards in `output/bu_reports/`.

## Material variances and provenance

- Variance tests run: 1,320 (120 cleaned rows times 11 P&L lines). Source: `output/pipeline_log.md`, variance step output.
- Material items: 19 (2 sustained episodes, 17 single months). Source: `output/variance_report.md`; `output/pipeline_log.md`.
- Corroborated by a dated business note: 4. Analyst input (labeled): 13. Still open, no clear driver identified: 2. Source: `output/pipeline_log.md`; `output/qa_report.md`.
- The two open items: Digital/Influence net billings August 2025 (+135,341, +10.2%, favorable); Government & Institutions cost of sales September 2025 (+68,616, +11.6%, unfavorable). Source: `output/variance_report.md`.
- Fourth documented item, outside the FY2025 walk: Government & Institutions IT, November 2024, +24,116 (+158.1%); evidence note N06. Source: `output/variance_report.md`.
- Materiality rules: monthly dual threshold 10% of budget and EUR20,000; monthly absolute trigger EUR150,000 and 7% of budget; sustained episodes of at least 2 consecutive months each at least 8% off budget, with a cumulative gap of at least EUR40,000 and 10% of the period budget. Source: `agents/variance_agent.py`, restated in `output/variance_report.md`.

## The data-entry trap

- Recorded value: 52,243,584 (Brand Events net billings, November 2025). Budget that month: 5,238,445. True value: 5,224,358; the recorded value is exactly 10x. Source: `data/ground_truth.md`; recorded and budget figures also in `output/variance_report.md`, excluded rows table.
- Operations data that month: 17 projects delivered against 17 planned; the recorded figure implies 3,073,152 per project against a 300,000 budgeted project value. Source: `data/ground_truth_drivers.md`; `output/bu_reports/brand_events.md`.
- Ingestion flagged 1 likely data error and 29 informational notable variances. Source: `output/pipeline_log.md`.

## The dataset

- Fictional company: EventCo, events agency, about EUR100M of annual net billings, 150 FTE across four business lines (support staff allocated to the lines). Source: `data/generate_dataset.py` (`BU_PARAMS`, module docstring).
- Business lines and base-year net billings plan: Brand Events 45M, Corporate Events 20M, Digital/Influence 25M, Government & Institutions 10M. Source: `data/generate_dataset.py`.
- Base-year (2024) P&L on true actuals: net billings 102,571,474; cost of sales 75.1% of billings; gross margin 25,494,106 (24.9% of billings). As % of gross margin: gross salaries 36.8%, employer social charges 16.9%, bonuses and profit sharing 6.6% (staff costs 60.2%); travel 0.9%, marketing and new business 3.7%, IT 5.0%, rent and facilities 5.8%, professional fees and G&A 4.7%, depreciation 1.4% (overheads 21.5%); operating result 4,612,078, 18.1% of gross margin and 4.5% of billings. Source: `data/generate_dataset.py` console output.
- Rows: 124 in the raw export (4 planted duplicates), 120 cleaned; 30 months, January 2024 to June 2026. Source: `output/pipeline_log.md`.
- Planted data-quality issues: 7 business-line name typos, 4 duplicate rows, 9 missing overhead cells, 10 currency-formatted text amounts, 4 date formats, 1 fat-fingered billings figure. Source: `data/ground_truth.md`.

## One-pagers (Brand Events example)

- Payroll (gross salaries) variance -30k: headcount effect -26k (average 54.6 FTE against 55 planned), rate effect -4.5k. Source: `output/bu_reports/brand_events.md`.
- Net billings variance -254k, excluding the held month: volume effect +1,494k (146 projects delivered against 141 planned), price/mix effect -1,748k. Source: `output/bu_reports/brand_events.md`.

## Rolling forecast, Q3 2026 (July to September)

- Net billings 22,613,628; cost of sales 16,928,330; gross margin 5,685,298; staff costs and overheads 5,437,458; operating result 247,841, 4.4% of gross margin and 1.1% of net billings. Source: `output/forecast_report.md`, group P&L summary.
- Operating result by month: July +18,483; August -392,041 (operating loss); September +621,399. Source: `output/forecast_report.md`.
- Net billings growth against the same quarter last year: Government & Institutions +6.4%, Brand Events +6.1%, Corporate Events +5.1%, Digital/Influence +4.6%. Source: `output/forecast_report.md`.
- History adjustments: 32 month-values normalized out of the forecast base, 0 kept as active episodes. Source: `output/forecast_report.md`.

## Pipeline

- Six steps, one of which calls a language model (`claude-sonnet-5`); QA checks: 8 passed, 0 failed. Source: `output/qa_report.md`; `output/pipeline_log.md`.
- The committed executive summary was generated by `claude-sonnet-5` via `agents/narrative_agent.py` and passed the grounding check (21 monetary figures, 8 percentages, all traced to source). Source: header of `output/executive_summary.md`; `output/qa_report.md`.
- Narrative grounding tolerance: 0.5% relative and EUR15,000 absolute for money figures, 1.0 percentage point for percentages. Source: `agents/grounding_check.py`.
- Ingestion's informational outlier tier surfaced 5 of the 11 planted anomaly-months; the variance step found all 11. Source: `tests/validate_ingestion.py` and `tests/validate_variance.py` output.
