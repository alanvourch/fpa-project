"""Generate a synthetic 30-month Budget/Actual/N-1 dataset for the fictional
events agency "EventCo" (4 BUs, ~150 FTE, ~EUR100M/year revenue).

Cost structure, as a share of group revenue in the base year: external
production bought for client projects (venues, technical suppliers, staging,
catering, freight, content, media) about 63%; freelance and project staff
(intermittents, freelance producers, event staff) about 11%; permanent
payroll, fully loaded with employer social charges, about 12% for the 130
FTE in the business lines; overheads about 10%, made of allocated office
rent and facilities, the agency's own marketing and new business, IT,
non-billable travel, allocated central G&A (the 20 central FTE in finance,
HR, IT and management, professional fees, insurance, other admin) and
depreciation. The operating result lands around 4% of revenue, the low
single digits a French events agency of this size earns.

Two distinct kinds of "problems" are planted on purpose:
  - business anomalies: real economic events the Variance Agent should explain
  - data quality issues: recording/transcription errors the Ingestion/QA Agent
    should clean, including one trap that looks like a business anomaly but
    is actually a fat-fingered data entry error

Every corruption applied below is logged into `notes` lists and written out
to data/ground_truth.md, so the documentation can never drift from the data.
"""

import numpy as np
import pandas as pd
from faker import Faker

SEED = 42
rng = np.random.default_rng(SEED)
# The freelance, G&A and depreciation lines draw from their own stream so the
# main stream's draw order (and with it the position of every planted
# anomaly and data-quality issue) is unchanged by their addition.
rng_overhead = np.random.default_rng(SEED + 1)
Faker.seed(SEED)
fake_fr = Faker("fr_FR")
fake_us = Faker("en_US")

N_MONTHS = 30
MONTHS = pd.date_range("2024-01-01", periods=N_MONTHS, freq="MS")
# Client-facing revenue verticals (business lines), not internal functions:
# each carries its own delivery P&L (revenue, COGS, payroll, opex).
BUS = ["Brand Events", "Corporate Events", "Digital/Influence", "Government & Institutions"]

# events industry seasonality index by calendar month, averages to 1.0 over the year
SEASONALITY = {
    1: 0.70, 2: 0.80, 3: 0.90, 4: 1.15, 5: 1.25, 6: 1.20,
    7: 0.85, 8: 0.60, 9: 0.95, 10: 1.20, 11: 1.30, 12: 1.10,
}

ANNUAL_REVENUE_GROWTH = 0.04
ANNUAL_PAY_INFLATION = 0.03

# Month-to-month noise (standard deviation of actual / budget) per line.
# Revenue carries the business's own volatility; external production and
# freelance are built on actual revenue, so their own noise is the rate
# and mix wobble on top of the volume effect they inherit from revenue.
NOISE = {
    "revenue": 0.05, "cogs": 0.03, "freelance": 0.04, "payroll": 0.02,
    "travel": 0.10, "marketing": 0.10, "it": 0.08, "facilities": 0.015,
    "ga": 0.04, "depreciation": 0.005, "prior_year": 0.03,
}

