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

Tolerance: money figures must be within 2% relative error AND within
EUR15,000 absolute error of some source figure; percentages within 1.0
percentage point absolute error. The combined relative+absolute band on
money is deliberate: with a 30-million-euro monthly forecast in play, a
relative-only tolerance lets two unrelated multi-million figures "match"
just from being the same order of magnitude (a fabricated EUR9,999,999
would fall within 3% of a real EUR9,901,455 line). The absolute cap closes
that hole while the relative band still covers normal prose rounding
("EUR2.08 million" for "EUR2,077,456").

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

import re
import sys

VARIANCE_REPORT_PATH = "output/variance_report.md"
FORECAST_REPORT_PATH = "output/forecast_report.md"
NARRATIVE_PATH = "output/executive_summary.md"

# Both must hold: a relative band (covers "EUR2.08 million" for "EUR2,077,456")
# capped by a small absolute band, so two unrelated multi-million-euro figures
# can't coincidentally "match" just from being the same order of magnitude —
# 3% of EUR9.9M is nearly EUR300k, wide enough that a fabricated EUR9,999,999
# would otherwise pass as if it were a real EUR9,901,455. The absolute cap
# closes that hole while still covering normal rounding on small figures.
MONEY_TOLERANCE_REL = 0.02
MONEY_TOLERANCE_ABS = 15_000
PERCENT_TOLERANCE_ABS = 1.0

# EUR12,345 / EUR12,345.67 / EUR2.08 million / EUR2.08m / EUR197k / EUR197,000
MONEY_PATTERN = re.compile(
    r"(?:EUR|€)\s?(-?\d[\d,]*\.?\d*)\s?(million|mn|m|thousand|k)?\b",
    re.IGNORECASE,
)
# +26.6% / -9.3% / 26.6 percent — no \b directly after the "%" literal itself
# (a non-word character followed by whitespace has no word boundary, so a
# trailing \b there silently never matches; only "percent" as a word needs it)
PERCENT_PATTERN = re.compile(r"([+-]?\d+\.?\d*)\s?(?:%|percent\b)", re.IGNORECASE)

SUFFIX_MULTIPLIER = {
    None: 1, "": 1,
    "k": 1_000, "thousand": 1_000,
    "m": 1_000_000, "mn": 1_000_000, "million": 1_000_000,
}


def parse_money_matches(text):
    values = []
    for amount, suffix in MONEY_PATTERN.findall(text):
        amount = amount.replace(",", "")
        try:
            value = float(amount)
        except ValueError:
            continue
        mult = SUFFIX_MULTIPLIER.get(suffix.lower() if suffix else None, 1)
        values.append(value * mult)
    return values


def parse_percent_matches(text):
    values = []
    for amount in PERCENT_PATTERN.findall(text):
        try:
            values.append(float(amount))
        except ValueError:
            continue
    return values


def load(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def money_matches_source(value, source_values):
    if not source_values:
        return False
    for src in source_values:
        if src == 0:
            continue
        diff = abs(value - src)
        if diff / abs(src) <= MONEY_TOLERANCE_REL and diff <= MONEY_TOLERANCE_ABS:
            return True
    return False


def percent_matches_source(value, source_values):
    for src in source_values:
        if abs(value - src) <= PERCENT_TOLERANCE_ABS:
            return True
    return False


def check_no_clear_driver_preserved(variance_text, narrative_text):
    """Every material row in the variance report explained as 'no clear driver
    identified' should be echoed as unexplained/follow-up in the narrative, via
    the honesty-preserving keywords the system prompt asked for."""
    n_no_driver_rows = variance_text.count("No clear driver identified")
    if n_no_driver_rows == 0:
        return True, "no 'no clear driver identified' rows in the source report to check"
    honesty_keywords = [
        "no clear driver", "no documented", "undocumented", "unexplained",
        "not yet explained", "follow-up", "follow up", "no driver identified",
        "lacks a documented", "without a documented",
    ]
    lower = narrative_text.lower()
    found = any(kw in lower for kw in honesty_keywords)
    if found:
        return True, f"narrative preserves the honesty language ({n_no_driver_rows} source rows had no driver)"
    return False, (
        f"source report has {n_no_driver_rows} 'no clear driver identified' row(s), "
        "but the narrative contains none of the expected unexplained/follow-up language"
    )


def check_trap_not_narrated(narrative_text):
    """The excluded data-entry-error row must not be framed as a business event."""
    lower = narrative_text.lower()
    trap_mentioned = "data entry" in lower or "data quality" in lower or "data error" in lower
    if not trap_mentioned:
        return True, "excluded data-error row not mentioned (acceptable — one sentence was optional)"
    business_framing = any(
        phrase in lower for phrase in [
            "client project", "cost overrun caused", "driven by a client",
            "fx-driven variance in production revenue",
        ]
    )
    if business_framing:
        return False, "the excluded data-error row appears to be narrated as a business event"
    return True, "excluded data-error row is mentioned without being framed as a business event"


def main():
    variance_text = load(VARIANCE_REPORT_PATH)
    forecast_text = load(FORECAST_REPORT_PATH)
    narrative_text = load(NARRATIVE_PATH)

    source_money = parse_money_matches(variance_text) + parse_money_matches(forecast_text)
    source_percent = parse_percent_matches(variance_text) + parse_percent_matches(forecast_text)

    narrative_money = parse_money_matches(narrative_text)
    narrative_percent = parse_percent_matches(narrative_text)

    failures, passes = [], []

    unmatched_money = [v for v in narrative_money if not money_matches_source(v, source_money)]
    if unmatched_money:
        failures.append(
            f"HALLUCINATED MONEY FIGURE(S) — not within {MONEY_TOLERANCE_REL:.0%}/"
            f"EUR{MONEY_TOLERANCE_ABS:,.0f} of any source figure: "
            f"{[f'EUR{v:,.0f}' for v in unmatched_money]}"
        )
    else:
        passes.append(
            f"All {len(narrative_money)} monetary figure(s) in the narrative trace back to a "
            f"source figure within {MONEY_TOLERANCE_REL:.0%}/EUR{MONEY_TOLERANCE_ABS:,.0f}"
        )

    unmatched_percent = [v for v in narrative_percent if not percent_matches_source(v, source_percent)]
    if unmatched_percent:
        failures.append(
            f"HALLUCINATED PERCENTAGE(S) — not within {PERCENT_TOLERANCE_ABS} pp of any source "
            f"figure: {unmatched_percent}"
        )
    else:
        passes.append(
            f"All {len(narrative_percent)} percentage(s) in the narrative trace back to a "
            f"source figure within {PERCENT_TOLERANCE_ABS} pp"
        )

    ok, msg = check_no_clear_driver_preserved(variance_text, narrative_text)
    (passes if ok else failures).append(msg)

    ok, msg = check_trap_not_narrated(narrative_text)
    (passes if ok else failures).append(msg)

    print("=== Narrative Agent Validation ===\n")
    print(f"Narrative: {len(narrative_money)} money figure(s), {len(narrative_percent)} percentage(s)")
    print(f"Source pool: {len(source_money)} money figure(s), {len(source_percent)} percentage(s)")
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
