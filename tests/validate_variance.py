"""Validation script for the Variance & Root-Cause Agent.

Same pattern as tests/validate_ingestion.py: the agent must never read
data/ground_truth.md, but this script's entire job is to read it and check
the agent's already-written output (output/variance_report.md) against it
after the fact. It verifies that:

  1. Every real business anomaly month is flagged as material.
  2. Every anomaly's explanation cites at least one of its designated signal
     notes (grounded, correct attribution).
  3. No material row cites evidence unless it overlaps a real anomaly, and
     never a note belonging to a different anomaly (no false attributions).
  4. Noise notes are never cited anywhere (no hallucinated causes).
  5. Material rows not matching any real anomaly say "no clear driver
     identified" instead of inventing an explanation.
  6. The favorable anomaly is reported and marked F.
  7. The fat-finger trap does not resurface as a business variance story —
     it must sit in the excluded-data-errors section, not the material table.

Run: .venv/Scripts/python.exe tests/validate_variance.py
"""

import re
import sys

GROUND_TRUTH_PATH = "data/ground_truth.md"
REPORT_PATH = "output/variance_report.md"

COLUMN_PHRASE_MAP = [
    (re.compile(r"COGS actual", re.I), "cogs_actual"),
    (re.compile(r"Revenue actual", re.I), "revenue_actual"),
    (re.compile(r"IT opex actual", re.I), "opex_it_actual"),
    (re.compile(r"Marketing opex actual", re.I), "opex_marketing_actual"),
]

# ground-truth column name -> line item label used in the variance report
COLUMN_TO_LINE = {
    "cogs_actual": "COGS",
    "revenue_actual": "Revenue",
    "opex_it_actual": "Opex - IT",
    "opex_marketing_actual": "Opex - Marketing",
}


def month_range(start, end):
    """Inclusive list of YYYY-MM strings."""
    y, m = map(int, start.split("-"))
    ey, em = map(int, end.split("-"))
    out = []
    while (y, m) <= (ey, em):
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


def parse_ground_truth(path):
    text = open(path, encoding="utf-8").read()
    business_section = text.split("## 2. Data quality issues", 1)[0]
    notes_section = text.split("## 4. Business notes evidence map", 1)[1]

    anomaly_months = []
    for line in business_section.splitlines():
        m = re.match(r"- \*\*([\w\-&/ ]+) / (\d{4}-\d{2})\*\* — (.+)", line)
        if not m:
            continue
        bu, month, rest = m.groups()
        column = next((col for pat, col in COLUMN_PHRASE_MAP if pat.search(rest)), None)
        anomaly_months.append({"business_unit": bu.strip(), "month": month, "column": column})

    signal_notes = {}  # BU -> set of note ids (one real anomaly per BU in this dataset)
    for line in notes_section.splitlines():
        m = re.match(r"- \*\*([\w\-&/ ]+) / (\w+)\*\*.*signal notes: ([N\d, ]+)", line)
        if m:
            bu, _column, ids = m.groups()
            signal_notes.setdefault(bu.strip(), set()).update(
                i.strip() for i in ids.split(","))
    noise_match = re.search(r"Noise notes[^:]*: ([N\d, ]+)", notes_section)
    noise_notes = {i.strip() for i in noise_match.group(1).split(",")} if noise_match else set()

    return anomaly_months, signal_notes, noise_notes


def get_section(text, header, next_header=None):
    start = text.index(header)
    end = text.index(next_header, start) if next_header else len(text)
    return text[start:end]


def extract_table_rows(section_text):
    table_lines = [l for l in section_text.splitlines() if l.startswith("|")]
    if len(table_lines) < 3:
        return []
    return [[c.strip() for c in line.strip("|").split("|")] for line in table_lines[2:]]


def parse_report(path):
    text = open(path, encoding="utf-8").read()
    excluded_section = get_section(
        text, "## Excluded from analysis", "## Material variances")
    material_section = get_section(text, "## Material variances")

    excluded = [
        {"business_unit": r[0], "line_item": r[1], "month": r[2]}
        for r in extract_table_rows(excluded_section)
    ]

    material = []
    for r in extract_table_rows(material_section):
        bu, line_item, period = r[0], r[1], r[2]
        direction, evidence, explanation = r[7], r[8], r[9]
        if ".." in period:
            start, end = period.split("..")
            months = month_range(start, end)
        else:
            months = [period]
        cited = set(re.findall(r"N\d+", evidence))
        material.append({
            "business_unit": bu, "line_item": line_item, "months": months,
            "direction": direction, "cited": cited, "explanation": explanation,
        })
    return excluded, material