# Per business line: annual revenue; external production (cogs) and freelance
# as shares of revenue; permanent FTE and their fully loaded annual cost
# (gross salary plus employer social charges); monthly overhead bases.
# Facilities are allocated by headcount (about EUR2.0M a year of Paris office
# and warehouse for 130 desks), G&A and depreciation by revenue share
# (EUR4.8M and EUR0.8M a year at group level).
BU_PARAMS = {
    "Brand Events":              {"revenue_annual": 45_000_000, "cogs_ratio": 0.67, "freelance_ratio": 0.12,
                                   "fte": 52, "avg_cost": 84_000,
                                   "travel_base": 25_000, "marketing_base": 30_000, "it_base": 20_000,
                                   "facilities_base": 66_700, "ga_base": 180_000, "da_base": 30_000},
    "Corporate Events":          {"revenue_annual": 20_000_000, "cogs_ratio": 0.61, "freelance_ratio": 0.11,
                                   "fte": 26, "avg_cost": 90_000,
                                   "travel_base": 15_000, "marketing_base": 45_000, "it_base": 10_000,
                                   "facilities_base": 33_300, "ga_base": 80_000, "da_base": 13_300},
    "Digital/Influence":         {"revenue_annual": 25_000_000, "cogs_ratio": 0.59, "freelance_ratio": 0.10,
                                   "fte": 36, "avg_cost": 104_000,
                                   "travel_base": 12_000, "marketing_base": 20_000, "it_base": 20_000,
                                   "facilities_base": 46_200, "ga_base": 100_000, "da_base": 16_700},
    "Government & Institutions": {"revenue_annual": 10_000_000, "cogs_ratio": 0.56, "freelance_ratio": 0.12,
                                   "fte": 16, "avg_cost": 81_000,
                                   "travel_base": 6_000, "marketing_base": 5_000, "it_base": 15_000,
                                   "facilities_base": 20_500, "ga_base": 40_000, "da_base": 6_700},
}

FINAL_COLUMNS = [
    "month", "business_unit",
    "revenue_budget", "revenue_actual", "revenue_prior_year",
    "cogs_budget", "cogs_actual",
    "freelance_budget", "freelance_actual",
    "payroll_budget", "payroll_actual",
    "opex_travel_budget", "opex_travel_actual",
    "opex_marketing_budget", "opex_marketing_actual",
    "opex_it_budget", "opex_it_actual",
    "opex_facilities_budget", "opex_facilities_actual",
    "opex_ga_budget", "opex_ga_actual",
    "depreciation_budget", "depreciation_actual",
]


def generate_clean_data():
    rows = []
    for bu in BUS:
        p = BU_PARAMS[bu]
        for i, date in enumerate(MONTHS):
            season = SEASONALITY[date.month]
            rev_growth = (1 + ANNUAL_REVENUE_GROWTH) ** (i / 12)
            pay_growth = (1 + ANNUAL_PAY_INFLATION) ** (i / 12)

            revenue_budget = p["revenue_annual"] / 12 * season * rev_growth
            revenue_actual = revenue_budget * rng.normal(1.0, NOISE["revenue"])

            cogs_budget = revenue_budget * p["cogs_ratio"]
            cogs_actual = revenue_actual * p["cogs_ratio"] * rng.normal(1.0, NOISE["cogs"])

            payroll_budget = p["fte"] * p["avg_cost"] / 12 * pay_growth
            payroll_actual = payroll_budget * rng.normal(1.0, NOISE["payroll"])

            travel_budget = p["travel_base"] * (0.7 + 0.3 * season)
            travel_actual = travel_budget * rng.normal(1.0, NOISE["travel"])

            mktg_budget = p["marketing_base"] * (0.7 + 0.3 * season)
            mktg_actual = mktg_budget * rng.normal(1.0, NOISE["marketing"])

            it_budget = p["it_base"] * (1 + 0.02 * i / 12)
            it_actual = it_budget * rng.normal(1.0, NOISE["it"])

            # Rent is contractual: the small wobble is utilities and services.
            fac_budget = p["facilities_base"] * (1 + 0.015 * i / 12)
            fac_actual = fac_budget * rng.normal(1.0, NOISE["facilities"])

            # Freelance follows activity like external production, with its
            # own rate noise on top (day rates, last-minute crews).
            freelance_budget = revenue_budget * p["freelance_ratio"]
            freelance_actual = revenue_actual * p["freelance_ratio"] * rng_overhead.normal(1.0, NOISE["freelance"])

            # Allocated central costs and depreciation are budgeted flat with
            # slow growth; their actuals move with central spend, not activity.
            ga_budget = p["ga_base"] * (1 + 0.02 * i / 12)
            ga_actual = ga_budget * rng_overhead.normal(1.0, NOISE["ga"])

            da_budget = p["da_base"] * (1 + 0.03 * i / 12)
            da_actual = da_budget * rng_overhead.normal(1.0, NOISE["depreciation"])

            rows.append({
                "month": date, "business_unit": bu,
                "revenue_budget": revenue_budget, "revenue_actual": revenue_actual,
                "cogs_budget": cogs_budget, "cogs_actual": cogs_actual,
                "freelance_budget": freelance_budget, "freelance_actual": freelance_actual,
                "payroll_budget": payroll_budget, "payroll_actual": payroll_actual,
                "opex_travel_budget": travel_budget, "opex_travel_actual": travel_actual,
                "opex_marketing_budget": mktg_budget, "opex_marketing_actual": mktg_actual,
                "opex_it_budget": it_budget, "opex_it_actual": it_actual,
                "opex_facilities_budget": fac_budget, "opex_facilities_actual": fac_actual,
                "opex_ga_budget": ga_budget, "opex_ga_actual": ga_actual,
                "depreciation_budget": da_budget, "depreciation_actual": da_actual,
            })

    df = pd.DataFrame(rows)

    # revenue_prior_year: true N-1 for months where the prior year exists in-dataset,
    # otherwise a synthesized 2023 estimate backed out of the growth trend
    df["revenue_prior_year"] = np.nan
    for bu in BUS:
        mask = df["business_unit"] == bu
        actual = df.loc[mask, "revenue_actual"].to_numpy()
        prior = np.empty(N_MONTHS)
        prior[12:] = actual[:-12]
        prior[:12] = actual[:12] / (1 + ANNUAL_REVENUE_GROWTH) * rng.normal(1.0, NOISE["prior_year"], size=12)
        df.loc[mask, "revenue_prior_year"] = prior

    return df[FINAL_COLUMNS[:1] + FINAL_COLUMNS[1:2] + [c for c in FINAL_COLUMNS if c not in ("month", "business_unit")]]


