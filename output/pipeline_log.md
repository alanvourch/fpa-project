# Pipeline Run Log

Run at 2026-09-17 16:40 by `orchestrator.py`.

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
Flagged as notable variances (informational): 27
Wrote data/eventco_monthly_cleaned.csv and output/data_quality_report.md
```

### Variance & Root-Cause

```
Variance rows computed: 1200
Excluded as suspected data errors: 1
Material items: 27 (2 episodes, 25 single months)
  corroborated by business notes: 4
  explained by analyst input (manual, labeled): 20
  still open, no clear driver identified: 3
Wrote output/variance_table.csv and output/variance_report.md
```

### Rolling Forecast

```
Forecast horizon: 2026-07, 2026-08, 2026-09 (cutoff 2026-06)
Forecast rows: 120 (40 series)
History adjustments: 40 normalized, 0 kept (active episodes)
Growth factors range: 0.89x .. 1.06x
Wrote output/forecast.csv and output/forecast_report.md
```

### BU One-Pagers

```
Brand Events: net -2,545k vs budget, 8 material item(s) -> output/bu_reports/brand_events.md + .pdf
Corporate Events: net -197k vs budget, 4 material item(s) -> output/bu_reports/corporate_events.md + .pdf
Digital/Influence: net -297k vs budget, 8 material item(s) -> output/bu_reports/digital_influence.md + .pdf
Government & Institutions: net -7.1k vs budget, 7 material item(s) -> output/bu_reports/government_institutions.md + .pdf
Wrote 4 BU one-pagers to output/bu_reports/
```

### Narrative (LLM)

```
(no output)
```

stderr:
```
No usable model credentials for this run, so the Narrative step is skipped rather than failing the pipeline (see README.md, 'Narrative Agent credentials'). Set ANTHROPIC_API_KEY, run `ant auth login`, or point this client at your organization's internal model gateway or another approved provider.
Underlying error: credentials file for profile 'default' (authentication.type 'user_oauth' with client_id) must include 'refresh_token': C:\Users\snip1\AppData\Roaming\Anthropic\credentials\default.json
```

### QA/Reviewer

```
QA checks: 8 passed, 0 failed, 0 skipped
Wrote output/qa_report.md
```

