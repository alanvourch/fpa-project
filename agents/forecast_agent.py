"""Forecast Agent.

Produces the rolling forecast for the next three months (N+1 to N+3 after the
last closed month) for every BU and line item, using the Variance Agent's
output table (output/variance_table.csv — cleaned actuals/budgets plus each
month's materiality classification and evidence). It never reads
data/ground_truth.md.

Method: seasonal base x robust growth.
  - Base = the same month one year earlier, from a NORMALIZED history. The
    events business is strongly seasonal and budgets/actuals both carry that
    shape, so same-month-last-year is the natural base.
  - Growth = the median year-over-year ratio (normalized actual vs. one year
    earlier) across the last 12 closed months. The median keeps any single
    distorted pair from steering the factor.

Normalization is where forecasting judgment lives — a forecast is only as
good as the history it extrapolates:
  - Suspected data errors (the ingestion agent's >4x/<0.25x rule; still
    uncorrected in the cleaned file) are replaced with budget x the line's
    typical achievement ratio. A fat-finger digit must never touch a trend.
  - One-off material months (single-month variances in the variance table:
    the FX hit, the IT incident, and unexplained outliers alike) are
    replaced the same way. One-offs, by definition, don't recur — carrying
    them into a seasonal base would re-forecast last year's accident.
  - Sustained episodes are the judgment call: a programme still running at
    the forecast cutoff SHOULD be carried into the forecast, so episode
    months are kept as-is when the episode reaches within
    EPISODE_ACTIVE_GRACE_MONTHS of the last closed month. An episode that
    ended earlier (e.g. a project overrun that closed, or a savings
    programme whose effect has since been absorbed into the baseline) is
    normalized out like a one-off, because its effect is already over.
    Every kept/normalized decision is logged with the episode's evidence
    notes, so the report shows WHY history was adjusted, not just THAT it
    was.

Outputs:
  - output/forecast.csv         (forecast grain + base/growth audit columns)
  - output/forecast_report.md   (method, every history adjustment, forecast
                                 tables, group P&L summary)

Run: .venv/Scripts/python.exe agents/forecast_agent.py
"""

import pandas as pd

VARIANCE_TABLE_PATH = "output/variance_table.csv"
FORECAST_PATH = "output/forecast.csv"
REPORT_PATH = "output/forecast_report.md"

HORIZON_MONTHS = 3
GROWTH_WINDOW_MONTHS = 12
# An episode counts as still active if its last month is within this many
# months of the last closed month — one or two quiet months at the end of a
# still-running programme shouldn't flip it to "concluded".
EPISODE_ACTIVE_GRACE_MONTHS = 2

LINE_ORDER = ["Revenue", "COGS", "Payroll", "Opex - Travel",
              "Opex - Marketing", "Opex - IT", "Opex - Facilities"]
COST_LINES = [l for l in LINE_ORDER if l != "Revenue"]


def load_variance_table():
    df = pd.read_csv(VARIANCE_TABLE_PATH)
    df["month"] = pd.to_datetime(df["month"], format="%Y-%m")
    df["materiality"] = df["materiality"].fillna("")
    df["evidence_notes"] = df["evidence_notes"].fillna("")
    return df.sort_values(["business_unit", "line_item", "month"]).reset_index(drop=True)