# Q2 2025 external-production overrun on one Brand Events project: about
# EUR2.0M over three months, consistent with the BU controller's note N13.
# (The three months run a few percent under budget before the injection,
# so the factor is set above the +21% the variance report ends up showing.)
OVERRUN_FACTOR = 1.29


def inject_business_anomalies(df):
    notes = []
    idx = {(r.business_unit, r.month): i for i, r in df.iterrows()}

    # 1. client project overrun (unfavorable) -- Brand Events, Q2 2025, subcontractor cost blowout
    client_name = fake_fr.company()
    q2_2025 = pd.date_range("2025-04-01", periods=3, freq="MS")
    for m in q2_2025:
        i = idx[("Brand Events", m)]
        before = df.at[i, "cogs_actual"]
        after = before * OVERRUN_FACTOR
        df.at[i, "cogs_actual"] = after
        notes.append(
            f"- **Brand Events / {m:%Y-%m}**: COGS actual jumped from EUR{before:,.0f} to "
            f"EUR{after:,.0f} (+{OVERRUN_FACTOR - 1:.0%}). Root cause: subcontractor scope creep on the "
            f"'{client_name}' activation contract ran well over budget across Q2 2025. Unfavorable."
        )

    # 2. FX-driven variance (unfavorable) -- Digital/Influence, one international USD-invoiced contract
    intl_client = fake_us.company()
    m = pd.Timestamp("2025-09-01")
    i = idx[("Digital/Influence", m)]
    before = df.at[i, "revenue_actual"]
    after = before * 0.91
    df.at[i, "revenue_actual"] = after
    notes.append(
        f"- **Digital/Influence / {m:%Y-%m}**: Revenue actual came in at EUR{after:,.0f} vs an "
        f"unimpacted run-rate of ~EUR{before:,.0f} (-9%). Root cause: the '{intl_client}' "
        f"contract is invoiced in USD; EUR strengthened against USD that month. Unfavorable, FX-driven, not volume-driven."
    )

    # 3. one-off cost spike (unfavorable) -- Government & Institutions, emergency on-site IT failure
    m = pd.Timestamp("2024-11-01")
    i = idx[("Government & Institutions", m)]
    before = df.at[i, "opex_it_actual"]
    after = before * 2.8
    df.at[i, "opex_it_actual"] = after
    notes.append(
        f"- **Government & Institutions / {m:%Y-%m}**: IT opex actual spiked from EUR{before:,.0f} to "
        f"EUR{after:,.0f} (+180%). Root cause: on-site registration and AV control systems failed during "
        f"a ministry summit engagement; emergency replacement hardware was procured outside the normal "
        f"purchasing cycle. One-time, non-recurring. Unfavorable."
    )

    # 4. favorable variance -- Corporate Events, renegotiated agency/media-buying contracts
    h2_2025 = pd.date_range("2025-07-01", periods=6, freq="MS")
    for m in h2_2025:
        i = idx[("Corporate Events", m)]
        before = df.at[i, "opex_marketing_actual"]
        after = before * 0.78
        df.at[i, "opex_marketing_actual"] = after
        notes.append(
            f"- **Corporate Events / {m:%Y-%m}**: Marketing opex actual came in at EUR{after:,.0f} vs "
            f"a pre-savings run-rate of ~EUR{before:,.0f} (-22%). Root cause: renegotiated media-buying "
            f"and agency contracts effective July 2025. Favorable, sustained cost savings (not a data error)."
        )

    return df, notes


