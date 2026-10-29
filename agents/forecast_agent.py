"""Seasonal forecasts with explicit recurrence review and retained unresolved effects."""
import json
import math
from pathlib import Path

import pandas as pd
from reporting_basis import load_reporting_table

VARIANCE_TABLE_PATH = "output/variance_table.csv"
FORECAST_PATH = "output/forecast.csv"
REPORT_PATH = "output/forecast_report.md"
HORIZON_MONTHS = 3
GROWTH_WINDOW_MONTHS = 12
LINE_ORDER = ["Net billings", "Cost of sales", "Payroll", "Social charges",
              "Bonuses and profit sharing", "Opex - Travel", "Opex - Marketing",
              "Opex - IT", "Opex - Facilities", "Opex - G&A", "Depreciation"]
COST_LINES = LINE_ORDER[1:]
CLASSIFICATIONS = {"confirmed one-off", "continuing structural effect", "timing shift", "unresolved"}


def load_variance_table():
    df = load_reporting_table(VARIANCE_TABLE_PATH)
    df["month"] = pd.to_datetime(df["month"], format="%Y-%m")
    for col in ("materiality", "evidence_notes", "analyst_comment"):
        df[col] = df[col].fillna("")
    return df.sort_values(["business_unit", "line_item", "month"]).reset_index(drop=True)


def load_reviews():
    reviews = pd.read_csv("data/forecast_reviews.csv").fillna("")
    if reviews.duplicated(["business_unit", "line_item", "month"]).any():
        raise ValueError("Duplicate forecast review keys")
    for r in reviews.to_dict("records"):
        if r["classification"] not in CLASSIFICATIONS or r["status"] not in {"proposed", "approved"}:
            raise ValueError(f"Invalid recurrence review: {r}")
        if r["status"] == "approved" and not all(r[k] for k in ("reviewer", "reviewed_at", "evidence")):
            raise ValueError("Approved adjustments require reviewer, review date and evidence")
        if r["status"] == "approved" and r["classification"] == "confirmed one-off":
            if not math.isfinite(float(r["replacement"])) or float(r["replacement"]) < 0:
                raise ValueError("Approved one-off requires an explicit non-negative replacement")
    return reviews.to_dict("records")


def normalize_history(g, cutoff, reviews=None):
    """Materiality never establishes recurrence. Only approved one-offs change history."""
    reviews = load_reviews() if reviews is None else reviews
    g = g[g["month"] <= cutoff]
    normalized, audit = g["actual"].copy(), []
    review_map = {(r["business_unit"], r["line_item"], r["month"]): r for r in reviews}
    for idx, row in g.iterrows():
        key = (row["business_unit"], row["line_item"], f"{row['month']:%Y-%m}")
        review = review_map.get(key)
        classification, status = "unresolved", "unreviewed"
        reason = "Retained: recurrence unresolved; materiality is a review trigger."
        evidence = row["evidence_notes"]
        if review:
            classification, status = review["classification"], review["status"]
            evidence = review["evidence"]
            eligible = status == "approved" and pd.Timestamp(review["reviewed_at"]) <= cutoff + pd.offsets.MonthEnd(0)
            if eligible and classification == "confirmed one-off":
                normalized.loc[idx] = float(review["replacement"])
                reason = "Approved one-off replacement; explicit analyst-reviewed value."
            else:
                reason = f"Retained: {classification}; {status}. Timing and structural effects need an explicit future schedule."
                if status == "approved" and not eligible:
                    reason = "Retained: review was not available at this historical cutoff."
        if row["suspected_data_error"]:
            reason += " Source anomaly pending verification; reporting-policy placeholder is a separate provisional assumption."
        if row["materiality"] or row["suspected_data_error"] or review:
            audit.append(dict(business_unit=row["business_unit"], line_item=row["line_item"], month=row["month"],
                              source_actual=row["source_actual"], raw_actual=row["actual"], normalized_to=normalized.loc[idx], reason=reason,
                              evidence=evidence, classification=classification, status=status))
    return normalized, audit


def predict(series, cutoff, horizon, use_growth=True):
    window = [cutoff - pd.DateOffset(months=k) for k in range(GROWTH_WINDOW_MONTHS)]
    ratios = [series[m] / series[m-pd.DateOffset(months=12)] for m in window
              if m in series.index and m-pd.DateOffset(months=12) in series.index
              and series[m-pd.DateOffset(months=12)] > 0]
    if not ratios:
        raise ValueError("Insufficient observed history for seasonal growth")
    growth = float(pd.Series(ratios).median()) if use_growth else 1.0
    return [(m, float(series[m-pd.DateOffset(months=12)]), growth) for m in horizon]


