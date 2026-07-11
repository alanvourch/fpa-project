"""Generate the synthetic operational-driver dataset for EventCo:
monthly FTE per BU (payroll driver) and monthly projects delivered per BU
(revenue volume driver).

Why a separate file instead of new columns in eventco_monthly.csv:
  - In a real company these numbers come from different systems (HR and
    project ops/CRM), not from the finance export, so a separate file is the
    realistic shape. They are also CLEAN: the planted data-quality mess
    belongs to the finance export story, not here.
  - Regenerating the main dataset with extra columns would shift the seeded
    rng draw order and silently change every committed report, chart and
    figure. This script instead replays the main generator's exact seeded
    path (same module, same call order) to recover the TRUE actuals in
    memory, then derives drivers from them, leaving the main CSV untouched.

Consistency by construction (the whole point of the drivers):
  - payroll_actual = fte_actual x implied monthly rate, exactly. The FTE
    path follows the smoothed payroll achievement signal (headcount is
    quantized and slow-moving; the residual is the rate variance), so a
    payroll bridge decomposes exactly into a volume (FTE) effect and a
    rate effect.
  - revenue_actual(TRUE) = projects_actual x implied avg project value,
    exactly. Volume absorbs roughly VOLUME_SHARE of each month's revenue
    variance (quantized); implied price/mix absorbs the rest.
  - Digital 2025-09 (the FX month): projects held exactly at budget, so the
    entire revenue miss is price (EUR translation), consistent with note
    N08 ("no change in delivered scope").
  - Production 2025-11 (the fat-finger trap): drivers reflect the TRUE
    revenue. Anyone dividing the corrupted EUR52M figure by the normal
    project count gets an implied project value ~10x budget - the ops
    system independently corroborates that the finance figure is a data
    entry error, not a business event.

Outputs:
  - data/eventco_drivers.csv
  - data/ground_truth_drivers.md   (answer key - agents never read it)

Run: .venv/Scripts/python.exe data/generate_drivers.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import generate_dataset as gd  # noqa: E402  (replays the seeded true world)

DRIVERS_PATH = "data/eventco_drivers.csv"
GROUND_TRUTH_PATH = "data/ground_truth_drivers.md"

DRIVER_SEED = 20260710  # separate stream: never touches the main generator's rng
driver_rng = np.random.default_rng(DRIVER_SEED)

# Average budgeted value of one delivered project, per BU. Chosen so monthly
# project counts land in a realistic 10-20 band for a EUR100M events group.
PROJECT_VALUE_BUDGET = {
    "Production": 300_000,   # large activations/launch events
    "Marketing": 100_000,    # campaigns and brand programmes
    "Digital": 175_000,      # platform builds and digital experiences
    "Back-Office": 50_000,   # internal/pass-through service engagements
}

# Share of a month's revenue variance carried by volume (project count);
# the remainder is implied price/mix. Quantization makes the split approximate
# per month, exact in the reconciliation (price is the implied residual).
VOLUME_SHARE = 0.6

FX_MONTH = ("Digital", pd.Timestamp("2025-09-01"))   # note N08: volume on plan
FTE_SMOOTHING_MONTHS = 3
FTE_MAX_DEVIATION = 2

FINAL_COLUMNS = [
    "month", "business_unit",
    "fte_budget", "fte_actual",
    "projects_budget", "projects_actual",
]


def true_world():
    """Replay the main generator's exact seeded path: clean data + business
    anomalies, WITHOUT the data-quality corruption layer. This reproduces the
    true actuals byte-for-byte because generate_dataset seeds its rng at
    import and this call order matches its own main()."""
    clean_df = gd.generate_clean_data()
    df, _ = gd.inject_business_anomalies(clean_df)
    return df


def build_fte(df):
    """FTE per BU/month. Budget FTE is the BU's planned headcount (constant,
    matching how payroll_budget was built: fte x average salary x pay
    inflation). Actual FTE follows the 3-month smoothed payroll achievement
    ratio, quantized to whole heads and capped at +/-2 vs plan: headcount
    moves slowly and in whole people, so the month-to-month payroll wobble
    beyond that is rate (salary mix, overtime, timing), not heads."""
    df = df.sort_values(["business_unit", "month"]).reset_index(drop=True)
    out = []
    for bu, g in df.groupby("business_unit"):
        g = g.sort_values("month")
        fte_budget = gd.BU_PARAMS[bu]["fte"]
        ratio = (g["payroll_actual"] / g["payroll_budget"]).rolling(
            FTE_SMOOTHING_MONTHS, min_periods=1).mean()
        deviation = np.clip(
            np.round(fte_budget * (ratio - 1.0)),
            -FTE_MAX_DEVIATION, FTE_MAX_DEVIATION,
        ).astype(int)
        for (_, r), d in zip(g.iterrows(), deviation):
            out.append({
                "month": r["month"], "business_unit": bu,
                "fte_budget": fte_budget, "fte_actual": fte_budget + int(d),
            })
    return pd.DataFrame(out)


def build_projects(df):
    """Projects delivered per BU/month. Budget count = budgeted revenue /
    budgeted average project value (rounded, min 1). Actual count moves with
    the TRUE revenue achievement ratio, dampened to VOLUME_SHARE, plus a
    small seeded jitter - so volume explains most of a revenue variance and
    implied price/mix explains the rest. The FX month is forced to budget
    volume: the miss there is purely translation."""
    df = df.sort_values(["business_unit", "month"]).reset_index(drop=True)
    out = []
    for _, r in df.iterrows():
        bu = r["business_unit"]
        budget_n = max(1, round(r["revenue_budget"] / PROJECT_VALUE_BUDGET[bu]))
        ratio = r["revenue_actual"] / r["revenue_budget"]
        jitter = int(driver_rng.choice([-1, 0, 0, 0, 1]))
        actual_n = max(1, round(budget_n * (1 + VOLUME_SHARE * (ratio - 1))) + jitter)
        if (bu, r["month"]) == FX_MONTH:
            actual_n = budget_n
        out.append({
            "month": r["month"], "business_unit": bu,
            "projects_budget": budget_n, "projects_actual": actual_n,
        })
    return pd.DataFrame(out)


def write_ground_truth(df, drivers):
    merged = drivers.merge(
        df[["month", "business_unit", "revenue_budget", "revenue_actual",
            "payroll_budget", "payroll_actual"]],
        on=["month", "business_unit"],
    )
    fx = merged[(merged["business_unit"] == FX_MONTH[0]) & (merged["month"] == FX_MONTH[1])].iloc[0]
    trap = merged[(merged["business_unit"] == "Production")
                  & (merged["month"] == pd.Timestamp("2025-11-01"))].iloc[0]
    trap_corrupted = trap["revenue_actual"] * 10  # the fat-fingered figure in the raw export
    dev_counts = {
        int(k): int(v)
        for k, v in (merged["fte_actual"] - merged["fte_budget"]).value_counts().sort_index().items()
    }

    content = f"""# EventCo Driver Dataset: Ground Truth

