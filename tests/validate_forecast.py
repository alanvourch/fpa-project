"""Validation script for the Forecast Agent.

Same pattern as the Phase 3/4 validators: the agent must never read
data/ground_truth.md; this script reads it after the fact and checks the
agent's outputs (output/forecast.csv, output/forecast_report.md) against it:

  1. The fat-finger trap is normalized in the history audit trail (data-error
     reason) and its value actually replaced — it must never touch a trend.
  2. Every ground-truth ONE-OFF anomaly month (isolated month) is normalized
     out of the history.
  3. Every ground-truth EPISODE month is handled with an explicit decision —
     here both episodes ended before the cutoff, so they must be normalized,
     with their evidence notes cited in the audit trail.
  4. No forecast is based on a raw anomaly month (base_was_normalized must be
     set wherever the base month is a ground-truth anomaly for that series).
  5. The FX dip is not re-forecast: Digital/Influence revenue for cutoff+3
     must exceed the raw FX-depressed actual of its base month.
  6. The concluded savings programme is not extrapolated: the Corporate
     Events marketing-opex forecast must sit above the raw deep-savings
     prior-year actuals.
  7. Structural sanity: 84 rows (28 series x 3 months), correct horizon,
     positive values, growth factors in a plausible band.

Run: .venv/Scripts/python.exe tests/validate_forecast.py
"""

import re
import sys

import pandas as pd

GROUND_TRUTH_PATH = "data/ground_truth.md"
FORECAST_PATH = "output/forecast.csv"
REPORT_PATH = "output/forecast_report.md"
VARIANCE_TABLE_PATH = "output/variance_table.csv"

COLUMN_PHRASE_MAP = [
    (re.compile(r"COGS actual", re.I), "cogs_actual"),
    (re.compile(r"Revenue actual", re.I), "revenue_actual"),
    (re.compile(r"IT opex actual", re.I), "opex_it_actual"),
    (re.compile(r"Marketing opex actual", re.I), "opex_marketing_actual"),
]
COLUMN_TO_LINE = {
    "cogs_actual": "COGS",
    "revenue_actual": "Revenue",
    "opex_it_actual": "Opex - IT",
    "opex_marketing_actual": "Opex - Marketing",
}
GROWTH_BAND = (0.7, 1.4)


def parse_ground_truth(path):
    text = open(path, encoding="utf-8").read()
    business_section = text.split("## 2. Data quality issues", 1)[0]

    anomalies = []
    for line in business_section.splitlines():
        m = re.match(r"- \*\*([\w\-&/ ]+) / (\d{4}-\d{2})\*\* — (.+)", line)
        if not m:
            continue
        bu, month, rest = m.groups()
        column = next((col for pat, col in COLUMN_PHRASE_MAP if pat.search(rest)), None)
        anomalies.append({"business_unit": bu.strip(), "month": month,
                          "line_item": COLUMN_TO_LINE.get(column)})

    # Classify: contiguous months within one BU/line = episode, isolated = one-off
    singles, episode_months = [], []
    df = pd.DataFrame(anomalies)
    for (bu, line), g in df.groupby(["business_unit", "line_item"]):
        months = sorted(pd.Period(m, "M") for m in g["month"])
        for i, m in enumerate(months):
            neighbors = (i > 0 and (m - months[i - 1]).n == 1) or (
                i < len(months) - 1 and (months[i + 1] - m).n == 1)
            rec = {"business_unit": bu, "line_item": line, "month": str(m)}
            (episode_months if neighbors else singles).append(rec)
    return singles, episode_months


def parse_adjustments(report_text):
    section = report_text.split("## History adjustments", 1)[1]
    section = section.split("## Forecast by BU", 1)[0]
    rows = []
    table_lines = [l for l in section.splitlines() if l.startswith("|")]
    for line in table_lines[2:]:
        cells = [c.strip() for c in line.strip("|").split("|")]
        rows.append({
            "business_unit": cells[0], "line_item": cells[1], "month": cells[2],
            "raw": cells[3], "used": cells[4], "reason": cells[5],
            "evidence": cells[6],
        })
    return rows


def money_to_float(s):
    return float(re.sub(r"[^\d.]", "", s))


