"""Validation script for the Data Ingestion Agent.

This is deliberately kept separate from agents/ingestion_agent.py: the agent
must never read data/ground_truth.md, but this script's entire job is to read
it and check the agent's already-written outputs (data/eventco_monthly_cleaned.csv
and output/data_quality_report.md) against it after the fact.

Run: .venv/Scripts/python.exe tests/validate_ingestion.py
"""

import re
import sys

import pandas as pd

GROUND_TRUTH_PATH = "data/ground_truth.md"
REPORT_PATH = "output/data_quality_report.md"
CLEANED_PATH = "data/eventco_monthly_cleaned.csv"

CANONICAL_BUS = {"Brand Events", "Corporate Events", "Digital/Influence", "Government & Institutions"}
NUMERIC_COLUMNS = [
    "revenue_budget", "revenue_actual", "revenue_prior_year",
    "cogs_budget", "cogs_actual", "payroll_budget", "payroll_actual",
    "opex_travel_budget", "opex_travel_actual",
    "opex_marketing_budget", "opex_marketing_actual",
    "opex_it_budget", "opex_it_actual",
    "opex_facilities_budget", "opex_facilities_actual",
]

COLUMN_PHRASE_MAP = [
    (re.compile(r"COGS actual", re.I), "cogs_actual"),
    (re.compile(r"Revenue actual", re.I), "revenue_actual"),
    (re.compile(r"IT opex actual", re.I), "opex_it_actual"),
    (re.compile(r"Marketing opex actual", re.I), "opex_marketing_actual"),
]


def parse_ground_truth(path):
    text = open(path, encoding="utf-8").read()
    business_section, rest = text.split("## 2. Data quality issues", 1)

    anomalies = []
    for line in business_section.splitlines():
        m = re.match(r"- \*\*([\w\-&/ ]+) / (\d{4}-\d{2})\*\* — (.+)", line)
        if not m:
            continue
        bu, month, rest_of_line = m.groups()
        column = next((col for pat, col in COLUMN_PHRASE_MAP if pat.search(rest_of_line)), None)
        anomalies.append({"business_unit": bu.strip(), "month": month, "column": column})

    trap_match = re.search(
        r"\*\*DATA ENTRY TRAP — ([\w\-&/ ]+) / (\d{4}-\d{2}) / (\w+)\*\*: recorded as EUR([\d,]+).*?"
        r"True value is EUR([\d,]+)",
        rest, re.S,
    )
    if not trap_match:
        raise ValueError("Could not find the data entry trap in ground_truth.md")
    bu, month, column, recorded, true_value = trap_match.groups()
    trap = {
        "business_unit": bu.strip(), "month": month, "column": column,
        "recorded_value": float(recorded.replace(",", "")),
        "true_value": float(true_value.replace(",", "")),
    }
    return anomalies, trap


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

    errors_section = get_section(
        text, "## 6. Flagged values: likely data entry errors",
        "## 7. Flagged values: notable variances",
    )
    notable_section = get_section(text, "## 7. Flagged values: notable variances")

    def rows_to_keys(rows):
        # table columns: Month | Business Unit | Column | Actual | Budget | Ratio...
        return {(r[1], r[0], r[2]) for r in rows}

    data_errors = rows_to_keys(extract_table_rows(errors_section))
    notable_variances = rows_to_keys(extract_table_rows(notable_section))
    return data_errors, notable_variances


def check_cleaned_csv(path):
    problems = []
    df = pd.read_csv(path)

    bad_bus = set(df["business_unit"].unique()) - CANONICAL_BUS
    if bad_bus:
        problems.append(f"Non-canonical BU names still present: {bad_bus}")

    dup_mask = df.duplicated(subset=["month", "business_unit"], keep=False)
    if dup_mask.any():
        problems.append(f"{dup_mask.sum()} duplicate (month, business_unit) rows remain")

    date_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}$")
    bad_dates = [m for m in df["month"] if not date_pattern.match(str(m))]
    if bad_dates:
        problems.append(f"{len(bad_dates)} month values not in canonical YYYY-MM-DD format: {bad_dates[:5]}")

    for col in NUMERIC_COLUMNS:
        non_numeric = pd.to_numeric(df[col], errors="coerce").isna() & df[col].notna()
        if non_numeric.any():
            problems.append(f"Column {col} has {non_numeric.sum()} non-numeric residual value(s)")

    opex_cols = [c for c in NUMERIC_COLUMNS if c.startswith("opex_")]
    missing = df[opex_cols].isna().sum()
    still_missing = missing[missing > 0]
    if len(still_missing):
        problems.append(f"Opex columns still have missing values: {still_missing.to_dict()}")

    return problems, df


def main():
    anomalies, trap = parse_ground_truth(GROUND_TRUTH_PATH)
    data_errors, notable_variances = parse_report(REPORT_PATH)
    csv_problems, df = check_cleaned_csv(CLEANED_PATH)

    failures, passes = [], []

    trap_key = (trap["business_unit"], trap["month"], trap["column"])
    if trap_key in data_errors:
        passes.append(f"Fat-finger trap correctly flagged as a likely data error: {trap_key}")
    else:
        failures.append(f"MISS: fat-finger trap {trap_key} was NOT flagged as a likely data error")

    false_positives = []
    for a in anomalies:
        key = (a["business_unit"], a["month"], a["column"])
        if key in data_errors:
            false_positives.append(key)
    if false_positives:
        failures.append(f"FALSE POSITIVE(S): real business anomalies misclassified as data errors: {false_positives}")
    else:
        passes.append(f"None of the {len(anomalies)} real business anomalies were misclassified as data errors")

    anomalies_seen_as_notable = [
        (a["business_unit"], a["month"], a["column"]) for a in anomalies
        if (a["business_unit"], a["month"], a["column"]) in notable_variances
    ]
    passes.append(
        f"{len(anomalies_seen_as_notable)}/{len(anomalies)} real anomalies also surfaced as informational "
        f"'notable variance' flags (bonus signal, not required): {anomalies_seen_as_notable}"
    )

    if csv_problems:
        failures.extend(f"CLEANED CSV ISSUE: {p}" for p in csv_problems)
    else:
        passes.append("Cleaned CSV passes all structural checks (BU names, dedup, dates, numeric, no missing opex)")

    print("=== Ingestion Agent Validation ===\n")
    print(f"Ground truth: {len(anomalies)} business anomalies + 1 data entry trap")
    print(f"Report: {len(data_errors)} flagged as data errors, {len(notable_variances)} flagged as notable variances")
    print()
    for p in passes:
        print(f"  PASS - {p}")
    for f in failures:
        print(f"  FAIL - {f}")

    print()
    if failures:
        print(f"RESULT: {len(failures)} failure(s) found.")
        sys.exit(1)
    else:
        print("RESULT: all checks passed.")
        sys.exit(0)


if __name__ == "__main__":
    main()
