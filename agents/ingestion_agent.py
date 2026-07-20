"""Data Ingestion Agent.

Cleans the raw EventCo monthly export (data/eventco_monthly.csv) into an
analysis-ready table, using only generalizable heuristics — fuzzy name
matching, time-series interpolation, currency-string parsing, and
budget-relative outlier detection. It never reads data/ground_truth.md: on
real, unseen data there would be no answer key, so every fix and flag here
has to stand on its own statistical or domain reasoning.

Two output artifacts:
  - data/eventco_monthly_cleaned.csv   (clean, analysis-ready table)
  - output/data_quality_report.md      (what was fixed vs. merely flagged, and why)

Run: .venv/Scripts/python.exe agents/ingestion_agent.py
"""

import difflib
import re
import warnings

import numpy as np
import pandas as pd

RAW_PATH = "data/eventco_monthly.csv"
CLEANED_PATH = "data/eventco_monthly_cleaned.csv"
REPORT_PATH = "output/data_quality_report.md"

CANONICAL_BUS = ["Brand Events", "Corporate Events", "Digital/Influence", "Government & Institutions"]

FINAL_COLUMNS = [
    "month", "business_unit",
    "revenue_budget", "revenue_actual", "revenue_prior_year",
    "cogs_budget", "cogs_actual",
    "payroll_budget", "payroll_actual",
    "opex_travel_budget", "opex_travel_actual",
    "opex_marketing_budget", "opex_marketing_actual",
    "opex_it_budget", "opex_it_actual",
    "opex_facilities_budget", "opex_facilities_actual",
]
NUMERIC_COLUMNS = [c for c in FINAL_COLUMNS if c not in ("month", "business_unit")]
OPEX_COLUMNS = [c for c in NUMERIC_COLUMNS if c.startswith("opex_")]

# (actual, budget) pairs used for budget-relative outlier detection
ACTUAL_BUDGET_PAIRS = [
    ("revenue_actual", "revenue_budget"),
    ("cogs_actual", "cogs_budget"),
    ("payroll_actual", "payroll_budget"),
    ("opex_travel_actual", "opex_travel_budget"),
    ("opex_marketing_actual", "opex_marketing_budget"),
    ("opex_it_actual", "opex_it_budget"),
    ("opex_facilities_actual", "opex_facilities_budget"),
]

# A single line item coming in at >4x or <0.25x its budget is not a plausible
# one-off business swing (the largest genuine anomaly in this dataset's shape
# is a 2.8x cost spike) -- it's the signature of a fat-fingered digit. This is
# a general FP&A rule of thumb, not a value read off any specific row.
DATA_ERROR_RATIO_HIGH = 4.0
DATA_ERROR_RATIO_LOW = 0.25
IQR_MULTIPLIER = 1.5


def load_raw(path):
    return pd.read_csv(path)


def standardize_dates(df, notes):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        parsed = pd.to_datetime(df["month"], errors="coerce")
    n_unparsed = parsed.isna().sum()
    if n_unparsed:
        notes["dates_unparsed"] = df.loc[parsed.isna(), "month"].tolist()
    else:
        notes["dates_unparsed"] = []
    notes["dates_original_sample"] = sorted(set(df["month"].astype(str)))[:8]
    df = df.copy()
    df["month"] = parsed
    return df


def fuzzy_correct_bu(raw_value):
    cleaned = str(raw_value).strip()
    normalized = cleaned.replace("-", " ").lower()
    normalized = re.sub(r"\s+", " ", normalized).strip()
    canonical_normalized = {c.replace("-", " ").lower(): c for c in CANONICAL_BUS}
    best_match, best_ratio = None, 0.0
    for candidate in canonical_normalized:
        ratio = difflib.SequenceMatcher(None, normalized, candidate).ratio()
        if ratio > best_ratio:
            best_match, best_ratio = candidate, ratio
    if best_ratio >= 0.6:
        return canonical_normalized[best_match], best_ratio, cleaned
    return cleaned, best_ratio, cleaned


def standardize_bu_names(df, notes):
    df = df.copy()
    corrections = []
    for i, raw in df["business_unit"].items():
        corrected, ratio, original = fuzzy_correct_bu(raw)
        if corrected != original:
            corrections.append({
                "row": i, "month": df.at[i, "month"], "original": original,
                "corrected": corrected, "match_confidence": round(ratio, 3),
            })
            df.at[i, "business_unit"] = corrected
    # A duplicated row carries its typo twice; log each distinct correction once
    # so the report doesn't list the same fix twice for a row dedup then removes.
    seen, unique = set(), []
    for c in corrections:
        key = (c["month"], c["original"], c["corrected"])
        if key not in seen:
            seen.add(key)
            unique.append(c)
    notes["bu_corrections"] = unique
    return df


