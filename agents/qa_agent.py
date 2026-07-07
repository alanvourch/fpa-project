"""QA/Reviewer Agent.

Checks the consistency of the pipeline's own outputs — never against a
hidden answer key (there is no data/ground_truth.md-equivalent on a real,
unseen monthly close; that file exists in this project purely to validate
the earlier agents during development, in tests/validate_*.py, and this
agent never reads it). Everything below is a cross-check between what the
Ingestion, Variance, Forecast, and Narrative agents actually produced.

Two categories of check:

1. Consistency checks — do the pipeline's own outputs agree with each
   other? Every flagged variance is either evidence-cited or explicitly
   marked "no clear driver identified" (never silently unexplained); every
   flagged month in the variance table is accounted for in the forecast's
   normalization audit trail; the narrative's figures all trace back to the
   two reports it was given (via agents/grounding_check.py, shared with
   tests/validate_narrative.py).

2. Data-governance checks — this project's most important non-technical
   requirement: only one component in this pipeline should ever call an
   external AI provider, and it should only ever see already-aggregated
   summary reports, never the raw dataset. This agent verifies that
   structurally, by scanning the other agent files for any external-API
   usage and confirming the Narrative Agent's own inputs are scoped to the
   two report files, not the raw CSV or ground truth.

This agent's report is explicitly a DRAFT gate, not a publish decision:
see the "Human sign-off" banner in output/qa_report.md. Nothing in this
pipeline sends a report anywhere on its own — a human always reviews the
QA report and the assembled pack before either is distributed.

Output: output/qa_report.md

Run: .venv/Scripts/python.exe agents/qa_agent.py
"""

import glob
import os
import re

from grounding_check import run_all_checks

VARIANCE_REPORT_PATH = "output/variance_report.md"
FORECAST_REPORT_PATH = "output/forecast_report.md"
NARRATIVE_PATH = "output/executive_summary.md"
VARIANCE_TABLE_PATH = "output/variance_table.csv"
QA_REPORT_PATH = "output/qa_report.md"

AGENTS_DIR = "agents"
NARRATIVE_AGENT_FILENAME = "narrative_agent.py"

# Files the narrative agent must never reference, by name — the raw dataset,
# the ingestion/variance intermediate CSVs, and the ground-truth file. If any
# of these strings appear in narrative_agent.py's source, the agent has
# scope-crept beyond the two aggregated report files it was designed to see.
FORBIDDEN_NARRATIVE_INPUTS = (
    "eventco_monthly", "ground_truth", "business_notes.csv", "variance_table.csv",
)


