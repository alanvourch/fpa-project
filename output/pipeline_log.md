# Pipeline Run Log

Run at 2026-07-06 15:59 by `orchestrator.py`.

| Step | Script | Exit code | Result |
|---|---|---|---|
| Data Ingestion | `agents/ingestion_agent.py` | 0 | OK |
| Variance & Root-Cause | `agents/variance_agent.py` | 0 | OK |
| Rolling Forecast | `agents/forecast_agent.py` | 0 | OK |
| Narrative (LLM) | `agents/narrative_agent.py` | 1 | FAILED |
| QA/Reviewer | `agents/qa_agent.py` | 0 | OK |

## Step output

### Data Ingestion

```
Raw rows: 124 -> cleaned rows: 120
BU typos corrected: 8
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
  with grounded evidence: 4
  no clear driver identified: 16
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

### Narrative (LLM)

```
(no output)
```

stderr:
```
No Anthropic credentials configured. Either set ANTHROPIC_API_KEY, or run `ant auth login` to authenticate via OAuth (uses your Claude subscription instead of a separate metered API key). See README.md for setup.
```

### QA/Reviewer

```
QA checks: 8 passed, 0 failed, 0 skipped
Wrote output/qa_report.md
```