def format_currency(value):
    if rng.random() < 0.5:
        return f"EUR{value:,.0f}"
    return f"{value:,.0f} EUR"


DATE_FORMATS = [
    lambda d: d.strftime("%Y-%m-%d"),
    lambda d: d.strftime("%m/%d/%Y"),
    lambda d: d.strftime("%B %Y"),
    lambda d: d.strftime("%Y/%m"),
]


def inject_data_quality_issues(df):
    notes = []
    df = df.copy()
    n = len(df)
    numeric_cols_all = [c for c in FINAL_COLUMNS if c not in ("month", "business_unit")]
    df = df.astype({c: object for c in numeric_cols_all})

    # a) typos / inconsistent casing in business_unit
    typo_map = {
        "Brand Events": ["Brand Evnets", "BRAND EVENTS"],
        "Corporate Events": ["Corportae Events", "corporate events"],
        "Digital/Influence": ["Digital/Inlfuence", "DIGITAL/INFLUENCE "],
        "Government & Institutions": ["Government and Institutions", "Government&Institutions"],
    }
    typo_idx = rng.choice(n, size=7, replace=False)
    typo_details = []
    for i in typo_idx:
        original = df.at[i, "business_unit"]
        variant = typo_map[original][rng.integers(0, 2)]
        df.at[i, "business_unit"] = variant
        typo_details.append(f"{df.at[i, 'month']:%Y-%m} {original} -> \"{variant}\"")
    notes.append(
        "- **BU name typos/casing** (7 rows): " + "; ".join(typo_details) +
        ". These must be normalized back to the canonical 4 BU names."
    )

    # b) missing values in Opex categories
    opex_cols = ["opex_travel_budget", "opex_travel_actual", "opex_marketing_budget", "opex_marketing_actual",
                 "opex_it_budget", "opex_it_actual", "opex_facilities_budget", "opex_facilities_actual",
                 "opex_ga_budget", "opex_ga_actual"]
    missing_rows = rng.choice(n, size=9, replace=False)
    missing_cols = rng.choice(opex_cols, size=9, replace=True)
    missing_details = []
    for i, col in zip(missing_rows, missing_cols):
        missing_details.append(f"{df.at[i, 'month']:%Y-%m} {df.at[i, 'business_unit']} / {col}")
        df.at[i, col] = np.nan
    notes.append(
        "- **Missing Opex values** (9 cells, blank in the CSV): " + "; ".join(missing_details) +
        ". Should be imputed or flagged, not treated as zero."
    )

    # c) amounts stored as currency-formatted text instead of numbers
    numeric_cols = numeric_cols_all
    remaining_mask = np.ones(n, dtype=bool)
    remaining_mask[missing_rows] = False
    candidate_rows = np.where(remaining_mask)[0]
    currency_rows = rng.choice(candidate_rows, size=10, replace=False)
    currency_cols = rng.choice([c for c in numeric_cols if c != "revenue_actual"], size=10, replace=True)
    currency_details = []
    for i, col in zip(currency_rows, currency_cols):
        value = df.at[i, col]
        if pd.isna(value):
            continue
        df.at[i, col] = format_currency(value)
        currency_details.append(f"{df.at[i, 'month']:%Y-%m} {df.at[i, 'business_unit']} / {col}")
    notes.append(
        "- **Currency-formatted text amounts** (10 cells stored as strings like \"EUR120,000\" "
        "instead of a plain number): " + "; ".join(currency_details) +
        ". Must be parsed back to numeric before any aggregation."
    )

    # d) the trap: fat-fingered extra digit that looks like a business anomaly but isn't
    trap_month = pd.Timestamp("2025-11-01")
    trap_i = df.index[(df["business_unit"] == "Brand Events") & (df["month"] == trap_month)][0]
    true_value = df.at[trap_i, "revenue_actual"]
    fat_fingered = true_value * 10
    df.at[trap_i, "revenue_actual"] = fat_fingered
    notes.append(
        f"- **DATA ENTRY TRAP: Brand Events / {trap_month:%Y-%m} / revenue_actual**: recorded as "
        f"EUR{fat_fingered:,.0f}, an extra trailing zero fat-fingered during manual entry. True value is "
        f"EUR{true_value:,.0f}. This is NOT a real business anomaly: at ~10x the normal monthly run-rate "
        f"for a single BU (more than half the company's typical *annual* revenue), it fails a basic magnitude "
        f"sanity check against trailing months and against COGS/payroll for the same period, which stayed normal. "
        f"Correct by dividing by 10 back to EUR{true_value:,.0f} before any variance analysis."
    )

    # e) inconsistent date formats (applied before duplication so duplicates inherit the same string)
    date_choice = rng.integers(0, len(DATE_FORMATS), size=n)
    df["month"] = [DATE_FORMATS[c](d) for c, d in zip(date_choice, df["month"])]
    fmt_counts = pd.Series(date_choice).value_counts().sort_index()
    notes.append(
        "- **Inconsistent date formats** in the `month` column: mixes ISO (YYYY-MM-DD), US (MM/DD/YYYY), "
        "long-form (\"Month YYYY\"), and year/month (YYYY/MM): " +
        ", ".join(f"{fmt_counts.get(i, 0)} rows as format #{i}" for i in range(len(DATE_FORMATS))) +
        ". All represent the first day of the month and must be normalized to a single date type."
    )

    # f) duplicate rows (same month/BU entered twice)
    dup_idx = rng.choice(n, size=4, replace=False)
    dup_details = []
    for i in dup_idx:
        dup_details.append(f"{df.at[i, 'month']} {df.at[i, 'business_unit']}")
    dup_rows = df.loc[dup_idx]
    df = pd.concat([df, dup_rows], ignore_index=True)
    notes.append(
        "- **Duplicate rows** (4 month/BU combinations entered twice): " + "; ".join(dup_details) +
        ". Must be de-duplicated before aggregation to avoid double-counting."
    )

    return df, notes