def normalize_history(g, cutoff):
    """Return (normalized series indexed like g, adjustment records).

    Flagged months are replaced with budget x the line's typical achievement
    ratio (median actual/budget over unflagged months) — except months of an
    episode still active at cutoff, which are deliberately kept.
    """
    unflagged = g[(g["materiality"] == "") & (~g["suspected_data_error"])]
    typical_ratio = (unflagged["actual"] / unflagged["budget"]).median()

    normalized = g["actual"].copy()
    adjustments = []

    def normalize(idx, reason):
        row = g.loc[idx]
        replacement = row["budget"] * typical_ratio
        normalized.loc[idx] = replacement
        adjustments.append({
            "business_unit": row["business_unit"], "line_item": row["line_item"],
            "month": row["month"], "raw_actual": row["actual"],
            "normalized_to": replacement, "reason": reason,
            "evidence": row["evidence_notes"],
        })

    for idx, row in g.iterrows():
        if row["suspected_data_error"]:
            normalize(idx, "suspected data entry error (>4x/<0.25x budget), "
                           "still uncorrected in the cleaned file")
        elif row["materiality"] == "single":
            normalize(idx, "one-off material variance, non-recurring by "
                           "nature, must not be extrapolated")

    # Episodes: contiguous runs of episode-flagged months per series
    ep = g[g["materiality"] == "episode"]
    if not ep.empty:
        runs, current = [], [ep.index[0]]
        for prev_i, i in zip(ep.index, ep.index[1:]):
            gap = (ep.at[i, "month"].to_period("M")
                   - ep.at[prev_i, "month"].to_period("M")).n
            if gap == 1:
                current.append(i)
            else:
                runs.append(current)
                current = [i]
        runs.append(current)
        for run in runs:
            last = g.at[run[-1], "month"]
            active = (cutoff.to_period("M") - last.to_period("M")).n <= EPISODE_ACTIVE_GRACE_MONTHS
            span = f"{g.at[run[0], 'month']:%Y-%m}..{last:%Y-%m}"
            if active:
                for idx in run:
                    row = g.loc[idx]
                    adjustments.append({
                        "business_unit": row["business_unit"], "line_item": row["line_item"],
                        "month": row["month"], "raw_actual": row["actual"],
                        "normalized_to": row["actual"],
                        "reason": f"KEPT: episode {span} still active at cutoff; "
                                  "its effect is deliberately carried into the forecast",
                        "evidence": row["evidence_notes"],
                    })
            else:
                for idx in run:
                    normalize(idx, f"part of episode {span}, concluded before "
                                   "the forecast cutoff. Its effect is over "
                                   "and must not be extrapolated")
    return normalized, adjustments


def build_forecast(df):
    cutoff = df["month"].max()
    horizon = [cutoff + pd.DateOffset(months=h) for h in range(1, HORIZON_MONTHS + 1)]

    forecasts, all_adjustments, growth_factors = [], [], []
    for (bu, line), g in df.groupby(["business_unit", "line_item"]):
        g = g.sort_values("month")
        normalized, adjustments = normalize_history(g, cutoff)
        all_adjustments.extend(adjustments)
        series = pd.Series(normalized.values, index=g["month"].values)

        window = [cutoff - pd.DateOffset(months=k) for k in range(GROWTH_WINDOW_MONTHS)]
        yoy = [series[m] / series[m - pd.DateOffset(months=12)]
               for m in window
               if m in series.index and (m - pd.DateOffset(months=12)) in series.index]
        growth = float(pd.Series(yoy).median())
        growth_factors.append({"business_unit": bu, "line_item": line,
                               "growth": growth, "n_pairs": len(yoy)})

        for m in horizon:
            base_month = m - pd.DateOffset(months=12)
            base_value = float(series[base_month])
            raw_base = float(g.loc[g["month"] == base_month, "actual"].iloc[0])
            forecasts.append({
                "month": m, "business_unit": bu, "line_item": line,
                "forecast": base_value * growth,
                "base_month": base_month, "base_value": base_value,
                "base_was_normalized": abs(base_value - raw_base) > 1e-9,
                "growth_factor": growth,
            })
    return (pd.DataFrame(forecasts), all_adjustments,
            pd.DataFrame(growth_factors), cutoff, horizon)


def fmt_money(v):
    return f"EUR{v:,.0f}"


