# Local pipeline validation

No report distribution is performed. --live-agents sends synthetic company context and selected evidence to Claude. --ai optionally sends statement ordering externally.

## Source ingestion

Exit status: 0

```
Raw rows: 124 -> cleaned rows: 120
BU typos corrected: 7
Duplicates removed: 4
Missing source values preserved: 9
Currency-formatted cells parsed: 10
Suspected anomalies requiring verification: 1
Flagged as notable variances (informational): 29
Wrote data/eventco_monthly_cleaned.csv and output/data_quality_report.md


```

## Provisional variance analysis

Exit status: 0

```
Variance rows computed: 1320
Excluded as suspected data errors: 1
Material items: 19 (2 episodes, 17 single months)
  corroborated by business notes: 4
  explained by analyst input (manual, labeled): 13
  still open, no clear driver identified: 2
Wrote output/variance_table.csv and output/variance_report.md


```

## Recurrence-reviewed forecast

Exit status: 0

```
Forecast: 132 rows; 32 recurrence decisions; 528 holdout predictions


```

## Business-line reports

Exit status: 0

```
Brand Events: net -1,965k vs budget, 5 material item(s) -> output/bu_reports/brand_events.md + .pdf
Corporate Events: net -148k vs budget, 3 material item(s) -> output/bu_reports/corporate_events.md + .pdf
Digital/Influence: net -317k vs budget, 5 material item(s) -> output/bu_reports/digital_influence.md + .pdf
Government & Institutions: net +1.9k vs budget, 6 material item(s) -> output/bu_reports/government_institutions.md + .pdf
Wrote 4 BU one-pagers to output/bu_reports/


```

## Bound commentary

Exit status: 0

```
Commentary: 28 bound statements; local deterministic rendering


```

## Recorded Claude agent review

Exit status: 0

```
Agent review: 5 recorded decisions; tool evidence and scoped facts verified; approval pending


```

## Charts

Exit status: 0

```
Wrote docs/variance_bridge_2025.png (budget 4,795,476 -> actual 2,366,738, reconciled)
Variance rankings: FY2025 view and full-history appendix (19 items)
Wrote docs/forecast_outlook.png (net EUR0.7M, margin 10.9%)
Wrote docs/og.png (1200x630, FY2025 gap -2,428,739)


```

## Canonical figures and source bridge

Exit status: 0

```
Canonical figures and source-to-provisional bridge regenerated


```

## Ingestion validation

Exit status: 0

```
=== Ingestion Agent Validation ===

Ground truth: 11 business anomalies + 1 data entry trap
Report: 1 flagged for source verification, 29 flagged as notable variances

  PASS - Fat-finger trap correctly flagged for source verification: ('Brand Events', '2025-11', 'revenue_actual')
  PASS - None of the 11 real business anomalies were misclassified as data errors
  PASS - 5/11 real anomalies also surfaced as informational 'notable variance' flags (bonus signal, not required): [('Brand Events', '2025-04', 'cogs_actual'), ('Brand Events', '2025-05', 'cogs_actual'), ('Brand Events', '2025-06', 'cogs_actual'), ('Government & Institutions', '2024-11', 'opex_it_actual'), ('Corporate Events', '2025-07', 'opex_marketing_actual')]
  PASS - Cleaned CSV passes all structural checks (BU names, dedup, dates, numeric, source gaps preserved)

RESULT: all checks passed.


```

## Variance validation

Exit status: 0

```
=== Variance Agent Validation ===

Ground truth: 11 anomaly months across 4 anomalies; 15 noise notes
Report: 19 material rows, 1 excluded data error(s)

  PASS - All 11 real anomaly months flagged as material on the right line item
  PASS - Every real anomaly is explained with a citation of its own signal note(s)
  PASS - No false attributions: every citation belongs to the citing row's own real anomaly
  PASS - None of the 15 noise notes is cited anywhere
  PASS - All 15 material rows without evidence are honest: 13 carry clearly-labeled analyst input, 2 say 'no clear driver identified'
  PASS - Favorable variance(s) covered and marked F: Corporate Events/Opex - Marketing
  PASS - Fat-finger trap (Brand Events revenue 2025-11) correctly excluded as a data error, not narrated

RESULT: all checks passed.


```