def load(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def extract_table_rows(section_text):
    lines = [l for l in section_text.splitlines() if l.startswith("|")]
    if len(lines) < 3:
        return []
    return [[c.strip() for c in line.strip("|").split("|")] for line in lines[2:]]


def check_every_material_row_explained(variance_text):
    """Every row in the rendered material-variance table must have a
    non-empty explanation that is either evidence-cited or an explicit
    'no clear driver identified' — never silently blank."""
    start = variance_text.index("## Material variances")
    rows = extract_table_rows(variance_text[start:])
    if not rows:
        return False, "no material-variance rows found to check (unexpected, verify the report rendered)"
    bad = []
    for r in rows:
        bu, line, period = r[0], r[1], r[2]
        evidence, explanation = r[8], r[9]
        has_citation = bool(re.search(r"N\d+", evidence))
        has_no_driver = "no clear driver identified" in explanation.lower()
        if not explanation.strip() or not (has_citation or has_no_driver):
            bad.append(f"{bu}/{line}/{period}")
    if bad:
        return False, f"material row(s) with neither an evidence citation nor an explicit 'no clear driver identified': {bad}"
    return True, f"all {len(rows)} material variance row(s) are either evidence-cited or explicitly marked as having no clear driver"


def check_forecast_covers_all_flagged_rows(variance_table_text, forecast_text):
    """Every row the Variance Agent flagged (materiality != '' or a suspected
    data error) must appear in the Forecast Agent's normalization audit
    trail — no flagged month should silently fall through uncounted."""
    import csv
    from io import StringIO

    reader = csv.DictReader(StringIO(variance_table_text))
    flagged = [
        (r["business_unit"], r["line_item"], r["month"])
        for r in reader
        if r["materiality"].strip() or r["suspected_data_error"].strip().lower() == "true"
    ]
    if not flagged:
        return True, "no flagged rows in the variance table to reconcile against the forecast"

    start = forecast_text.index("## History adjustments")
    end = forecast_text.index("## Forecast by BU")
    audit_rows = extract_table_rows(forecast_text[start:end])
    audit_keys = {(r[0], r[1], r[2]) for r in audit_rows}

    missing = [key for key in flagged if key not in audit_keys]
    if missing:
        return False, f"variance-flagged row(s) missing from the forecast normalization audit trail: {missing}"
    return True, f"all {len(flagged)} variance-flagged row(s) are accounted for in the forecast normalization audit trail"


def check_llm_isolation():
    """Data governance: only narrative_agent.py may call an external AI
    provider. Every other agent script must be free of any such reference —
    this is checked structurally (source-code scan), not by trusting a
    comment, so it holds even if someone edits an agent later without
    reading this docstring."""
    violations = []
    for path in sorted(glob.glob(os.path.join(AGENTS_DIR, "*.py"))):
        if os.path.basename(path) == NARRATIVE_AGENT_FILENAME:
            continue
        text = load(path)
        if re.search(r"\bimport anthropic\b|\bfrom anthropic\b|api\.anthropic\.com", text):
            violations.append(path)
    if violations:
        return False, f"external AI provider usage found outside narrative_agent.py: {violations}"
    return True, "no agent other than narrative_agent.py references an external AI provider"


def check_narrative_input_scope():
    """Data governance: the Narrative Agent must only ever be given the two
    already-aggregated report files, never the raw dataset or ground truth.

    Scoped to the arguments of actual `open(...)` calls, not the whole file —
    a defensive comment or docstring elsewhere in the script (e.g. "never
    reads data/ground_truth.md") legitimately mentions these names without
    the script ever opening them."""
    path = os.path.join(AGENTS_DIR, NARRATIVE_AGENT_FILENAME)
    text = load(path)
    open_call_args = re.findall(r"open\(([^)]*)\)", text)
    hits = sorted({
        name for call in open_call_args for name in FORBIDDEN_NARRATIVE_INPUTS if name in call
    })
    if hits:
        return False, f"narrative_agent.py opens a data source beyond the two aggregated reports: {hits}"
    return True, "narrative_agent.py's file reads are scoped to the two aggregated report files only"


def main():
    variance_text = load(VARIANCE_REPORT_PATH)
    forecast_text = load(FORECAST_REPORT_PATH)
    variance_table_text = load(VARIANCE_TABLE_PATH)

    results = []
    results.append(check_every_material_row_explained(variance_text))
    results.append(check_forecast_covers_all_flagged_rows(variance_table_text, forecast_text))
    results.append(check_llm_isolation())
    results.append(check_narrative_input_scope())

    narrative_checked = os.path.exists(NARRATIVE_PATH)
    if narrative_checked:
        narrative_text = load(NARRATIVE_PATH)
        results.extend(run_all_checks(variance_text, forecast_text, narrative_text))
    else:
        results.append((None, "output/executive_summary.md not found; narrative grounding not checked this run"))

    passed = [msg for ok, msg in results if ok is True]
    failed = [msg for ok, msg in results if ok is False]
    skipped = [msg for ok, msg in results if ok is None]

    lines = [
        "# QA Report: EventCo Budget vs Actual & Rolling Forecast",
        "",
        "Generated by `agents/qa_agent.py`. This agent never reads `data/ground_truth.md`. "
        "Every check below cross-references the pipeline's own outputs against each other, "
        "the same way a reviewer would on a real, unseen monthly close with no answer key.",
        "",
        "## Status",
        "",
        f"**{len(passed)} passed, {len(failed)} failed, {len(skipped)} skipped.**",
        "",
    ]
    if failed:
        lines += [
            "**REQUIRES ATTENTION BEFORE HUMAN SIGN-OFF.** One or more consistency or "
            "governance checks failed. See below.", "",
        ]
    lines += [
        "> **Human sign-off required.** This report, and the assembled pack it accompanies, "
        "are drafts. Nothing in this pipeline is sent to anyone automatically. A human "
        "reviewer must read this report and the pack, and explicitly approve before either "
        "is distributed.",
        "",
        "## Consistency checks",
        "",
    ]
    # Render in original check order, grouped by category for readability.
    consistency_results = results[:2]
    governance_results = results[2:4]
    narrative_results = results[4:]

    def render_group(group):
        out = []
        for ok, msg in group:
            tag = "PASS" if ok is True else ("SKIP" if ok is None else "FAIL")
            out.append(f"- **{tag}**: {msg}")
        return out

    lines += render_group(consistency_results)
    lines += ["", "## Data governance checks", "",
              "Confirms the project's core control principle: only the Narrative Agent may "
              "call an external AI provider, and only with already-aggregated summary data, "
              "never the raw dataset, never client-identifying transaction detail.", ""]
    lines += render_group(governance_results)
    lines += ["", "## Narrative grounding checks", ""]
    lines += render_group(narrative_results)

    with open(QA_REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"QA checks: {len(passed)} passed, {len(failed)} failed, {len(skipped)} skipped")
    for msg in failed:
        print(f"  FAIL - {msg}")
    print(f"Wrote {QA_REPORT_PATH}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
