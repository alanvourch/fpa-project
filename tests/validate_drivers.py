"""Validate data/eventco_drivers.csv against its construction guarantees.

Checks, in order:
  1. Determinism: regenerating the drivers in memory reproduces the committed
     CSV exactly (same seeds, same replayed true world).
  2. Structure: 120 rows (4 BUs x 30 months), integer columns, no gaps, no
     duplicates, budget FTE sums to the 150-head plan every month.
  3. Replay fidelity: the replayed true world matches the cleaned CSV on
     payroll (never corrupted beyond formatting) for every row, and on
     revenue for every row except the trap row, where cleaned = 10x true.
  4. Payroll bridge: volume effect + rate effect == payroll variance,
     exactly, for every BU/month.
  5. Revenue bridge: volume effect + price effect == true revenue variance,
     exactly, for every BU/month.
  6. FX month (Digital 2025-09): projects at budget; the miss is 100% price.
  7. Trap month (Production 2025-11): implied price from the CORRUPTED
     export figure is >4x the budget project value (the same magnitude rule
     the ingestion agent uses), i.e. the ops system corroborates the error.
  8. FTE sanity: |actual - budget| <= 2 heads everywhere.

Run: .venv/Scripts/python.exe tests/validate_drivers.py
"""

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "data"))

import generate_dataset as gd  # noqa: E402
import generate_drivers as gdr  # noqa: E402

DRIVERS_PATH = ROOT / "data" / "eventco_drivers.csv"
CLEANED_PATH = ROOT / "data" / "eventco_monthly_cleaned.csv"

TRAP_BU, TRAP_MONTH = "Production", pd.Timestamp("2025-11-01")
FX_BU, FX_MONTH = "Digital", pd.Timestamp("2025-09-01")

TOL = 1e-6  # float reconciliation tolerance, EUR

results = []


def check(ok, msg):
    results.append((bool(ok), msg))