## Forecast validation

Exit status: 0

```
PASS: 132 forecasts independently reconciled; unresolved effects retained; 32 decisions; 528 holdout predictions


```

## Driver validation

Exit status: 0

```
  PASS - regenerating drivers in memory reproduces the committed CSV exactly
  PASS - 120 rows expected, found 120
  PASS - coverage is 4 BUs x 30 months
  PASS - no duplicate BU/month rows
  PASS - no missing driver values
  PASS - budget FTE sums to the 150-head business-line plan every month (found 150..150)
  PASS - true world joins cleaned CSV on all 120 rows (found 120)
  PASS - replayed true payroll matches cleaned payroll on every row, to the whole euro (max diff EUR0.3195)
  PASS - replayed true revenue matches cleaned revenue on all non-trap rows (max diff EUR0.0050)
  PASS - trap row: cleaned revenue is exactly 10x the true revenue (ratio 10.000000)
  PASS - payroll bridge (FTE volume + rate) reconciles exactly on all 120 rows (max gap EUR4.73e-11)
  PASS - revenue bridge (volume + price/mix) reconciles exactly on all 120 rows (max gap EUR5.82e-10)
  PASS - FX month Digital/Influence 2025-09: projects at budget (12 = 12), the whole miss is price
  PASS - trap month: corrupted export implies EUR3,073,152/project vs EUR300,000 budgeted (10.2x, above the 4x data-error rule) - ops data corroborates the error
  PASS - FTE actuals stay within 2 heads of plan (max deviation 1)

RESULT: all checks passed.


```

## Report validation

Exit status: 0