def render_report(fc, adjustments, cutoff, horizon):
    kept = [a for a in adjustments if a["reason"].startswith("KEPT")]
    replaced = [a for a in adjustments if not a["reason"].startswith("KEPT")]

    lines = [
        "# Rolling Forecast: EventCo "
        + " / ".join(f"{m:%b %Y}" for m in horizon),
        "",
        "Generated by `agents/forecast_agent.py` from `output/variance_table.csv` "
        "(the Variance & Root-Cause Agent's output: cleaned actuals/budgets plus "
        "materiality flags and evidence). This agent never reads "
        f"`data/ground_truth.md`. Last closed month: {cutoff:%B %Y}.",
        "",
        "## Method",
        "",
        "Forecast = seasonal base × median year-over-year growth, per BU and "
        "line item:",
        "",
        "- **Base**: the same month one year earlier, taken from a *normalized* "
        "history (see adjustments below). The events business is strongly "
        "seasonal, so same-month-last-year carries the right shape.",
        f"- **Growth**: the median year-over-year ratio across the last "
        f"{GROWTH_WINDOW_MONTHS} closed months, on the normalized history. The "
        "median keeps any single distorted pair from steering the factor.",
        "",
        "**Normalization rules.** A forecast is only as good as the history it "
        "extrapolates:",
        "",
        "- Suspected data entry errors (still uncorrected in the cleaned file) "
        "are replaced with budget × the line's typical achievement ratio. A "
        "fat-finger digit must never touch a trend.",
        "- One-off material months (single-month variances, explained or not) "
        "are replaced the same way. One-offs don't recur, and carrying them "
        "into a seasonal base would re-forecast last year's accident.",
        "- Sustained episodes are kept **only if still running at the cutoff** "
        f"(within {EPISODE_ACTIVE_GRACE_MONTHS} months of {cutoff:%Y-%m}); an "
        "episode that ended earlier is normalized out, because its effect is "
        "already over or absorbed into the current baseline.",
        "",
        "## History adjustments (full audit trail)",
        "",
        f"{len(replaced)} month-values normalized, "
        f"{len(kept)} episode month-values deliberately kept.",
        "",
        "| Business Unit | Line item | Month | Raw actual | Used in history | Reason | Evidence |",
        "|---|---|---|---|---|---|---|",
    ]
    for a in sorted(adjustments, key=lambda a: (a["business_unit"], a["line_item"], a["month"])):
        lines.append(
            f"| {a['business_unit']} | {a['line_item']} | {a['month']:%Y-%m} | "
            f"{fmt_money(a['raw_actual'])} | {fmt_money(a['normalized_to'])} | "
            f"{a['reason']} | {a['evidence'] or '-'} |")

    lines += [
        "",
        "## Forecast by BU and line item",
        "",
        "Prior year (PY) is the normalized actual of the same month last year "
        "(the forecast base). Growth is the median YoY factor applied.",
        "",
        "| Business Unit | Line item | Growth | "
        + " | ".join(f"{m:%b-%y}" for m in horizon)
        + " | 3-mo total | PY 3-mo | vs PY |",
        "|---|---|---|" + "---|" * (HORIZON_MONTHS + 3),
    ]
    for (bu, line), g in fc.groupby(["business_unit", "line_item"], sort=False):
        g = g.sort_values("month")
        total, py_total = g["forecast"].sum(), g["base_value"].sum()
        cells = " | ".join(fmt_money(v) for v in g["forecast"])
        lines.append(
            f"| {bu} | {line} | {g['growth_factor'].iloc[0]:.2f}x | {cells} | "
            f"{fmt_money(total)} | {fmt_money(py_total)} | "
            f"{total / py_total - 1:+.1%} |")

    lines += ["", "## Group P&L summary (forecast)", "",
              "| | " + " | ".join(f"{m:%b-%y}" for m in horizon)
              + " | 3-mo total |",
              "|---|" + "---|" * (HORIZON_MONTHS + 1)]
    rev = fc[fc["line_item"] == "Revenue"].groupby("month")["forecast"].sum()
    costs = fc[fc["line_item"].isin(COST_LINES)].groupby("month")["forecast"].sum()
    net = rev - costs
    for label, s in [("Revenue", rev), ("Total costs", costs), ("Net result", net)]:
        cells = " | ".join(fmt_money(s[m]) for m in horizon)
        lines.append(f"| {label} | {cells} | {fmt_money(s.sum())} |")
    lines += [
        "",
        f"Margin: {net.sum() / rev.sum():.1%} of revenue over the horizon.",
        "",
        "No sustained programme was still active at the cutoff, so no episode "
        "effect is carried forward in this run. Had one been active (see the "
        "adjustment rules above), its months would appear as KEPT in the audit "
        "trail and flow into the base." if not kept else
        "Episode months marked KEPT in the audit trail are carried into the "
        "forecast base: their programmes were still running at the cutoff.",
    ]
    return "\n".join(lines) + "\n"


def main():
    df = load_variance_table()
    fc, adjustments, growth, cutoff, horizon = build_forecast(df)

    out = fc.copy()
    out["month"] = out["month"].dt.strftime("%Y-%m")
    out["base_month"] = out["base_month"].dt.strftime("%Y-%m")
    out.to_csv(FORECAST_PATH, index=False)

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(render_report(fc, adjustments, cutoff, horizon))

    n_kept = sum(1 for a in adjustments if a["reason"].startswith("KEPT"))
    print(f"Forecast horizon: {', '.join(f'{m:%Y-%m}' for m in horizon)} "
          f"(cutoff {cutoff:%Y-%m})")
    print(f"Forecast rows: {len(fc)} ({fc.groupby(['business_unit', 'line_item']).ngroups} series)")
    print(f"History adjustments: {len(adjustments) - n_kept} normalized, {n_kept} kept (active episodes)")
    print(f"Growth factors range: {growth['growth'].min():.2f}x .. {growth['growth'].max():.2f}x")
    print(f"Wrote {FORECAST_PATH} and {REPORT_PATH}")


if __name__ == "__main__":
    main()