def main():
    committed = pd.read_csv(DRIVERS_PATH, parse_dates=["month"])
    cleaned = pd.read_csv(CLEANED_PATH, parse_dates=["month"])

    # 1. Determinism
    true_df = gdr.true_world()
    regen = gdr.build_fte(true_df).merge(
        gdr.build_projects(true_df), on=["month", "business_unit"]
    ).sort_values(["business_unit", "month"]).reset_index(drop=True)[gdr.FINAL_COLUMNS]
    same = regen.reset_index(drop=True).equals(
        committed[gdr.FINAL_COLUMNS].reset_index(drop=True))
    check(same, "regenerating drivers in memory reproduces the committed CSV exactly"
          if same else "regenerated drivers DIFFER from the committed CSV: rerun data/generate_drivers.py or investigate seed drift")

    # 2. Structure
    check(len(committed) == 120, f"120 rows expected, found {len(committed)}")
    check(committed["business_unit"].nunique() == 4 and committed["month"].nunique() == 30,
          "coverage is 4 BUs x 30 months")
    check(not committed.duplicated(subset=["month", "business_unit"]).any(),
          "no duplicate BU/month rows")
    check(committed[["fte_budget", "fte_actual", "projects_budget", "projects_actual"]]
          .notna().all().all(), "no missing driver values")
    fte_plan = committed.groupby("month")["fte_budget"].sum()
    check((fte_plan == 150).all(),
          f"budget FTE sums to the 150-head plan every month (found {fte_plan.min()}..{fte_plan.max()})")

    # 3. Replay fidelity vs the cleaned CSV
    m = true_df.merge(cleaned, on=["month", "business_unit"], suffixes=("_true", "_clean"))
    check(len(m) == 120, f"true world joins cleaned CSV on all 120 rows (found {len(m)})")
    pay_match = (m["payroll_actual_true"] - m["payroll_actual_clean"]).abs().max()
    check(pay_match < 0.01,
          f"replayed true payroll matches cleaned payroll on every row (max diff EUR{pay_match:.4f})")
    trap_mask = (m["business_unit"] == TRAP_BU) & (m["month"] == TRAP_MONTH)
    rev_diff = (m.loc[~trap_mask, "revenue_actual_true"]
                - m.loc[~trap_mask, "revenue_actual_clean"]).abs().max()
    check(rev_diff < 0.01,
          f"replayed true revenue matches cleaned revenue on all non-trap rows (max diff EUR{rev_diff:.4f})")
    trap = m.loc[trap_mask].iloc[0]
    ratio = trap["revenue_actual_clean"] / trap["revenue_actual_true"]
    check(abs(ratio - 10) < 1e-9,
          f"trap row: cleaned revenue is exactly 10x the true revenue (ratio {ratio:.6f})")

    # 4. Payroll bridge reconciles exactly (volume + rate == variance)
    d = committed.merge(cleaned[["month", "business_unit", "payroll_budget", "payroll_actual",
                                 "revenue_budget"]],
                        on=["month", "business_unit"])
    d = d.merge(true_df[["month", "business_unit", "revenue_actual"]].rename(
        columns={"revenue_actual": "revenue_actual_true"}), on=["month", "business_unit"])
    rate_b = d["payroll_budget"] / d["fte_budget"]
    rate_a = d["payroll_actual"] / d["fte_actual"]
    vol_eff = (d["fte_actual"] - d["fte_budget"]) * rate_b
    rate_eff = (rate_a - rate_b) * d["fte_actual"]
    gap = (vol_eff + rate_eff - (d["payroll_actual"] - d["payroll_budget"])).abs().max()
    check(gap < TOL, f"payroll bridge (FTE volume + rate) reconciles exactly on all 120 rows (max gap EUR{gap:.2e})")

    # 5. Revenue bridge reconciles exactly (volume + price == true variance)
    val_b = d["revenue_budget"] / d["projects_budget"]
    val_a = d["revenue_actual_true"] / d["projects_actual"]
    vol_eff_r = (d["projects_actual"] - d["projects_budget"]) * val_b
    price_eff_r = (val_a - val_b) * d["projects_actual"]
    gap_r = (vol_eff_r + price_eff_r - (d["revenue_actual_true"] - d["revenue_budget"])).abs().max()
    check(gap_r < TOL, f"revenue bridge (volume + price/mix) reconciles exactly on all 120 rows (max gap EUR{gap_r:.2e})")

    # 6. FX month: pure price effect
    fx = d[(d["business_unit"] == FX_BU) & (d["month"] == FX_MONTH)].iloc[0]
    check(fx["projects_actual"] == fx["projects_budget"],
          f"FX month {FX_BU} {FX_MONTH:%Y-%m}: projects at budget "
          f"({fx['projects_actual']} = {fx['projects_budget']}), the whole miss is price")

    # 7. Trap month: corrupted figure fails the driver plausibility check
    tr = d[(d["business_unit"] == TRAP_BU) & (d["month"] == TRAP_MONTH)].iloc[0]
    corrupted = tr["revenue_actual_true"] * 10
    implied = corrupted / tr["projects_actual"]
    budget_val = gdr.PROJECT_VALUE_BUDGET[TRAP_BU]
    check(implied > 4 * budget_val,
          f"trap month: corrupted export implies EUR{implied:,.0f}/project vs EUR{budget_val:,.0f} "
          f"budgeted ({implied / budget_val:.1f}x, above the 4x data-error rule) - ops data corroborates the error")

    # 8. FTE bounds
    dev = (committed["fte_actual"] - committed["fte_budget"]).abs().max()
    check(dev <= 2, f"FTE actuals stay within 2 heads of plan (max deviation {dev})")

    n_fail = sum(1 for ok, _ in results if not ok)
    for ok, msg in results:
        print(f"  {'PASS' if ok else 'FAIL'} - {msg}")
    print(f"\nRESULT: {'all checks passed.' if not n_fail else f'{n_fail} CHECK(S) FAILED.'}")
    return 1 if n_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
