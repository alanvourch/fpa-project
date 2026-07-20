# Pipeline Run Log

Run at 2026-07-20 19:14 by `orchestrator.py`.

| Step | Script | Exit code | Result |
|---|---|---|---|
| Data Ingestion | `agents/ingestion_agent.py` | 0 | OK |
| Variance & Root-Cause | `agents/variance_agent.py` | 0 | OK |
| Rolling Forecast | `agents/forecast_agent.py` | 0 | OK |
| BU One-Pagers | `agents/bu_report_agent.py` | 0 | OK |
| Narrative (LLM) | `agents/narrative_agent.py` | 1 | FAILED |
| QA/Reviewer | `agents/qa_agent.py` | 0 | OK |

## Step output

### Data Ingestion

```
Raw rows: 124 -> cleaned rows: 120
BU typos corrected: 7
Duplicates removed: 4
Opex values imputed: 9
Currency-formatted cells parsed: 10
Flagged as likely data errors: 1
Flagged as notable variances (informational): 26
Wrote data/eventco_monthly_cleaned.csv and output/data_quality_report.md
```

### Variance & Root-Cause

```
Variance rows computed: 840
Excluded as suspected data errors: 1
Material items: 20 (3 episodes, 17 single months)
  corroborated by business notes: 4
  explained by analyst input (manual, labeled): 14
  still open, no clear driver identified: 2
Wrote output/variance_table.csv and output/variance_report.md
```

### Rolling Forecast

```
Forecast horizon: 2026-07, 2026-08, 2026-09 (cutoff 2026-06)
Forecast rows: 84 (28 series)
History adjustments: 34 normalized, 0 kept (active episodes)
Growth factors range: 0.89x .. 1.10x
Wrote output/forecast.csv and output/forecast_report.md
```

### BU One-Pagers

```
Brand Events: net -2,482k vs budget, 5 material item(s) -> output/bu_reports/brand_events.md + .pdf
Corporate Events: net -82k vs budget, 6 material item(s) -> output/bu_reports/corporate_events.md + .pdf
Digital/Influence: net -480k vs budget, 7 material item(s) -> output/bu_reports/digital_influence.md + .pdf
Government & Institutions: net -71k vs budget, 2 material item(s) -> output/bu_reports/government_institutions.md + .pdf
Wrote 4 BU one-pagers to output/bu_reports/
```

### Narrative (LLM)

```
(no output)
```

stderr:
```
No usable model credentials for this run, so the Narrative step is skipped rather than failing the pipeline (see README.md, 'Narrative Agent credentials'). Set ANTHROPIC_API_KEY, run `ant auth login`, or point this client at your organization's internal model gateway or another approved provider.
Underlying error: user_oauth refresh failed (HTTP 400): {'error': 'invalid_grant', 'error_description': 'Refresh token not found or invalid'} [request_id=req_011CdEA9s2ZBJAM1W9QrjXgR]
```

### QA/Reviewer

```
QA checks: 8 passed, 0 failed, 0 skipped
Wrote output/qa_report.md
```