def build_forecast(df, reviews=None, cutoff=None):
    cutoff = df["month"].max() if cutoff is None else pd.Timestamp(cutoff)
    df = df[df["month"] <= cutoff].copy()
    horizon = [cutoff + pd.DateOffset(months=h) for h in range(1, HORIZON_MONTHS+1)]
    forecasts, audit, growths = [], [], []
    for (bu, line), g in df.groupby(["business_unit", "line_item"]):
        g = g.sort_values("month")
        normalized, adjustments = normalize_history(g, cutoff, reviews)
        audit.extend(adjustments)
        series = pd.Series(normalized.values, index=g["month"].values)
        raw = pd.Series(g["source_actual"].fillna(g["actual"]).values, index=g["month"].values)
        # Diagnostic only: an aggressive neutralization of ALL material months.
        # This is unapproved sensitivity, never the selected forecast.
        hypothetical = g["actual"].copy()
        good = g[(g["materiality"] == "") & (~g["suspected_data_error"])]
        typical = (good["actual"] / good["budget"]).median()
        hypothetical.loc[g["materiality"] != ""] = g.loc[g["materiality"] != "", "budget"] * typical
        hyp = pd.Series(hypothetical.values, index=g["month"].values)
        raw_fc, hyp_fc = predict(raw, cutoff, horizon), predict(hyp, cutoff, horizon)
        for i, (m, base, growth) in enumerate(predict(series, cutoff, horizon)):
            base_month = m-pd.DateOffset(months=12)
            forecasts.append(dict(month=m, business_unit=bu, line_item=line, forecast=base*growth,
                                  base_month=base_month, base_value=base,
                                  base_was_normalized=abs(base-float(g.loc[g["month"] == base_month, "actual"].iloc[0])) > 1e-9,
                                  growth_factor=growth, raw_baseline_forecast=raw_fc[i][1]*raw_fc[i][2],
                                  neutralized_sensitivity=hyp_fc[i][1]*hyp_fc[i][2]))
        growths.append(dict(business_unit=bu, line_item=line, growth=growth))
    return pd.DataFrame(forecasts), audit, pd.DataFrame(growths), cutoff, horizon


def backtest(df, reviews):
    """Four overlapping holdouts, no later data or review available to a fold."""
    records = []
    for cutoff in pd.date_range("2025-12-01", "2026-03-01", freq="MS"):
        fc, *_ = build_forecast(df, reviews=reviews, cutoff=cutoff)
        targets = df[["month", "business_unit", "line_item", "source_actual", "suspected_data_error"]]
        for r in fc.merge(targets, on=["month", "business_unit", "line_item"]).to_dict("records"):
            if pd.isna(r["source_actual"]) or r["suspected_data_error"]:
                continue
            records.append(dict(cutoff=f"{cutoff:%Y-%m}", month=f"{r['month']:%Y-%m}",
                                business_unit=r['business_unit'], line_item=r['line_item'], actual=r['source_actual'],
                                forecast=r['forecast'], absolute_error=abs(r['forecast']-r['source_actual']),
                                naive_error=abs(r['base_value']-r['source_actual'])))
    return pd.DataFrame(records)


def fmt_money(v):
    return f"-EUR{-v:,.0f}" if v < 0 else f"EUR{v:,.0f}"


def group_pnl(fc, column="forecast"):
    totals = fc.groupby("line_item")[column].sum()
    rev, cos = totals["Net billings"], totals["Cost of sales"]
    staff = totals.drop(["Net billings", "Cost of sales"]).sum()
    return [("Net billings", rev), ("Cost of sales", cos), ("Gross margin", rev-cos),
            ("Staff costs and overheads", staff), ("Operating result", rev-cos-staff)]


