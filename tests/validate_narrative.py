"""Validation script for the Narrative Agent.

Unlike the Ingestion/Variance/Forecast validators, there is no ground-truth
table to diff free-text prose against. Instead this is a hallucination
check: extract every monetary figure and percentage mentioned in
output/executive_summary.md, and confirm each one actually derives from a
figure present in output/variance_report.md or output/forecast_report.md
(the only two documents the narrative agent was given). A figure that
doesn't match anything in the source reports — within a tolerance that
allows for the light, readability rounding the agent's prompt explicitly
permits ("EUR2.08 million" for "EUR2,077,456") — is flagged as a probable
hallucination and fails the check loudly.

The actual parsing/matching logic lives in agents/grounding_check.py and is
shared with agents/qa_agent.py — this script is a thin CLI wrapper for
standalone dev-time re-validation. See that module's docstring for the full
tolerance rationale (money: 0.5% relative AND EUR15,000 absolute; percent:
1.0 percentage point absolute — both deliberately tight given ~280
candidate source figures across the two reports).

Also checks the two honesty requirements from the agent's system prompt:
- every "no clear driver identified" variance in the source report is
  reflected as unexplained/follow-up language in the narrative, not
  smoothed into a confident-sounding explanation
- the excluded data-entry-error row is not narrated as a business event

Known limitation: the trap check is keyword-based (it looks for data-quality
language, then checks that language isn't paired with business-event
phrasing). It cannot catch a narrative that fabricates a plausible business
story around the excluded figure WITHOUT ever using a data-quality word —
that would require semantic understanding this script doesn't have. This
mirrors the accepted, documented heuristic limitations elsewhere in this
project (e.g. the ingestion agent's IQR tier in Phase 3); the money/percent
hallucination check remains the primary, harder-to-evade safety net, since
the excluded figure's magnitude is real but its narration as a "cause" is
what would need to be invented.

Run: .venv/Scripts/python.exe tests/validate_narrative.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agents.grounding_check import parse_money_matches, parse_percent_matches, run_all_checks

VARIANCE_REPORT_PATH = "output/variance_report.md"
FORECAST_REPORT_PATH = "output/forecast_report.md"
NARRATIVE_PATH = "output/executive_summary.md"


def load(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def main():
    variance_text = load(VARIANCE_REPORT_PATH)
    forecast_text = load(FORECAST_REPORT_PATH)
    narrative_text = load(NARRATIVE_PATH)

    results = run_all_checks(variance_text, forecast_text, narrative_text)
    passes = [msg for ok, msg in results if ok]
    failures = [msg for ok, msg in results if not ok]

    print("=== Narrative Agent Validation ===\n")
    print(f"Narrative: {len(parse_money_matches(narrative_text))} money figure(s), "
          f"{len(parse_percent_matches(narrative_text))} percentage(s)")
    print()
    for p in passes:
        print(f"  PASS - {p}")
    for f in failures:
        print(f"  FAIL - {f}")

    print()
    if failures:
        print(f"RESULT: {len(failures)} failure(s) found.")
        sys.exit(1)
    print("RESULT: all checks passed.")
    sys.exit(0)


if __name__ == "__main__":
    main()
