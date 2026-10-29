"""Cross-output checks and constrained commentary checks. Source scans are limited regression checks, not runtime isolation."""
import glob
import os
import re

from grounding_check import run_all_checks
from release_gate import stamp_manifest

VARIANCE_REPORT_PATH = "output/variance_report.md"
FORECAST_REPORT_PATH = "output/forecast_report.md"
NARRATIVE_PATH = "output/executive_summary.md"
VARIANCE_TABLE_PATH = "output/variance_table.csv"
QA_REPORT_PATH = "output/qa_report.md"

AGENTS_DIR = "agents"
NARRATIVE_AGENT_FILENAME = "narrative_agent.py"

# Files the narrative agent must never reference, by name: the raw dataset,
# the ingestion/variance intermediate CSVs, and the ground-truth file. If any
# of these strings appear in narrative_agent.py's source, the agent has
# scope-crept beyond the two aggregated report files it was designed to see.
FORBIDDEN_NARRATIVE_INPUTS = (
    "eventco_monthly", "ground_truth", "business_notes.csv", "variance_table.csv",
    "analyst_commentary.csv", "eventco_drivers.csv",
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
    """Every row in the rendered material-variance table must carry exactly
    one of the three legitimate explanation types: an evidence citation, a
    clearly-labeled manual analyst input, or an explicit 'no clear driver
    identified'; never silently blank, never an unlabeled cause."""
    start = variance_text.index("## Material variances")
    rows = extract_table_rows(variance_text[start:])
    if not rows:
        return False, "no material-variance rows found to check (unexpected, verify the report rendered)"
    bad = []
    counts = {"evidence": 0, "analyst": 0, "open": 0}
    for r in rows:
        bu, line, period = r[0], r[1], r[2]
        evidence, explanation = r[8], r[9]
        has_citation = bool(re.search(r"N\d+", evidence))
        has_analyst = "analyst input" in explanation.lower()
        has_no_driver = "no clear driver identified" in explanation.lower()
        if has_citation:
            counts["evidence"] += 1
        elif has_analyst:
            counts["analyst"] += 1
        elif has_no_driver:
            counts["open"] += 1
        if not explanation.strip() or not (has_citation or has_analyst or has_no_driver):
            bad.append(f"{bu}/{line}/{period}")
    if bad:
        return False, f"material row(s) with no evidence citation, no labeled analyst input, and no explicit 'no clear driver identified': {bad}"
    return True, (f"all {len(rows)} material variance row(s) carry a legitimate explanation type: "
                  f"{counts['evidence']} evidence-cited, {counts['analyst']} labeled analyst input, "
                  f"{counts['open']} explicitly open")


def check_forecast_covers_all_flagged_rows(variance_table_text, forecast_text):
    """Every row the Variance Agent flagged (materiality != '' or a suspected
    data error) must appear in the Forecast Agent's normalization audit
    trail; no flagged month should silently fall through uncounted."""
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
        return False, f"variance-flagged row(s) missing from the forecast recurrence-decision audit trail: {missing}"
    return True, f"all {len(flagged)} variance-flagged row(s) are accounted for in the forecast recurrence-decision audit trail"


def check_llm_isolation():
    """Detect specified Anthropic import/endpoint regressions only."""
    violations = []
    for path in sorted(glob.glob(os.path.join(AGENTS_DIR, "*.py"))):
        if os.path.basename(path) == NARRATIVE_AGENT_FILENAME:
            continue
        text = load(path)
        if re.search(r"\bimport anthropic\b|\bfrom anthropic\b|api\.anthropic\.com", text):
            violations.append(path)
    if violations:
        return False, f"external AI provider usage found outside narrative_agent.py: {violations}"
    return True, "Limited source regression scan: no specified Anthropic reference outside narrative_agent.py; this is not runtime network isolation or data-loss prevention"


def check_narrative_input_scope():
    """Limited scan for specified prohibited literal filenames in open() calls.

    Scoped to the arguments of actual `open(...)` calls, not the whole file:
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
    return True, "Limited input regression scan: no prohibited filename in literal open() calls; not a comprehensive input or confidentiality control"


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
        results.append((False, "Executive summary missing; required commentary validation cannot run"))

    passed = [msg for ok, msg in results if ok is True]
    failed = [msg for ok, msg in results if ok is False]
    skipped = [msg for ok, msg in results if ok is None]

    lines = [
        "# QA Report: EventCo Budget vs Actual & Rolling Forecast",
        "",
        "Generated by `agents/qa_agent.py`. This agent never reads `data/ground_truth.md`. "
        "Every check below cross-references the pipeline's own outputs against each other, "
        "the same way a reviewer would on a real, unseen monthly pack with no answer key.",
        "",
        "## Status",
        "",
        f"**{len(passed)} passed, {len(failed)} failed, {len(skipped)} skipped.**",
        "",
    ]
    if failed:
        lines += [
            "**FAILED REVIEW: SITE BUILD BLOCKED.** One or more consistency or "
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
              "These source scans detect specified regressions only. Calculations run locally. "
              "The optional AI ordering step sends a structured statement catalogue to its provider. "
              "Business context can identify clients even after aggregation; live employer data needs an approved confidentiality policy.", ""]
    lines += render_group(governance_results)
    lines += ["", "## Narrative grounding checks", ""]
    lines += render_group(narrative_results)

    with open(QA_REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    # Only the orchestrator can grant a fresh build manifest after ALL validators.
    # A standalone QA pass does not replace the full pipeline validation.
    if failed:
        stamp_manifest(False, "; ".join(failed))
    print(f"QA checks: {len(passed)} passed, {len(failed)} failed, {len(skipped)} skipped")
    for msg in failed:
        print(f"  FAIL - {msg}")
    print(f"Wrote {QA_REPORT_PATH}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