def render_report(fc, adjustments, cutoff, horizon, bt):
    lines = ["# Rolling forecast: Q3 2026", "", f"As of {cutoff + pd.offsets.MonthEnd(0):%d %B %Y}. Synthetic provisional reporting scenario.", "",
             "## Method", "", "Forecast = same-month-prior-year actual times median year-over-year growth over the last 12 months, by business unit and P&L line. "
             "Unresolved business effects remain in history. A single material month is not evidence of a one-off; an episode ending does not establish that a structural effect has stopped.", "",
             "Only a confirmed one-off with approved status, reviewer, date, evidence and an explicit replacement in data/forecast_reviews.csv changes history. "
             "Proposed adjustments remain proposals. Structural effects and timing shifts are retained pending an explicit future schedule. "
             "Missing source cells and the November billings placeholder follow the separate provisional reporting policy; neither is a confirmed accounting value.", "",
             "## History adjustments (full audit trail)", "", "| Business Unit | Line item | Month | Source actual | Provisional input | Used in history | Reason | Evidence |", "|---|---|---|---|---|---|---|---|"]
    for a in adjustments:
        lines.append(f"| {a['business_unit']} | {a['line_item']} | {a['month']:%Y-%m} | {fmt_money(a['source_actual']) if pd.notna(a['source_actual']) else 'missing'} | {fmt_money(a['raw_actual'])} | {fmt_money(a['normalized_to'])} | {a['reason']} | {a['evidence'] or '-'} |")
    lines += ["", "## Forecast by BU and line item", "", "Amounts in EURk, rounded. Base values are provisional prior-year observations; unresolved effects are retained.", "",
              "| Business Unit | Line item | Jul-26 | Aug-26 | Sep-26 | Q3 total |", "|---|---|---|---|---|---|"]
    for bu in sorted(fc.business_unit.unique()):
        for line in LINE_ORDER:
            g = fc[(fc.business_unit == bu) & (fc.line_item == line)].sort_values('month')
            lines.append(f"| {bu} | {line} | " + " | ".join(f"{v/1000:,.0f}" for v in g.forecast) + f" | {g.forecast.sum()/1000:,.0f} |")
    lines += ["", "## Group P&L summary (forecast)", "", "| Metric | Jul-26 | Aug-26 | Sep-26 | Q3 total |", "|---|---|---|---|---|"]
    monthly = {m: dict(group_pnl(fc[fc.month == m])) for m in horizon}
    for metric, total in group_pnl(fc):
        lines.append(f"| {metric} | " + " | ".join(fmt_money(monthly[m][metric]) for m in horizon) + f" | {fmt_money(total)} |")
    lines += ["", "## Baseline and sensitivity", "", "| Scenario | Q3 operating result |", "|---|---|"]
    for label, col in [("Raw source baseline (missing cells estimated; anomaly retained)", "raw_baseline_forecast"),
                       ("Selected provisional baseline (unresolved business effects retained)", "forecast"),
                       ("Unapproved diagnostic: neutralize every material month", "neutralized_sensitivity")]:
        lines.append(f"| {label} | {fmt_money(dict(group_pnl(fc, col))['Operating result'])} |")
    lines += ["", "The neutralized scenario is a sensitivity, not an approved forecast or a confidence interval. "
              "The August loss needs a commercial and cost review; the seasonal shape does not establish that it is acceptable.", "", "## Historical evaluation", "",
              f"Four overlapping three-month holdouts from December 2025 to March 2026; {len(bt)} comparable line-month predictions. "
              "Each fold uses only history and reviews available at its cutoff. Missing or flagged target source cells are excluded. "
              "The synthetic, short and overlapping sample does not establish performance on real employer data.", "",
              f"Mean absolute error per line-month: seasonal growth {fmt_money(bt.absolute_error.mean())}; seasonal naive {fmt_money(bt.naive_error.mean())}. "
              "A lower error is better. Detailed fold predictions are in forecast_backtest.csv.", ""]
    return "\n".join(lines)


def main():
    df, reviews = load_variance_table(), load_reviews()
    known = set(zip(df.business_unit, df.line_item, df.month.dt.strftime('%Y-%m')))
    if any((r['business_unit'], r['line_item'], r['month']) not in known for r in reviews):
        raise ValueError("Forecast review does not match a source observation")
    fc, adjustments, _, cutoff, horizon = build_forecast(df, reviews)
    bt = backtest(df, reviews)
    out = fc.copy()
    for col in ('month', 'base_month'):
        out[col] = out[col].dt.strftime('%Y-%m')
    for col in ('forecast', 'base_value', 'raw_baseline_forecast', 'neutralized_sensitivity'):
        out[col] = out[col].round(2)
    out.growth_factor = out.growth_factor.round(6)
    out.to_csv(FORECAST_PATH, index=False)
    audit = pd.DataFrame(adjustments)
    audit['month'] = audit['month'].dt.strftime('%Y-%m')
    audit.to_csv('output/forecast_adjustments.csv', index=False)
    bt.round(2).to_csv('output/forecast_backtest.csv', index=False)
    Path(REPORT_PATH).write_text(render_report(fc, adjustments, cutoff, horizon, bt), encoding='utf-8')
    print(f"Forecast: {len(fc)} rows; {len(adjustments)} recurrence decisions; {len(bt)} holdout predictions")


if __name__ == '__main__':
    main()
