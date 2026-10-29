# FP&A reporting automation

I built this synthetic case study to demonstrate how I automate recurring FP&A reporting. It produces variance analysis, business-line reviews and a three-month forecast, with source checks and analyst review.

EventCo is a fictional events agency with four business lines. The reporting cycle draws on my experience as Head of FP&A at a EUR100M events agency. All amounts, events, notes and analyst explanations in this repository are synthetic.

The reporting date is 30 June 2026. The management assessment covers FY2025, the forecast covers Q3 2026, and the historical appendix covers January 2024-June 2026.

## Read the reports

Start with the [Brand Events business review](output/bu_reports/brand_events.pdf), then the [executive assessment](output/executive_summary.md). The [draft management pack](output/board_pack.md) includes variance analysis, the forecast and validation results. The [public case study](https://alanvourch.com/fpa-project/) will reflect these changes after publication; the local build is under `showcase/_site/`.

![FY2025 provisional operating result, with a zero baseline](docs/variance_bridge_2025.png)

FY2025 provisional operating result is approximately EUR2.4M against a EUR4.8M budget comparator. Brand Events posts a provisional annual operating loss. A project cost overrun and FX loss account for major adverse items; below-threshold margin shortfalls also accumulate. These results require a management response.

The figures include unapproved estimates for missing source cells and a budget placeholder for November 2025 Brand Events billings. They are an optional demonstration scenario, not confirmed accounting actuals or an approved reconstructed budget. Source verification remains open.

## Financial definitions and source handling

Net billings are invoiced amounts. Cost of sales covers client-project purchases and external production crews. Gross margin is billings less cost of sales. Operating result is gross margin less staff costs and overheads. This simplified management P&L does not implement accounting revenue recognition, ARR or ACV restatement, a full accounting close, or SAP/BPC integration.

`data/eventco_monthly_cleaned.csv` preserves all nine source gaps. It corrects formatting and names and removes identical duplicates. Conflicting duplicates stop the run. A ratio above 4x or below 0.25x budget triggers source review; it does not establish that the observation is wrong or justify discarding it.

Without `--provisional`, source gaps stop downstream reporting. The optional scenario uses previous observed values within the same series. An opening actual with no earlier observation uses a same-month budget placeholder. It never uses a later month to estimate an earlier one. Estimates and the cell-specific November billings assumption are logged in `output/reporting_adjustments.csv`.

The variance CSV keeps `actual` and `budget` as source columns, beside separate `provisional_actual` and `provisional_budget` columns. Variance amounts and flags use the provisional columns and carry a reporting-basis label. Approved corrections should be supplied at source, with the obsolete placeholder removed from `data/reporting_policy.json` after review.

## Forecast and recurrence review

The forecast uses the same month in the prior year times median year-over-year growth over the last 12 observed months, by business unit and line. Materiality does not establish recurrence. Single-month and multi-month effects remain in history unless a confirmed one-off has explicit approval, evidence and a replacement value in `data/forecast_reviews.csv`.

The review file accepts `confirmed one-off`, `continuing structural effect`, `timing shift` or `unresolved`, with `proposed` or `approved` status. Approved one-offs require reviewer, review date, evidence and a non-negative replacement. Reviews dated after a historical cutoff cannot affect that fold. Timing and structural effects are retained until a separate future schedule is specified. No recurrence approvals are supplied for this case study.

The report shows the raw source baseline, the selected provisional baseline and an unapproved diagnostic that neutralizes every material month. The diagnostic is a sensitivity, not a confidence interval or an approved forecast. On this dataset, the raw and selected forecasts coincide despite the November placeholder because the median growth factor and seasonal bases are unaffected by that single observation.

Four overlapping three-month holdouts compare seasonal growth with seasonal naive forecasts. Training uses only observations and reviews available at each cutoff; missing or flagged source targets are excluded. The current growth method has higher mean absolute error than seasonal naive on this short synthetic sample. That finding calls for further model review and does not establish performance on employer data.

Corporate Events' detected marketing run spans April 2025-February 2026, while the notes support in-housing only from July through December 2025. Only that documented period receives the cause attribution. Earlier and later months remain a timing/cause follow-up.

## Commentary and validation

The default executive summary is rendered locally from a statement catalogue. Each fact binds business unit, period, metric, signed amount, direction and evidence. Validation recomputes that catalogue from the current outputs and checks both the claim ledger and the exact rendered statements. Required losses, the annual shortfall, source uncertainty and unresolved items must be included.

This is constrained commentary. Arbitrary new prose fails closed; the validator does not claim to understand every possible financial assertion. A wording change requires an explicit template change and review. The regression suite tests wrong business units, wrong periods, wrong signs, omitted losses, invented amounts and unsupported reassurance, alongside source preservation, recurrence approval and forecast leakage.

The orchestrator returns a failing exit status when any required step fails, writes a failed-review notice, and invalidates `output/release_status.json`. A site build requires passing validation for the exact current source and artifacts. It does not constitute approval for report distribution. A human still reviews the draft and authorizes publication.

## Run locally

Use Python 3.12 and the pinned packages in `requirements.txt`. Run from the repository root.

```powershell
python -m venv .venv
.venv\Scripts\pip.exe install -r requirements.txt
.venv\Scripts\python.exe orchestrator.py --provisional
.venv\Scripts\python.exe showcase/build_site.py
.venv\Scripts\python.exe -m http.server 8765 --bind 127.0.0.1 --directory showcase/_site
```

On macOS/Linux, use `.venv/bin/python` and `.venv/bin/pip` for the equivalent commands. Open the local server in a browser. Building does not publish. The repository's existing `gh-pages` workflow remains a separate release action.

The pipeline runs ingestion, variance analysis, forecast, four business-line PDFs, commentary, charts, six validation scripts, adversarial regression tests and the QA gate. `output/pipeline_log.md` records their results. Calculations are reproducible for fixed inputs. The default commentary is deterministic; optional AI ordering is not guaranteed to be identical on fresh calls.

## Optional AI and data handling

The default run makes no AI call. `orchestrator.py --provisional --ai` opts in to sending the structured statement catalogue to the configured Anthropic-compatible provider for ordering only. It cannot add or rewrite statements. A provider error or an invalid response fails the run; an older summary is never used as a fallback.

Provider credentials are environment configuration; no secret is committed. `FPA_NARRATIVE_MODEL` can select the configured model. This optional path has not been exercised as part of the local repair verification.

Business notes and catalogues can contain identifying client names and context. Aggregation does not anonymize them. Live employer data requires an approved provider and confidentiality policy. Source scans check specified provider references and prohibited filenames in literal `open()` calls; they do not establish runtime network isolation or comprehensive data-loss prevention.

No step distributes reports. The optional AI request is separate from report distribution.

## Limits

- The synthetic dataset and operational drivers are consistent by construction. A real HR/CRM reconciliation needs tolerances and an explicit unallocated difference.
- The 13 analyst explanations are illustrative text over seeded noise, not investigative findings. A dated business note is evidence of context, not independent proof of every cause or amount.
- The two unexplained material items remain open. The partial marketing attribution and source uncertainty remain additional review actions.
- Support staff and overheads are allocated to the four business lines. A real management pack should also show central cost centres before allocation.
- There is no measured before/after productivity benefit, real-client deployment or production confidentiality control demonstrated here.

See [canonical figures](FIGURES.md) and the [audit repair record](docs/audit-repairs.md).