Generated by `generate_drivers.py` (driver seed {DRIVER_SEED}; the P&L side
replays `generate_dataset.py`'s seed {gd.SEED} to recover the true actuals).
Answer key for validating driver-based outputs - agents never read this file;
`tests/validate_drivers.py` does.

## What the drivers are

`data/eventco_drivers.csv`: one row per BU per month (120 rows), from the HR
and project-ops systems respectively - deliberately CLEAN data, unlike the
messy finance export:

- **fte_budget / fte_actual**: planned vs actual headcount. Budget is the
  BU's planned headcount (Production 55, Marketing 20, Digital 40,
  Back-Office 35; group 150). Actual follows the 3-month smoothed payroll
  achievement ratio, in whole heads, capped at +/-2 vs plan. Deviation
  distribution across all 120 rows: {dev_counts}.
- **projects_budget / projects_actual**: planned vs delivered project count.
  Budget = budgeted revenue / budgeted average project value
  ({", ".join(f"{bu} EUR{v:,.0f}" for bu, v in PROJECT_VALUE_BUDGET.items())}).
  Actual carries ~{VOLUME_SHARE:.0%} of each month's true revenue variance
  (quantized, small seeded jitter); implied price/mix is the exact residual.

## Reconciliation identities (hold exactly, by construction)

- payroll_actual = fte_actual x (payroll_actual / fte_actual): the payroll
  bridge splits variance into a volume effect (delta FTE x budget monthly
  rate) and a rate effect (delta rate x actual FTE) that sum EXACTLY to the
  payroll variance.
- revenue_actual (true) = projects_actual x implied average project value:
  the revenue bridge splits variance into volume (delta projects x budget
  value) and price/mix (delta value x actual projects) that sum EXACTLY to
  the true revenue variance.

## Planted driver stories (only two - drivers are context, not new anomalies)

1. **FX month, Digital / 2025-09**: projects_actual = projects_budget
   ({fx['projects_actual']:.0f} = {fx['projects_budget']:.0f}). The EUR{fx['revenue_budget'] - fx['revenue_actual']:,.0f}
   revenue miss is 100% price (USD contract translated at a stronger EUR),
   0% volume - independently corroborating note N08 ("no change in
   delivered scope").
2. **Trap month, Production / 2025-11**: drivers reflect the TRUE revenue of
   EUR{trap['revenue_actual']:,.0f} ({trap['projects_actual']:.0f} projects vs
   {trap['projects_budget']:.0f} budgeted). Dividing the corrupted export figure of
   EUR{trap_corrupted:,.0f} by that project count implies
   EUR{trap_corrupted / trap['projects_actual']:,.0f} per project vs a budget value of
   EUR{PROJECT_VALUE_BUDGET['Production']:,.0f} - roughly 10x. The ops system
   independently confirms the finance figure is a data entry error, not a
   real business event.

There are NO other planted headcount or volume anomalies: no attrition story,
no comp-band analysis, no workforce planning. Drivers exist so variance
commentary can go one level below the P&L line (rate vs volume, price vs
volume), nothing more.
"""
    with open(GROUND_TRUTH_PATH, "w", encoding="utf-8") as f:
        f.write(content)


def main():
    df = true_world()
    drivers = build_fte(df).merge(build_projects(df), on=["month", "business_unit"])
    drivers = drivers.sort_values(["business_unit", "month"]).reset_index(drop=True)

    out = drivers.copy()
    out["month"] = out["month"].dt.strftime("%Y-%m-%d")
    out = out[FINAL_COLUMNS]
    out.to_csv(DRIVERS_PATH, index=False)
    write_ground_truth(df, drivers)

    total_fte = drivers.groupby("month")["fte_actual"].sum()
    print(f"Wrote {DRIVERS_PATH}: {len(out)} rows "
          f"({drivers['business_unit'].nunique()} BUs x {drivers['month'].nunique()} months)")
    print(f"Group actual FTE range: {total_fte.min():.0f}..{total_fte.max():.0f} (plan 150)")
    print(f"Project counts (budget): {drivers['projects_budget'].min()}..{drivers['projects_budget'].max()} per BU/month")
    print(f"Wrote {GROUND_TRUTH_PATH}")


if __name__ == "__main__":
    main()