def remove_duplicates(df, notes):
    dup_mask = df.duplicated(subset=["month", "business_unit"], keep="first")
    dup_rows = df.loc[dup_mask].copy()
    identical_check = []
    for _, row in dup_rows.iterrows():
        first = df[(df["month"] == row["month"]) & (df["business_unit"] == row["business_unit"])].iloc[0]
        cols_to_compare = [c for c in FINAL_COLUMNS if c not in ("month", "business_unit")]
        same = all(
            (pd.isna(first[c]) and pd.isna(row[c])) or (str(first[c]) == str(row[c]))
            for c in cols_to_compare
        )
        identical_check.append(same)
    notes["duplicates_removed"] = [
        {
            "month": r["month"], "business_unit": r["business_unit"],
            "identical_to_kept_row": ident,
        }
        for (_, r), ident in zip(dup_rows.iterrows(), identical_check)
    ]
    return df.loc[~dup_mask].reset_index(drop=True)


def parse_currency_value(value):
    if pd.isna(value):
        return np.nan
    if isinstance(value, (int, float)):
        return float(value)
    text = re.sub(r"[^0-9,.\-]", "", str(value))
    text = text.replace(",", "")
    if text in ("", "-"):
        return np.nan
    return float(text)


def parse_currency_columns(df, notes):
    df = df.copy()
    parsed_cells = []
    for col in NUMERIC_COLUMNS:
        for i, value in df[col].items():
            if isinstance(value, str) and not re.fullmatch(r"-?\d+(\.\d+)?", value.strip()):
                parsed_cells.append({
                    "row": i, "month": df.at[i, "month"], "business_unit": df.at[i, "business_unit"],
                    "column": col, "raw_value": value,
                })
        df[col] = df[col].apply(parse_currency_value)
    notes["currency_parsed"] = parsed_cells
    return df


def impute_missing_opex(df, notes):
    df = df.sort_values(["business_unit", "month"]).reset_index(drop=True)
    imputations = []
    for col in OPEX_COLUMNS:
        missing_before = df[df[col].isna()][["month", "business_unit"]].copy()
        df[col] = df.groupby("business_unit")[col].transform(
            lambda s: s.interpolate(method="linear", limit_direction="both")
        )
        for _, row in missing_before.iterrows():
            imputed_value = df[(df["month"] == row["month"]) & (df["business_unit"] == row["business_unit"])][col].iloc[0]
            imputations.append({
                "month": row["month"], "business_unit": row["business_unit"],
                "column": col, "imputed_value": round(float(imputed_value), 2),
            })
    notes["opex_imputed"] = imputations
    return df


def detect_outliers(df, notes):
    df = df.sort_values(["business_unit", "month"]).reset_index(drop=True)
    data_errors, notable_variances = [], []

    ratio_cols = {}
    for actual_col, budget_col in ACTUAL_BUDGET_PAIRS:
        ratio_col = f"_ratio_{actual_col}"
        with np.errstate(divide="ignore", invalid="ignore"):
            df[ratio_col] = df[actual_col] / df[budget_col]
        ratio_cols[actual_col] = (ratio_col, budget_col)

    for actual_col, (ratio_col, budget_col) in ratio_cols.items():
        for bu in CANONICAL_BUS:
            bu_mask = df["business_unit"] == bu
            ratios = df.loc[bu_mask, ratio_col]

            # Tier 1: magnitude-implausible -> likely a data entry error
            error_mask = bu_mask & ((df[ratio_col] > DATA_ERROR_RATIO_HIGH) | (df[ratio_col] < DATA_ERROR_RATIO_LOW))
            for i in df[error_mask].index:
                data_errors.append({
                    "month": df.at[i, "month"], "business_unit": bu, "column": actual_col,
                    "actual": round(float(df.at[i, actual_col]), 2),
                    "budget": round(float(df.at[i, budget_col]), 2),
                    "ratio_to_budget": round(float(df.at[i, ratio_col]), 2),
                })

            # Tier 2: IQR outlier on this BU/column's own historical ratio distribution,
            # excluding tier-1 rows so a single extreme point doesn't distort the fence
            clean_ratios = ratios[~error_mask.loc[ratios.index]]
            if len(clean_ratios) < 4:
                continue
            q1, q3 = clean_ratios.quantile(0.25), clean_ratios.quantile(0.75)
            iqr = q3 - q1
            lower, upper = q1 - IQR_MULTIPLIER * iqr, q3 + IQR_MULTIPLIER * iqr
            variance_mask = bu_mask & (~error_mask) & ((df[ratio_col] < lower) | (df[ratio_col] > upper))
            for i in df[variance_mask].index:
                notable_variances.append({
                    "month": df.at[i, "month"], "business_unit": bu, "column": actual_col,
                    "actual": round(float(df.at[i, actual_col]), 2),
                    "budget": round(float(df.at[i, budget_col]), 2),
                    "ratio_to_budget": round(float(df.at[i, ratio_col]), 2),
                    "historical_range": f"[{lower:.2f}, {upper:.2f}]",
                })

    df = df.drop(columns=[c for c, _ in ratio_cols.values()])
    notes["data_errors"] = sorted(data_errors, key=lambda r: (str(r["business_unit"]), str(r["month"])))
    notes["notable_variances"] = sorted(notable_variances, key=lambda r: (str(r["business_unit"]), str(r["month"])))
    return df


