# Agent design choices

This project demonstrates a recurring FP&A review: check the numbers, investigate a business line and prepare a brief for the manager. Python owns the calculations. Claude chooses from a limited set of read-only checks and proposes questions. The analyst judges the evidence and approves the report.

## Comparison with Anthropic's finance templates

Reviewed on 29 October 2026:

| Reference | Useful for this project | Decision |
|---|---|---|
| [Month-end closer](https://github.com/anthropics/financial-services/blob/main/plugins/agent-plugins/month-end-closer/agents/month-end-closer.md) | Separate evidence gathering, variance commentary and controller sign-off. | Keep the review boundary. Accruals, journal drafts and GL connections are outside this dataset's scope. |
| [Variance commentary](https://github.com/anthropics/financial-services/blob/main/plugins/agent-plugins/month-end-closer/skills/variance-commentary/SKILL.md) | Link explanations to underlying activity and leave unclear drivers open. | Keep dated evidence and unresolved items visible. Arithmetic rate and mix residuals alone do not establish a cause. |
| [Spreadsheet audit](https://github.com/anthropics/financial-services/blob/main/plugins/vertical-plugins/financial-analysis/skills/audit-xls/SKILL.md) | Check units, signs, input separation and model consistency. | Keep explicit Python reconciliations and regression tests. This project does not demonstrate a Claude audit of Excel formulas. |
| [Deck refresh](https://github.com/anthropics/financial-services/blob/main/plugins/vertical-plugins/financial-analysis/skills/deck-refresh/SKILL.md) | Keep displayed values, charts and derived metrics consistent when figures change. | Render reports and charts from the same calculated outputs, then validate the build. An Office add-in is a possible later extension. |

These are reference comparisons. No Anthropic finance plugin, market-data connector or Office add-in is installed or integrated in this implementation. The prompts and Python tools in this repository are specific to EventCo's reporting exercise.

## Why a focused workflow

The case study needs to show that an analyst can direct an agent, inspect its work and decide what belongs in a management report. A company brief defines the financial terms, reporting period and approval rules. Separate role instructions guide the investigation and the brief. Report styling follows a template.

The captured example contains actual Claude responses on synthetic data. Its analyst assignment and follow-up are illustrative. Replaying it recalculates the requested checks and rejects changed inputs; it makes no new API call. Questions still need human review, and the record is not an approved business recommendation.

The analyst must distinguish a cost variance against budget from a net operating result and reconcile the full bridge of favorable and adverse movements. Note N13 also confirms a signed change order for partial recovery, so the next check is its amount and whether billings already include it. The case study keeps the model's questions visible alongside these review points.

Broader finance agents would need additional source data and a specific business need. For this project, ledger posting, investment research and paid market-data feeds would add scope without improving the business-line review.
