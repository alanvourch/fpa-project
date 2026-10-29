"""Source-preserving reporting scenarios. Estimates are never accounting corrections."""

import json
from pathlib import Path

import pandas as pd

POLICY_PATH = Path("data/reporting_policy.json")


def provisional_scenario(source, enabled=False):
    """Return a separate scenario, with causal estimates and an explicit cell ledger.

    A missing cell uses only earlier observed values in its own series. The
    source dataframe is unchanged. Ratio flags alone never replace a value.
    """
    result = source.sort_values(["business_unit", "month"]).copy()
    ledger = []
    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    for column in source.columns:
        if column in ("month", "business_unit"):
            continue
        previous = result.groupby("business_unit")[column].ffill()
        for idx in result.index[result[column].isna()]:
            row = result.loc[idx]
            value = previous.loc[idx]
            method = "previous observed month only"
            if enabled and pd.isna(value) and column.endswith("_actual"):
                value = row[column.removesuffix("_actual") + "_budget"]
                method = "opening actual has no earlier observation; same-month budget placeholder"
            if not enabled or pd.isna(value):
                raise ValueError(f"Missing source cell: {row['business_unit']}/{row['month']}/{column}. "
                                 "Restore an approved source value or use --provisional for a labelled demo scenario.")
            result.loc[idx, column] = value
            ledger.append(dict(month=f"{row['month']:%Y-%m}", business_unit=row['business_unit'],
                               column=column, source_value=None, scenario_value=round(float(value), 2),
                               method=method, approval="unapproved demonstration estimate"))
    for cell in policy["placeholders"]:
        mask = ((result["business_unit"] == cell["business_unit"])
                & (result["month"].dt.strftime("%Y-%m") == cell["month"]))
        if mask.sum() != 1:
            raise ValueError(f"Placeholder does not select exactly one source row: {cell}")
        idx = result.index[mask][0]
        raw = result.at[idx, cell["column"]]
        if not enabled:
            raise ValueError("An unresolved source-verification item requires --provisional or an approved source correction.")
        if raw != cell["expected_source_value"]:
            raise ValueError("Source-verification value changed; review reporting_policy.json before reusing a placeholder.")
        value = result.at[idx, cell["budget_column"]]
        result.at[idx, cell["column"]] = value
        ledger.append(dict(month=cell['month'], business_unit=cell['business_unit'], column=cell['column'],
                           source_value=float(raw), scenario_value=float(value), method="budget placeholder pending source verification",
                           approval="unapproved demonstration assumption"))
    return result, ledger


def load_reporting_table(path="output/variance_table.csv"):
    """Expose scenario columns to calculations while retaining source columns."""
    table = pd.read_csv(path)
    for name in ("actual", "budget"):
        table[f"source_{name}"] = table[name]
        table[name] = table[f"provisional_{name}"]
    return table