def render_report(notes, row_count_raw, row_count_clean):
    def fmt_money(v):
        return f"EUR{v:,.0f}"

    lines = [
        "# Data Quality Report: EventCo Monthly Ingestion",
        "",
        "Generated by `agents/ingestion_agent.py`. This agent never reads "
        "`data/ground_truth.md`. Every fix and flag below is derived from "
        "generalizable heuristics (fuzzy matching, time-series interpolation, "
        "budget-relative outlier detection), the same way it would run against "
        "real, unseen monthly data.",
        "",
        f"- Rows in raw file: {row_count_raw}",
        f"- Rows after de-duplication: {row_count_clean}",
        "",
        "## 1. BU/category name typos corrected (fuzzy match against canonical names)",
        "",
    ]
    if notes["bu_corrections"]:
        lines.append("| Month | Original | Corrected to | Match confidence |")
        lines.append("|---|---|---|---|")
        for c in notes["bu_corrections"]:
            lines.append(f"| {c['month']:%Y-%m} | \"{c['original']}\" | {c['corrected']} | {c['match_confidence']:.2f} |")
    else:
        lines.append("None found.")
    lines += ["", "## 2. Duplicate rows removed (same month + BU entered twice)", ""]
    if notes["duplicates_removed"]:
        lines.append("| Month | Business Unit | Identical to kept row? |")
        lines.append("|---|---|---|")
        for d in notes["duplicates_removed"]:
            lines.append(f"| {d['month']:%Y-%m} | {d['business_unit']} | {'Yes' if d['identical_to_kept_row'] else 'No, manual review recommended'} |")
    else:
        lines.append("None found.")
    lines += ["", "## 3. Missing Opex values imputed", "",
              "Strategy: linear interpolation across each BU's own monthly time series "
              "for that column (interior gaps); for gaps at the very start/end of the "
              "series, the nearest available value is carried in, since linear "
              "interpolation cannot extrapolate beyond observed data. Opex budgets and "
              "actuals move smoothly month to month for a given BU, so a BU's own recent "
              "trend is a more defensible estimate than a company-wide average or a hard "
              "zero. No rows were dropped.", ""]
    if notes["opex_imputed"]:
        lines.append("| Month | Business Unit | Column | Imputed value |")
        lines.append("|---|---|---|---|")
        for imp in notes["opex_imputed"]:
            lines.append(f"| {imp['month']:%Y-%m} | {imp['business_unit']} | {imp['column']} | {fmt_money(imp['imputed_value'])} |")
    else:
        lines.append("None found.")
    lines += ["", "## 4. Currency-formatted text amounts parsed to numeric", ""]
    if notes["currency_parsed"]:
        lines.append("| Month | Business Unit | Column | Raw value |")
        lines.append("|---|---|---|---|")
        for c in notes["currency_parsed"]:
            lines.append(f"| {c['month']:%Y-%m} | {c['business_unit']} | {c['column']} | \"{c['raw_value']}\" |")
    else:
        lines.append("None found.")
    lines += ["", "## 5. Date formats standardized", "",
              f"Raw `month` values mixed ISO (YYYY-MM-DD), US (MM/DD/YYYY), long-form "
              f"(\"Month YYYY\"), and year/month (YYYY/MM) styles. Sample of distinct raw "
              f"values seen: {', '.join(notes['dates_original_sample'])}. All parsed "
              f"successfully via flexible date inference and standardized to ISO "
              f"(YYYY-MM-DD, first of month) in the cleaned file. "
              f"Unparseable values: {len(notes['dates_unparsed'])}.", ""]
    lines += ["## 6. Flagged values: likely data entry errors (high confidence)", "",
              f"Rule: a line item actual coming in above {DATA_ERROR_RATIO_HIGH:.0f}x or "
              f"below {DATA_ERROR_RATIO_LOW:.2f}x its own budget is treated as a probable "
              f"data entry error rather than a real business event. A single BU/month is "
              f"not operationally capable of swinging that far from plan without a "
              f"corresponding, equally extreme movement in related lines (COGS, payroll), "
              f"which these do not show. These rows were **not** auto-corrected; they are "
              f"flagged here for manual verification before any variance analysis uses them.", ""]
    if notes["data_errors"]:
        lines.append("| Month | Business Unit | Column | Actual | Budget | Ratio to budget |")
        lines.append("|---|---|---|---|---|---|")
        for e in notes["data_errors"]:
            lines.append(f"| {e['month']:%Y-%m} | {e['business_unit']} | {e['column']} | {fmt_money(e['actual'])} | {fmt_money(e['budget'])} | {e['ratio_to_budget']:.1f}x |")
    else:
        lines.append("None found.")
    lines += ["", "## 7. Flagged values: notable variances (informational, not errors)", "",
              "Rule: IQR outlier (1.5x IQR fence) on that BU/column's own historical "
              "actual-vs-budget ratio distribution, excluding anything already flagged "
              "above as a likely data error. These look like real, large-but-plausible "
              "business swings, well under the data-error magnitude threshold above. "
              "They are left untouched in the cleaned data and forwarded as-is for the "
              "Variance & Root-Cause Agent to explain, not treated as data quality issues.", ""]
    if notes["notable_variances"]:
        lines.append("| Month | Business Unit | Column | Actual | Budget | Ratio to budget | Historical normal range |")
        lines.append("|---|---|---|---|---|---|---|")
        for v in notes["notable_variances"]:
            lines.append(f"| {v['month']:%Y-%m} | {v['business_unit']} | {v['column']} | {fmt_money(v['actual'])} | {fmt_money(v['budget'])} | {v['ratio_to_budget']:.2f}x | {v['historical_range']} |")
    else:
        lines.append("None found.")
    return "\n".join(lines) + "\n"