def main():
    singles, episode_months = parse_ground_truth(GROUND_TRUTH_PATH)
    report_text = open(REPORT_PATH, encoding="utf-8").read()
    adjustments = parse_adjustments(report_text)
    fc = pd.read_csv(FORECAST_PATH)
    var = pd.read_csv(VARIANCE_TABLE_PATH)

    adj_index = {(a["business_unit"], a["line_item"], a["month"]): a for a in adjustments}
    failures, passes = [], []

    # 1. Trap normalized with a data-error reason and value actually replaced
    trap = adj_index.get(("Brand Events", "Revenue", "2025-11"))
    if trap and "data entry error" in trap["reason"]:
        if money_to_float(trap["used"]) < 0.25 * money_to_float(trap["raw"]):
            passes.append("Fat-finger trap normalized out of the history (data-error reason, value replaced)")
        else:
            failures.append("TRAP: listed as data error but the used value was not actually replaced")
    else:
        failures.append("TRAP: Brand Events revenue 2025-11 missing from the audit trail (or wrong reason)")

    # 2. Ground-truth one-off months normalized
    missing_singles = [
        (s["business_unit"], s["line_item"], s["month"]) for s in singles
        if (s["business_unit"], s["line_item"], s["month"]) not in adj_index
        or "one-off" not in adj_index[(s["business_unit"], s["line_item"], s["month"])]["reason"]
    ]
    if missing_singles:
        failures.append(f"ONE-OFF(S) NOT NORMALIZED: {missing_singles}")
    else:
        passes.append(f"All {len(singles)} ground-truth one-off anomaly months normalized out of the history")

    # 3. Episode months normalized (both ground-truth episodes ended before the
    #    cutoff) with their evidence cited
    missing_episodes, uncited = [], []
    for e in episode_months:
        key = (e["business_unit"], e["line_item"], e["month"])
        a = adj_index.get(key)
        if not a or "episode" not in a["reason"]:
            missing_episodes.append(key)
        elif not re.search(r"N\d+", a["evidence"]):
            uncited.append(key)
    if missing_episodes:
        failures.append(f"EPISODE MONTH(S) WITHOUT AN EXPLICIT DECISION: {missing_episodes}")
    else:
        passes.append(f"All {len(episode_months)} ground-truth episode months handled with an explicit concluded-episode decision")
    if uncited:
        failures.append(f"EPISODE decisions missing their evidence citation: {uncited}")
    else:
        passes.append("Episode decisions cite their evidence notes in the audit trail")

    # 4. No forecast is based on a raw anomaly month
    truth_keys = {(x["business_unit"], x["line_item"], x["month"])
                  for x in singles + episode_months}
    leaks = [
        (r["business_unit"], r["line_item"], r["base_month"])
        for _, r in fc.iterrows()
        if (r["business_unit"], r["line_item"], r["base_month"]) in truth_keys
        and not r["base_was_normalized"]
    ]
    if leaks:
        failures.append(f"RAW ANOMALY MONTH(S) USED AS FORECAST BASE: {leaks}")
    else:
        n_anomaly_bases = sum(
            1 for _, r in fc.iterrows()
            if (r["business_unit"], r["line_item"], r["base_month"]) in truth_keys)
        passes.append(f"No raw anomaly month used as a forecast base ({n_anomaly_bases} anomaly base month(s), all normalized)")

    # 5. FX dip not re-forecast
    fx_truth = [s for s in singles if s["line_item"] == "Revenue"]
    for s in fx_truth:
        base_raw = var[(var["business_unit"] == s["business_unit"])
                       & (var["line_item"] == "Revenue")
                       & (var["month"] == s["month"])]["actual"].iloc[0]
        fc_month = str(pd.Period(s["month"], "M") + 12)
        fc_row = fc[(fc["business_unit"] == s["business_unit"])
                    & (fc["line_item"] == "Revenue") & (fc["month"] == fc_month)]
        if fc_row.empty:
            continue  # anomaly base outside the forecast horizon
        if fc_row["forecast"].iloc[0] > base_raw:
            passes.append(
                f"FX one-off not re-forecast: {s['business_unit']} revenue {fc_month} "
                f"({fc_row['forecast'].iloc[0]:,.0f}) sits above the raw dip ({base_raw:,.0f})")
        else:
            failures.append(f"FX DIP CARRIED FORWARD into {fc_month}")

    # 6. Concluded savings programme not extrapolated
    ep_bu_lines = {(e["business_unit"], e["line_item"]) for e in episode_months}
    for bu, line in sorted(ep_bu_lines):
        base_months = [str(pd.Period(m, "M") - 12) for m in fc[
            (fc["business_unit"] == bu) & (fc["line_item"] == line)]["month"]]
        raw_py = var[(var["business_unit"] == bu) & (var["line_item"] == line)
                     & (var["month"].isin(base_months))]["actual"].sum()
        fc_total = fc[(fc["business_unit"] == bu)
                      & (fc["line_item"] == line)]["forecast"].sum()
        ep_months_in_base = [m for m in base_months
                             if (bu, line, m) in truth_keys]
        if not ep_months_in_base:
            continue  # this episode doesn't touch the forecast base window
        if fc_total > raw_py:
            passes.append(
                f"Concluded episode not extrapolated: {bu}/{line} 3-mo forecast "
                f"({fc_total:,.0f}) back above the raw episode-period actuals ({raw_py:,.0f})")
        else:
            failures.append(f"CONCLUDED EPISODE EXTRAPOLATED: {bu}/{line} forecast still at episode level")

    # 7. Structural sanity
    problems = []
    if len(fc) != 84:
        problems.append(f"expected 84 forecast rows, got {len(fc)}")
    if sorted(fc["month"].unique()) != ["2026-07", "2026-08", "2026-09"]:
        problems.append(f"unexpected horizon months: {sorted(fc['month'].unique())}")
    if (fc["forecast"] <= 0).any() or fc["forecast"].isna().any():
        problems.append("non-positive or missing forecast values")
    lo, hi = GROWTH_BAND
    bad_growth = fc[(fc["growth_factor"] < lo) | (fc["growth_factor"] > hi)]
    if len(bad_growth):
        problems.append(
            "growth factors outside plausible band: "
            + str(bad_growth[["business_unit", "line_item", "growth_factor"]].drop_duplicates().values.tolist()))
    if problems:
        failures.extend(f"STRUCTURAL: {p}" for p in problems)
    else:
        passes.append(f"Structural checks pass (84 rows, horizon 2026-07..09, positive values, growth within [{lo}, {hi}])")

    print("=== Forecast Agent Validation ===\n")
    print(f"Ground truth: {len(singles)} one-off month(s), {len(episode_months)} episode month(s) + 1 data entry trap")
    print(f"Forecast: {len(fc)} rows; audit trail: {len(adjustments)} adjustment entries")
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
