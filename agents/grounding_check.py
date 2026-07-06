"""Narrative grounding checks — shared logic.

Extracted so both agents/qa_agent.py (the production QA/Reviewer Agent) and
tests/validate_narrative.py (the standalone dev-time re-validation script)
run the exact same check, rather than maintaining two copies. Unlike the
ingestion/variance/forecast validators, none of this logic needs
data/ground_truth.md — it only cross-references the narrative against the
two upstream reports it was actually given, which is exactly what a real
QA/Reviewer step could do in production (there is no hidden answer key on
a live monthly close).

See tests/validate_narrative.py for the CLI entry point and full rationale
for the tolerance choices.
"""

import re

MONEY_TOLERANCE_REL = 0.005
MONEY_TOLERANCE_ABS = 15_000
PERCENT_TOLERANCE_ABS = 1.0

MONEY_PATTERN = re.compile(
    r"(?:EUR|€)\s?(-?\d[\d,]*\.?\d*)\s?(million|mn|m|thousand|k)?\b",
    re.IGNORECASE,
)
PERCENT_PATTERN = re.compile(r"([+-]?\d+\.?\d*)\s?(?:%|percent\b)", re.IGNORECASE)
BARE_SIGNED_MONEY_PATTERN = re.compile(r"[+-]\d{1,3}(?:,\d{3})+(?:\.\d+)?")

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


def parse_bare_signed_money_matches(text):
    values = []
    for match in BARE_SIGNED_MONEY_PATTERN.findall(text):
        try:
            values.append(float(match.replace(",", "")))
        except ValueError:
            continue
    return values


def source_money_pool(*texts):
    pool = []
    for text in texts:
        pool += parse_money_matches(text) + parse_bare_signed_money_matches(text)
    return pool


def source_percent_pool(*texts):
    pool = []
    for text in texts:
        pool += parse_percent_matches(text)
    return pool


def money_matches_source(value, source_values):
    """Compare magnitudes, not signed values: prose commonly states a variance
    as a positive amount with direction conveyed in words ("EUR197,000 under
    budget"), while source tables store the same figure signed ("-196,953")."""
    if not source_values:
        return False
    value = abs(value)
    for src in source_values:
        src = abs(src)
        if src == 0:
            continue
        diff = abs(value - src)
        if diff / src <= MONEY_TOLERANCE_REL and diff <= MONEY_TOLERANCE_ABS:
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


TRAP_KEYWORDS = ("data entry", "data quality", "data error")
BUSINESS_FRAMING_KEYWORDS = (
    "client project", "cost overrun caused", "driven by a client",
    "fx-driven variance in production revenue",
)


def check_trap_not_narrated(narrative_text):
    """The excluded data-entry-error row must not be framed as a business event.

    Scoped to the paragraph(s) that actually mention the trap, not the whole
    document — the narrative legitimately discusses unrelated business events
    (e.g. a real client project overrun) elsewhere, and a document-wide keyword
    scan would misfire on that unrelated mention.
    """
    paragraphs = [p for p in re.split(r"\n\s*\n", narrative_text) if p.strip()]
    trap_paragraphs = [p for p in paragraphs if any(kw in p.lower() for kw in TRAP_KEYWORDS)]
    if not trap_paragraphs:
        return True, "excluded data-error row not mentioned (acceptable — one sentence was optional)"
    for p in trap_paragraphs:
        if any(kw in p.lower() for kw in BUSINESS_FRAMING_KEYWORDS):
            return False, f"a paragraph mentioning the excluded data-error row also uses business-framing language: {p.strip()[:200]!r}"
    return True, "excluded data-error row is mentioned without being framed as a business event"


def run_all_checks(variance_text, forecast_text, narrative_text):
    """Returns a list of (passed: bool, message: str) tuples covering every
    grounding check: money figures, percentages, and the two honesty rules."""
    source_money = source_money_pool(variance_text, forecast_text)
    source_percent = source_percent_pool(variance_text, forecast_text)
    narrative_money = parse_money_matches(narrative_text)
    narrative_percent = parse_percent_matches(narrative_text)

    results = []

    unmatched_money = [v for v in narrative_money if not money_matches_source(v, source_money)]
    if unmatched_money:
        results.append((False, (
            f"HALLUCINATED MONEY FIGURE(S) — not within {MONEY_TOLERANCE_REL:.1%}/"
            f"EUR{MONEY_TOLERANCE_ABS:,.0f} of any source figure: "
            f"{[f'EUR{v:,.0f}' for v in unmatched_money]}"
        )))
    else:
        results.append((True, (
            f"All {len(narrative_money)} monetary figure(s) in the narrative trace back to a "
            f"source figure within {MONEY_TOLERANCE_REL:.1%}/EUR{MONEY_TOLERANCE_ABS:,.0f}"
        )))

    unmatched_percent = [v for v in narrative_percent if not percent_matches_source(v, source_percent)]
    if unmatched_percent:
        results.append((False, (
            f"HALLUCINATED PERCENTAGE(S) — not within {PERCENT_TOLERANCE_ABS} pp of any source "
            f"figure: {unmatched_percent}"
        )))
    else:
        results.append((True, (
            f"All {len(narrative_percent)} percentage(s) in the narrative trace back to a "
            f"source figure within {PERCENT_TOLERANCE_ABS} pp"
        )))

    results.append(check_no_clear_driver_preserved(variance_text, narrative_text))
    results.append(check_trap_not_narrated(narrative_text))
    return results