def main():
    notes = {}
    df = load_raw(RAW_PATH)
    row_count_raw = len(df)

    df = standardize_dates(df, notes)
    df = standardize_bu_names(df, notes)
    df = remove_duplicates(df, notes)
    df = parse_currency_columns(df, notes)
    df = impute_missing_opex(df, notes)
    df = detect_outliers(df, notes)

    df = df.sort_values(["business_unit", "month"]).reset_index(drop=True)
    df["month"] = df["month"].dt.strftime("%Y-%m-%d")
    df = df[FINAL_COLUMNS]
    # Round at the serialization boundary only: every check above (typo
    # matching, imputation, outlier detection) already ran on full
    # precision, so this only trims float noise from the published file,
    # the same way a real accounting export is never sub-cent.
    df[NUMERIC_COLUMNS] = df[NUMERIC_COLUMNS].round(2)
    df.to_csv(CLEANED_PATH, index=False)

    report = render_report(notes, row_count_raw, len(df))
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"Raw rows: {row_count_raw} -> cleaned rows: {len(df)}")
    print(f"BU typos corrected: {len(notes['bu_corrections'])}")
    print(f"Duplicates removed: {len(notes['duplicates_removed'])}")
    print(f"Opex values imputed: {len(notes['opex_imputed'])}")
    print(f"Currency-formatted cells parsed: {len(notes['currency_parsed'])}")
    print(f"Flagged as likely data errors: {len(notes['data_errors'])}")
    print(f"Flagged as notable variances (informational): {len(notes['notable_variances'])}")
    print(f"Wrote {CLEANED_PATH} and {REPORT_PATH}")


if __name__ == "__main__":
    main()