def write_ground_truth(business_notes, dq_notes, path):
    content = f"""# EventCo Synthetic Dataset: Ground Truth

Generated by `generate_dataset.py` with a fixed random seed ({SEED}) for full
reproducibility. This document is the answer key for validating later agent
outputs (Ingestion, Variance, QA) against what was actually planted in
`eventco_monthly.csv`.

## 1. Business anomalies (for the Variance & Root-Cause Agent to explain)

These are real economic events reflected in the true actuals; they are not
data errors and should survive data cleaning untouched.

{chr(10).join(business_notes)}

See also `data/ground_truth_drivers.md` (written by `generate_drivers.py`) for
the operational-driver dataset: monthly FTE and projects delivered per BU,
derived consistent with the true actuals above.

## 2. Data quality issues (for the Ingestion/QA Agent to clean)

These are recording/transcription problems in the raw export. None of them
represent real financial events; all should be fixed during ingestion, before
any variance analysis runs.

{chr(10).join(dq_notes)}

## 3. Why the trap matters

The data entry trap (see above) is deliberately similar in *shape* to a real
anomaly (a large, unexplained jump in a single BU/month) but is
distinguishable by magnitude: it implies a single BU produced in one month
more revenue than several months of its entire annual budget, with no
corresponding movement in COGS or payroll. A later agent that flags variances
purely on percentage deviation without a magnitude/plausibility check would
misreport this as a business anomaly. It should instead be caught and
corrected during ingestion/QA, before it ever reaches the Variance Agent.

## 4. Business notes evidence map (validation only)

`data/business_notes.csv` (21 dated, BU-tagged internal notes) was authored alongside the
anomalies above so the Variance & Root-Cause Agent has genuine operational evidence to
ground its explanations in, plus deliberate noise so matching isn't trivial. The agent
must never read this file; `tests/validate_variance.py` uses this map after the fact.

Signal notes (each maps to one real business anomaly documented in section 1):

- **Brand Events / cogs_actual** (client project overrun, Falcon launch): signal notes: N11, N13
- **Digital/Influence / revenue_actual** (FX on USD contract; revenue-only, delivery costs are EUR-denominated): signal notes: N08
- **Government & Institutions / opex_it_actual** (one-off IT infrastructure failure): signal notes: N06
- **Corporate Events / opex_marketing_actual** (favorable in-housing savings): signal notes: N12, N16

Noise notes (must never be cited as a variance explanation): N01, N02, N03, N04, N05, N07, N09, N10, N14, N15, N17, N18, N19, N20, N21
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def main():
    clean_df = generate_clean_data()
    clean_df, business_notes = inject_business_anomalies(clean_df)
    raw_df, dq_notes = inject_data_quality_issues(clean_df)
    raw_df = raw_df[FINAL_COLUMNS]

    csv_path = "data/eventco_monthly.csv"
    raw_df.to_csv(csv_path, index=False)
    write_ground_truth(business_notes, dq_notes, "data/ground_truth.md")

    print(f"Wrote {csv_path}: {len(raw_df)} rows (includes 4 planted duplicates)")
    print(f"Clean (pre-corruption) rows: {len(clean_df)}")
    print(f"Date range: {clean_df['month'].min():%Y-%m} to {clean_df['month'].max():%Y-%m}")
    print("\nRevenue actual totals by BU (clean, EUR):")
    totals = clean_df.groupby("business_unit")["revenue_actual"].sum().sort_values(ascending=False)
    for bu, total in totals.items():
        print(f"  {bu:<14} {total:>15,.0f}")
    print(f"  {'TOTAL':<14} {totals.sum():>15,.0f}")

    # Base-year (first 12 months) group P&L on true actuals, so the cost
    # structure behind the parameters above is visible at a glance.
    base = clean_df[clean_df["month"] < MONTHS[12]]
    revenue = base["revenue_actual"].sum()
    print(f"\nBase-year group P&L (true actuals, {MONTHS[0]:%Y}), EUR and % of revenue:")
    print(f"  {'Revenue':<24} {revenue:>14,.0f}  100.0%")
    cost_lines = [c for c in FINAL_COLUMNS if c.endswith("_actual") and c != "revenue_actual"]
    total_costs = 0.0
    for col in cost_lines:
        value = base[col].sum()
        total_costs += value
        print(f"  {col[:-7]:<24} {value:>14,.0f}  {value / revenue:>5.1%}")
    result = revenue - total_costs
    print(f"  {'Operating result':<24} {result:>14,.0f}  {result / revenue:>5.1%}")
    print(f"\nWrote data/ground_truth.md ({len(business_notes)} business anomalies, "
          f"{len(dq_notes)} data quality issue categories)")


if __name__ == "__main__":
    main()