def main():
    anomaly_months, signal_notes, noise_notes = parse_ground_truth(GROUND_TRUTH_PATH)
    excluded, material = parse_report(REPORT_PATH)

    failures, passes = [], []

    # Index truth anomaly months by BU for overlap tests
    truth_by_bu = {}
    for a in anomaly_months:
        truth_by_bu.setdefault(a["business_unit"], set()).add(a["month"])

    # 1 + 2: every anomaly month flagged material on the right line, and the
    # covering rows cite that anomaly's signal notes
    missed, unexplained = [], []
    for a in anomaly_months:
        want_line = COLUMN_TO_LINE.get(a["column"])
        covering = [
            m for m in material
            if m["business_unit"] == a["business_unit"] and a["month"] in m["months"]
            and (want_line is None or m["line_item"] == want_line)
        ]
        if not covering:
            missed.append((a["business_unit"], a["month"], a["column"]))
            continue
        cited = set().union(*(m["cited"] for m in covering))
        if not (cited & signal_notes.get(a["business_unit"], set())):
            unexplained.append((a["business_unit"], a["month"], a["column"]))
    if missed:
        failures.append(f"MISSED ANOMALY MONTH(S) — not flagged material: {missed}")
    else:
        passes.append(f"All {len(anomaly_months)} real anomaly months flagged as material on the right line item")
    if unexplained:
        failures.append(f"UNGROUNDED — anomaly months flagged but not explained via their signal notes: {unexplained}")
    else:
        passes.append("Every real anomaly is explained with a citation of its own signal note(s)")

    # 3 + 4 + 5: citation discipline on every material row
    false_attributions, noise_cited, invented = [], [], []
    for m in material:
        row_id = (m["business_unit"], m["line_item"], f"{m['months'][0]}..{m['months'][-1]}")
        overlaps_truth = bool(
            truth_by_bu.get(m["business_unit"], set()) & set(m["months"]))
        if m["cited"]:
            bad = m["cited"] - signal_notes.get(m["business_unit"], set())
            if bad or not overlaps_truth:
                false_attributions.append((row_id, sorted(m["cited"])))
            if m["cited"] & noise_notes:
                noise_cited.append((row_id, sorted(m["cited"] & noise_notes)))
        elif not overlaps_truth and "no clear driver identified" not in m["explanation"].lower() \
                and "analyst input" not in m["explanation"].lower():
            # A row outside any real anomaly may carry clearly-labeled manual
            # analyst commentary (the human half of the workflow) or the
            # explicit no-driver statement — anything else is the agent
            # inventing a cause, which is exactly what must never happen.
            invented.append(row_id)
    if false_attributions:
        failures.append(f"FALSE ATTRIBUTION(S) — rows citing notes that don't belong to their anomaly: {false_attributions}")
    else:
        passes.append("No false attributions: every citation belongs to the citing row's own real anomaly")
    if noise_cited:
        failures.append(f"NOISE NOTE(S) CITED: {noise_cited}")
    else:
        passes.append(f"None of the {len(noise_notes)} noise notes is cited anywhere")
    if invented:
        failures.append(f"INVENTED CAUSE(S) — material rows outside any real anomaly lacking a 'no clear driver' statement or a labeled analyst input: {invented}")
    else:
        n_analyst = sum(1 for m in material if not m["cited"]
                        and "analyst input" in m["explanation"].lower())
        n_open = sum(1 for m in material if not m["cited"]
                     and "no clear driver identified" in m["explanation"].lower())
        passes.append(f"All {n_analyst + n_open} material rows without evidence are honest: "
                      f"{n_analyst} carry clearly-labeled analyst input, {n_open} say 'no clear driver identified'")

    # 6: the favorable anomaly is reported and marked F
    favorable_rows = [
        m for m in material
        if m["cited"] & signal_notes.get(m["business_unit"], set()) and m["direction"] == "F"
    ]
    if favorable_rows:
        passes.append("Favorable variance(s) covered and marked F: "
                      + ", ".join(f"{m['business_unit']}/{m['line_item']}" for m in favorable_rows))
    else:
        failures.append("FAVORABLE MISSING — no explained anomaly row is marked F")

    # 7: the fat-finger trap stays a data error, not a variance story
    trap_in_material = [
        (m["business_unit"], m["line_item"], m["months"]) for m in material
        if m["business_unit"] == "Brand Events" and m["line_item"] == "Revenue"
        and "2025-11" in m["months"]
    ]
    trap_excluded = any(
        e["business_unit"] == "Brand Events" and e["line_item"] == "Revenue"
        and e["month"] == "2025-11" for e in excluded
    )
    if trap_in_material:
        failures.append(f"TRAP RESURFACED as a material business variance: {trap_in_material}")
    elif not trap_excluded:
        failures.append("TRAP NOT LISTED in the excluded-data-errors section")
    else:
        passes.append("Fat-finger trap (Brand Events revenue 2025-11) correctly excluded as a data error, not narrated")

    print("=== Variance Agent Validation ===\n")
    print(f"Ground truth: {len(anomaly_months)} anomaly months across "
          f"{len(signal_notes)} anomalies; {len(noise_notes)} noise notes")
    print(f"Report: {len(material)} material rows, {len(excluded)} excluded data error(s)")
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