```
  PASS - 4 BUs found in the variance table (found 4)
  PASS - Brand Events: .md, .pdf and _bridge.png all exist
  PASS - Brand Events: PDF is a real, non-trivial PDF (47,535 bytes)
  PASS - Brand Events: FY2025 revenue figure EUR47,447,991 appears on the page
  PASS - Brand Events: FY2025 gross margin figure EUR7,046,599 appears on the page
  PASS - Brand Events: FY2025 net figure -EUR391,140 appears on the page
  PASS - Brand Events: net variance -1,965k appears on the page
  PASS - Brand Events: payroll split reconciles exactly before rounding
  PASS - Brand Events: revenue split reconciles exactly before rounding
  PASS - Brand Events: payroll headcount effect -26k appears on the page
  PASS - Brand Events: payroll rate effect -4.5k appears on the page
  PASS - Brand Events: revenue volume effect +1,494k appears on the page
  PASS - Brand Events: revenue price/mix effect -1,748k appears on the page
  PASS - Brand Events: all 5 material item(s) appear on the page
  PASS - Brand Events: all 4 analyst-explained item(s) are labeled '(analyst input, manual)'
  PASS - Brand Events: no em dashes on the page
  PASS - Brand Events: no buzzwords on the page
  PASS - Corporate Events: .md, .pdf and _bridge.png all exist
  PASS - Corporate Events: PDF is a real, non-trivial PDF (46,599 bytes)
  PASS - Corporate Events: FY2025 revenue figure EUR21,317,881 appears on the page
  PASS - Corporate Events: FY2025 gross margin figure EUR5,303,857 appears on the page
  PASS - Corporate Events: FY2025 net figure EUR711,413 appears on the page
  PASS - Corporate Events: net variance -148k appears on the page
  PASS - Corporate Events: payroll split reconciles exactly before rounding
  PASS - Corporate Events: revenue split reconciles exactly before rounding
  PASS - Corporate Events: payroll headcount effect 0k appears on the page
  PASS - Corporate Events: payroll rate effect +4.4k appears on the page
  PASS - Corporate Events: revenue volume effect -202k appears on the page
  PASS - Corporate Events: revenue price/mix effect +319k appears on the page
  PASS - Corporate Events: all 3 material item(s) appear on the page
  PASS - Corporate Events: all 2 analyst-explained item(s) are labeled '(analyst input, manual)'
  PASS - Corporate Events: no em dashes on the page
  PASS - Corporate Events: no buzzwords on the page
  PASS - Digital/Influence: .md, .pdf and _bridge.png all exist
  PASS - Digital/Influence: PDF is a real, non-trivial PDF (46,373 bytes)
  PASS - Digital/Influence: FY2025 revenue figure EUR25,872,171 appears on the page
  PASS - Digital/Influence: FY2025 gross margin figure EUR8,171,376 appears on the page
  PASS - Digital/Influence: FY2025 net figure EUR1,458,341 appears on the page
  PASS - Digital/Influence: net variance -317k appears on the page
  PASS - Digital/Influence: payroll split reconciles exactly before rounding
  PASS - Digital/Influence: revenue split reconciles exactly before rounding
  PASS - Digital/Influence: payroll headcount effect -17k appears on the page
  PASS - Digital/Influence: payroll rate effect +17k appears on the page
  PASS - Digital/Influence: revenue volume effect +355k appears on the page
  PASS - Digital/Influence: revenue price/mix effect -984k appears on the page
  PASS - Digital/Influence: all 5 material item(s) appear on the page
  PASS - Digital/Influence: all 3 analyst-explained item(s) are labeled '(analyst input, manual)'
  PASS - Digital/Influence: 'No clear driver identified' appears for each of the 1 still-open item(s)
  PASS - Digital/Influence: no em dashes on the page
  PASS - Digital/Influence: no buzzwords on the page
  PASS - Government & Institutions: .md, .pdf and _bridge.png all exist
  PASS - Government & Institutions: PDF is a real, non-trivial PDF (47,902 bytes)
  PASS - Government & Institutions: FY2025 revenue figure EUR10,508,792 appears on the page
  PASS - Government & Institutions: FY2025 gross margin figure EUR3,173,554 appears on the page
  PASS - Government & Institutions: FY2025 net figure EUR588,123 appears on the page
  PASS - Government & Institutions: net variance +1.9k appears on the page
  PASS - Government & Institutions: payroll split reconciles exactly before rounding
  PASS - Government & Institutions: revenue split reconciles exactly before rounding
  PASS - Government & Institutions: payroll headcount effect 0k appears on the page
  PASS - Government & Institutions: payroll rate effect -7.4k appears on the page
  PASS - Government & Institutions: revenue volume effect -149k appears on the page
  PASS - Government & Institutions: revenue price/mix effect +57k appears on the page
  PASS - Government & Institutions: all 6 material item(s) appear on the page
  PASS - Government & Institutions: all 4 analyst-explained item(s) are labeled '(analyst input, manual)'
  PASS - Government & Institutions: 'No clear driver identified' appears for each of the 1 still-open item(s)
  PASS - Government & Institutions: no em dashes on the page
  PASS - Government & Institutions: no buzzwords on the page
  PASS - Brand Events: the trap month never appears as a material variance row
  PASS - Brand Events: the page discloses the Nov-2025 data note
  PASS - Brand Events: the ops-system corroboration (normal project count) is shown

RESULT: all checks passed.


```

## Commentary validation

Exit status: 0

```
PASS: Statement ledger matches recomputed facts keyed by BU, period, metric, signed amount, direction and evidence
PASS: Every statement matches its bound template; changed attribution, period, sign, omitted losses and added reassurance fail this check
PASS: Structured unresolved items and their count are all present
PASS: Provisional basis, annual shortfall, Brand Events result and outlook risk are present


```

## Adversarial and gate regression tests

Exit status: 0

```

..............
----------------------------------------------------------------------
Ran 14 tests in 9.414s

OK

```

## Agent scope and replay checks

Exit status: 0

```

...........
----------------------------------------------------------------------
Ran 11 tests in 2.607s

OK

```

## Agent API spend and response checks

Exit status: 0

```

...
----------------------------------------------------------------------
Ran 3 tests in 12.530s

OK

```

## QA gate

Exit status: 0

```
QA checks: 8 passed, 0 failed, 0 skipped
Wrote output/qa_report.md


```
