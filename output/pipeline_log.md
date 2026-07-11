# Pipeline Run Log

Run at 2026-07-11 13:02 by `orchestrator.py`.

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
Back-Office: net -71k vs budget, 2 material item(s) -> output/bu_reports/back_office.md + .pdf
Digital: net -480k vs budget, 7 material item(s) -> output/bu_reports/digital.md + .pdf
Marketing: net -82k vs budget, 6 material item(s) -> output/bu_reports/marketing.md + .pdf
Production: net -2,482k vs budget, 5 material item(s) -> output/bu_reports/production.md + .pdf
Wrote 4 BU one-pagers to output/bu_reports/
```

### Narrative (LLM)

```
(no output)
```

stderr:
```
Traceback (most recent call last):
  File "C:\Users\snip1\Documents\GitHub\fpa-project\agents\narrative_agent.py", line 182, in <module>
    main()
  File "C:\Users\snip1\Documents\GitHub\fpa-project\agents\narrative_agent.py", line 136, in main
    response = client.messages.create(
               ^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\snip1\Documents\GitHub\fpa-project\.venv\Lib\site-packages\anthropic\_utils\_utils.py", line 294, in wrapper
    return func(*args, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\snip1\Documents\GitHub\fpa-project\.venv\Lib\site-packages\anthropic\resources\messages\messages.py", line 1050, in create
    return self._post(
           ^^^^^^^^^^^
  File "C:\Users\snip1\Documents\GitHub\fpa-project\.venv\Lib\site-packages\anthropic\_base_client.py", line 1536, in post
    return cast(ResponseT, self.request(cast_to, opts, stream=stream, stream_cls=stream_cls))
                           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\snip1\Documents\GitHub\fpa-project\.venv\Lib\site-packages\anthropic\_base_client.py", line 1137, in request
    response, prepared = self._attempt_request(
                         ^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\snip1\Documents\GitHub\fpa-project\.venv\Lib\site-packages\anthropic\_base_client.py", line 1295, in _attempt_request
    response = self._client.send(
               ^^^^^^^^^^^^^^^^^^
  File "C:\Users\snip1\Documents\GitHub\fpa-project\.venv\Lib\site-packages\httpx\_client.py", line 914, in send
    response = self._send_handling_auth(
               ^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\snip1\Documents\GitHub\fpa-project\.venv\Lib\site-packages\httpx\_client.py", line 939, in _send_handling_auth
    request = next(auth_flow)
              ^^^^^^^^^^^^^^^
  File "C:\Users\snip1\Documents\GitHub\fpa-project\.venv\Lib\site-packages\anthropic\lib\credentials\_auth.py", line 109, in sync_auth_flow
    token = self._token_cache.get_token()
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\snip1\Documents\GitHub\fpa-project\.venv\Lib\site-packages\anthropic\lib\credentials\_cache.py", line 151, in get_token
    fresh = self._call_provider()
            ^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\snip1\Documents\GitHub\fpa-project\.venv\Lib\site-packages\anthropic\lib\credentials\_cache.py", line 95, in _call_provider
    result = self._invoke_provider(force=force)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\snip1\Documents\GitHub\fpa-project\.venv\Lib\site-packages\anthropic\lib\credentials\_cache.py", line 79, in _invoke_provider
    return self._provider(force_refresh=force)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\snip1\Documents\GitHub\fpa-project\.venv\Lib\site-packages\anthropic\lib\credentials\_providers.py", line 458, in __call__
    return self._call_user_oauth(auth, force_refresh=force_refresh)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\snip1\Documents\GitHub\fpa-project\.venv\Lib\site-packages\anthropic\lib\credentials\_providers.py", line 527, in _call_user_oauth
    _raise_token_endpoint_error(resp, message_prefix="user_oauth refresh failed")
  File "C:\Users\snip1\Documents\GitHub\fpa-project\.venv\Lib\site-packages\anthropic\lib\credentials\_workload.py", line 85, in _raise_token_endpoint_error
    raise WorkloadIdentityError(
anthropic.lib.credentials._workload.WorkloadIdentityError: user_oauth refresh failed (HTTP 400): {'error': 'invalid_grant', 'error_description': 'Refresh token not found or invalid'} [request_id=req_011CcvdYxkZYQe69asJyMS2q]
```

### QA/Reviewer

```
QA checks: 8 passed, 0 failed, 0 skipped
Wrote output/qa_report.md
```

