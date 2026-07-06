"""Variance & Root-Cause Agent.

Computes Budget vs Actual variances (EUR and %) for every line item, by BU and
month, from the ingestion agent's cleaned table — never the raw file. Material
variances are then explained by searching a log of dated, BU-tagged internal
business notes (data/business_notes.csv) for corroborating evidence: numbers
can only say WHERE and HOW MUCH, so the WHY must be grounded in documented
operational context, the way a human FP&A analyst cross-references project
notes before writing commentary. When no note corroborates a material
variance, the agent says "no clear driver identified" instead of inventing a
plausible-sounding cause.

It never reads data/ground_truth.md: on real, unseen data there would be no
answer key, so every flag and explanation here has to stand on its own.

Materiality:
  - Monthly (dual threshold): |variance| >= 10% of budget AND >= EUR 20k.
    10% is a standard planning tolerance; the EUR floor (~0.25% of average
    monthly group revenue) keeps percentage-noise on tiny opex lines out of
    the report, while the % test keeps small relative wobbles on
    multi-million revenue lines out.
  - Monthly (absolute trigger): |variance| >= EUR 150k AND >= 7% of budget.
    On a large line, a EUR 150k+ miss (~2% of monthly group revenue) gets
    asked about in every board review even below the 10% tolerance. The 7%
    floor sits just above this business's routine forecast-noise band
    (revenue lines land within about +/-6% of budget in a normal month), so
    the trigger catches genuine misses without flooding the report with
    ordinary wobble on the biggest lines.
  - Sustained episodes: >= 2 consecutive months, same direction, each
    |variance| >= 8% of budget, cumulative |variance| >= EUR 40k and >= 10%
    of cumulative budget. A persistent drift can be material in aggregate
    even when no single month clears the monthly EUR floor — classic
    "creep" that monthly-only thresholds miss. One below-threshold month is
    bridged if the drift resumes in the same direction right after: a
    sustained programme doesn't switch off because one month's noise masks
    it. A direction flip or two quiet months in a row end the episode.

Rows already implausible as business events (actual >4x or <0.25x budget —
the same rule the ingestion agent uses) are excluded from the analysis and
listed separately as pending data corrections, so a fat-finger entry can
never be dressed up as a business story.

Outputs:
  - output/variance_table.csv   (full BU x month x line variance grain)
  - output/variance_report.md   (material variances + grounded explanations)

Run: .venv/Scripts/python.exe agents/variance_agent.py
"""

import re
from datetime import timedelta

import pandas as pd

CLEANED_PATH = "data/eventco_monthly_cleaned.csv"
NOTES_PATH = "data/business_notes.csv"
REPORT_PATH = "output/variance_report.md"
TABLE_PATH = "output/variance_table.csv"

# (line item, actual column, budget column, is_cost). For revenue, actual >
# budget is favorable; for cost lines the reverse.
LINE_ITEMS = [
    ("Revenue", "revenue_actual", "revenue_budget", False),
    ("COGS", "cogs_actual", "cogs_budget", True),
    ("Payroll", "payroll_actual", "payroll_budget", True),
    ("Opex - Travel", "opex_travel_actual", "opex_travel_budget", True),
    ("Opex - Marketing", "opex_marketing_actual", "opex_marketing_budget", True),
    ("Opex - IT", "opex_it_actual", "opex_it_budget", True),
    ("Opex - Facilities", "opex_facilities_actual", "opex_facilities_budget", True),
]

MATERIALITY_PCT = 0.10
MATERIALITY_EUR = 20_000
ABS_MATERIALITY_EUR = 150_000
ABS_MATERIALITY_MIN_PCT = 0.07
EPISODE_PCT = 0.08
EPISODE_MIN_MONTHS = 2
EPISODE_CUM_EUR = 40_000
EPISODE_CUM_PCT = 0.10

# Same magnitude rule as the ingestion agent: a single line landing >4x or
# <0.25x its budget is a probable data entry error, not a business event.
DATA_ERROR_RATIO_HIGH = 4.0
DATA_ERROR_RATIO_LOW = 0.25

# Evidence window around a variance period: operational notes usually either
# announce an event a few days before it hits the P&L (a savings programme, a
# scope change) or confirm it shortly after month-end close. The window is
# deliberately tight on both sides — a note written well before or well after
# the variance period is stale context for it, and citing stale notes is how
# an old, unrelated event gets wrongly blamed for a fresh variance.
EVIDENCE_LOOKBACK_DAYS = 10
EVIDENCE_LOOKAHEAD_DAYS = 20

# Line-item evidence lexicons: a note only counts as corroboration for a line
# if it actually talks about that kind of cost/revenue. Matching is
# whole-word/phrase, case-insensitive.
LEXICON = {
    "Revenue": ["revenue", "contract", "invoice", "invoiced", "billing",
                "pricing", "fx", "currency", "usd", "dollar", "exchange rate",
                "cancellation", "postponed"],
    "COGS": ["cogs", "cost overrun", "overrun", "freight", "staging",
             "supplier", "subcontract", "venue", "pass-through",
             "production cost", "external production", "scope expansion",
             "overtime"],
    "Payroll": ["payroll", "headcount", "hiring", "recruit", "salary",
                "bonus", "severance", "overtime", "parental leave",
                "temporary cover"],
    "Opex - Travel": ["travel", "flight", "hotel", "per diem"],
    "Opex - Marketing": ["marketing spend", "campaign", "media buying",
                         "agency retainer", "sponsorship", "media"],
    "Opex - IT": ["license", "server", "hardware", "software", "storage",
                  "cyber", "helpdesk", "infrastructure", "laptop"],
    "Opex - Facilities": ["office", "lease", "rent", "facilities",
                          "utilities", "landlord"],
}


def load_data():
    df = pd.read_csv(CLEANED_PATH, parse_dates=["month"])
    notes = pd.read_csv(NOTES_PATH, parse_dates=["date"])
    return df, notes


def build_variance_table(df):
    """Long-format table: one row per BU x month x line item."""
    rows = []
    for line, actual_col, budget_col, is_cost in LINE_ITEMS:
        for _, r in df.iterrows():
            actual, budget = r[actual_col], r[budget_col]
            var_eur = actual - budget
            var_pct = var_eur / budget if budget else float("nan")
            favorable = var_eur < 0 if is_cost else var_eur > 0
            ratio = actual / budget if budget else float("nan")
            rows.append({
                "month": r["month"], "business_unit": r["business_unit"],
                "line_item": line, "actual": actual, "budget": budget,
                "variance_eur": var_eur, "variance_pct": var_pct,
                "direction": "F" if favorable else "U",
                "suspected_data_error": ratio > DATA_ERROR_RATIO_HIGH or ratio < DATA_ERROR_RATIO_LOW,
            })
    return pd.DataFrame(rows).sort_values(
        ["business_unit", "line_item", "month"]).reset_index(drop=True)


def find_material_items(var_df):
    """Return (episodes, single_months): sustained multi-month episodes first,
    then standalone material months not absorbed by an episode. Suspected data
    errors are excluded from both and reported separately."""
    clean = var_df[~var_df["suspected_data_error"]]
    episodes = []
    covered = set()

    for (bu, line), g in clean.groupby(["business_unit", "line_item"]):
        g = g.sort_values("month").reset_index(drop=True)

        def flush(run):
            if len(run) < EPISODE_MIN_MONTHS:
                return
            seg = g.loc[run]
            cum_eur, cum_budget = seg["variance_eur"].sum(), seg["budget"].sum()
            if abs(cum_eur) >= EPISODE_CUM_EUR and abs(cum_eur / cum_budget) >= EPISODE_CUM_PCT:
                episodes.append({
                    "business_unit": bu, "line_item": line,
                    "months": list(seg["month"]),
                    "actual": seg["actual"].sum(), "budget": cum_budget,
                    "variance_eur": cum_eur, "variance_pct": cum_eur / cum_budget,
                    "direction": seg["direction"].iloc[0],
                })
                covered.update((bu, line, m) for m in seg["month"])

        run, bridge = [], []
        for i, r in g.iterrows():
            strong = abs(r["variance_pct"]) >= EPISODE_PCT
            same_dir = not run or g.loc[run[-1], "direction"] == r["direction"]
            if strong and same_dir:
                # a strong month right after a single quiet same-direction
                # month absorbs it: one month of noise masking a sustained
                # drift doesn't end the episode
                run += bridge + [i]
                bridge = []
            elif run and same_dir and not bridge:
                bridge = [i]  # hold; kept only if the drift resumes next month
            else:
                flush(run)
                run, bridge = ([i] if strong else []), []
        flush(run)

    abs_pct, abs_eur = clean["variance_pct"].abs(), clean["variance_eur"].abs()
    monthly_mask = (
        ~clean.apply(lambda r: (r["business_unit"], r["line_item"], r["month"]) in covered, axis=1)
        & (((abs_pct >= MATERIALITY_PCT) & (abs_eur >= MATERIALITY_EUR))
           | ((abs_eur >= ABS_MATERIALITY_EUR) & (abs_pct >= ABS_MATERIALITY_MIN_PCT)))
    )
    single_months = [
        {
            "business_unit": r["business_unit"], "line_item": r["line_item"],
            "months": [r["month"]], "actual": r["actual"], "budget": r["budget"],
            "variance_eur": r["variance_eur"], "variance_pct": r["variance_pct"],
            "direction": r["direction"],
        }
        for _, r in clean[monthly_mask].iterrows()
    ]
    return episodes, single_months


def note_matches(note, item):
    """A note corroborates a material item only if (a) it belongs to the same
    BU or is group-wide, (b) it is dated within the evidence window around the
    variance period, and (c) it talks about that line item's kind of spend."""
    if note["business_unit"] not in (item["business_unit"], "Group"):
        return []
    start = min(item["months"]) - timedelta(days=EVIDENCE_LOOKBACK_DAYS)
    end = max(item["months"]) + pd.offsets.MonthEnd(0) + timedelta(days=EVIDENCE_LOOKAHEAD_DAYS)
    if not (start <= note["date"] <= end):
        return []
    text = str(note["note"]).lower()
    return [term for term in LEXICON[item["line_item"]]
            if re.search(rf"(?<![a-z]){re.escape(term)}(?![a-z])", text)]


def attach_evidence(items, notes):
    for item in items:
        hits = []
        for _, note in notes.iterrows():
            terms = note_matches(note, item)
            if terms:
                hits.append({"note": note, "terms": terms})
        hits.sort(key=lambda h: -len(h["terms"]))
        item["evidence"] = hits[:2]
    return items


def fmt_money(v):
    return f"EUR{v:,.0f}"


def fmt_period(months):
    months = sorted(months)
    if len(months) == 1:
        return f"{months[0]:%Y-%m}"
    return f"{months[0]:%Y-%m}..{months[-1]:%Y-%m}"


def explanation_text(item):
    if item["evidence"]:
        parts = []
        for h in item["evidence"]:
            n = h["note"]
            parts.append(
                f"{n['note_id']} ({n['date']:%Y-%m-%d}, {n['business_unit']}, "
                f"{n['author_role']}): \"{n['note']}\""
            )
        return "Corroborated by the business notes log — " + " / ".join(parts)
    return ("No clear driver identified: no corroborating note found in the "
            "business log for this BU, line item and period. The variance is "
            "numerically material but unexplained — recommend follow-up with "
            "the BU controller rather than attributing a cause.")


def render_report(material, excluded, var_df):
    n_lines = var_df.groupby(["business_unit", "line_item"]).ngroups
    lines = [
        "# Variance Report — EventCo Budget vs Actual",
        "",
        "Generated by `agents/variance_agent.py` from "
        "`data/eventco_monthly_cleaned.csv` (the Data Ingestion Agent's output) "
        "and the internal business notes log `data/business_notes.csv`. This "
        "agent never reads `data/ground_truth.md`.",
        "",
        "## Method",
        "",
        "Variance = actual − budget, computed for every line item, BU and month "
        f"({n_lines} BU/line series across {var_df['month'].nunique()} months; "
        "full grain in `output/variance_table.csv`). Direction is **F** "
        "(favorable) or **U** (unfavorable): revenue above budget is favorable, "
        "cost above budget is unfavorable.",
        "",
        "**Materiality:**",
        "",
        f"- *Monthly (dual threshold):* |variance| ≥ {MATERIALITY_PCT:.0%} of "
        f"budget **and** ≥ {fmt_money(MATERIALITY_EUR)}. The % leg is a "
        "standard planning tolerance; the EUR floor (~0.25% of average "
        "monthly group revenue) keeps percentage noise on small opex lines "
        "out of the report, while the % leg keeps small relative wobbles on "
        "multi-million revenue lines out.",
        f"- *Monthly (absolute trigger):* |variance| ≥ "
        f"{fmt_money(ABS_MATERIALITY_EUR)} **and** ≥ "
        f"{ABS_MATERIALITY_MIN_PCT:.0%} of budget. On a large line, a miss "
        "of this size (~2% of monthly group revenue) warrants comment even "
        "below the 10% tolerance; the % floor sits just above the routine "
        "forecast-noise band of the biggest lines (±6% in a normal month).",
        f"- *Sustained episodes:* ≥ {EPISODE_MIN_MONTHS} consecutive months in "
        f"the same direction, each ≥ {EPISODE_PCT:.0%} off budget, with a "
        f"cumulative gap ≥ {fmt_money(EPISODE_CUM_EUR)} and ≥ "
        f"{EPISODE_CUM_PCT:.0%} of the period budget. Persistent drifts are "
        "material in aggregate even when no single month clears the monthly "
        "EUR floor. A single below-threshold month is bridged when the drift "
        "resumes in the same direction immediately after — one month of "
        "noise masking a sustained programme doesn't end the episode; a "
        "direction flip or two quiet months in a row do.",
        "",
        "**Root-cause discipline:** an explanation is only given when a dated, "
        "BU-relevant note in the business log corroborates the variance "
        "(right BU or group-wide, dated within the evidence window of "
        f"{EVIDENCE_LOOKBACK_DAYS} days before to {EVIDENCE_LOOKAHEAD_DAYS} "
        "days after the variance period, and actually about that kind of "
        "spend). Otherwise the report says **no clear driver identified** — "
        "a material number with no documented cause is a follow-up item, not "
        "a story to invent.",
        "",
        "## Excluded from analysis — suspected data entry errors",
        "",
        "Same magnitude rule as the ingestion agent (actual >4x or <0.25x "
        "budget is not a plausible business event). These rows are withheld "
        "from variance analysis and materiality testing entirely, pending "
        "correction at source — explaining them as business variances would "
        "be inventing a story about a typo.",
        "",
    ]
    if excluded:
        lines.append("| Business Unit | Line item | Month | Actual | Budget |")
        lines.append("|---|---|---|---|---|")
        for e in excluded:
            lines.append(
                f"| {e['business_unit']} | {e['line_item']} | {e['month']:%Y-%m} "
                f"| {fmt_money(e['actual'])} | {fmt_money(e['budget'])} |")
    else:
        lines.append("None found.")
    lines += [
        "",
        "## Material variances",
        "",
        "Sorted by absolute EUR impact. Period spans of more than one month "
        "are sustained episodes; Actual/Budget/Variance are cumulative over "
        "the period. Evidence cites note IDs from `data/business_notes.csv`.",
        "",
        "| Business Unit | Line item | Period | Actual | Budget | Variance EUR | Variance % | F/U | Evidence | Explanation |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for item in material:
        evidence_ids = ", ".join(h["note"]["note_id"] for h in item["evidence"]) or "—"
        explanation = explanation_text(item).replace("|", "/")
        lines.append(
            f"| {item['business_unit']} | {item['line_item']} | "
            f"{fmt_period(item['months'])} | {fmt_money(item['actual'])} | "
            f"{fmt_money(item['budget'])} | {item['variance_eur']:+,.0f} | "
            f"{item['variance_pct']:+.1%} | {item['direction']} | "
            f"{evidence_ids} | {explanation} |")
    lines += [
        "",
        "All other BU/line/month combinations are within materiality "
        "tolerance and are not individually commented; the full variance "
        "grain is in `output/variance_table.csv`.",
    ]
    return "\n".join(lines) + "\n"


def main():
    df, notes = load_data()
    var_df = build_variance_table(df)

    excluded = [
        {"business_unit": r["business_unit"], "line_item": r["line_item"],
         "month": r["month"], "actual": r["actual"], "budget": r["budget"]}
        for _, r in var_df[var_df["suspected_data_error"]].iterrows()
    ]

    episodes, single_months = find_material_items(var_df)
    material = attach_evidence(episodes + single_months, notes)
    material.sort(key=lambda x: -abs(x["variance_eur"]))

    # Mark each month-row with its materiality classification and evidence, so
    # downstream agents (Forecast) can tell one-off months from sustained
    # programmes without re-deriving the analysis.
    flag_map = {}
    for item in material:
        kind = "episode" if len(item["months"]) > 1 else "single"
        ids = ", ".join(h["note"]["note_id"] for h in item["evidence"])
        for m in item["months"]:
            flag_map[(item["business_unit"], item["line_item"], m)] = (kind, ids)
    out = var_df.copy()
    keys = list(zip(out["business_unit"], out["line_item"], out["month"]))
    out["materiality"] = [flag_map.get(k, ("", ""))[0] for k in keys]
    out["evidence_notes"] = [flag_map.get(k, ("", ""))[1] for k in keys]
    out["month"] = out["month"].dt.strftime("%Y-%m")
    out.to_csv(TABLE_PATH, index=False)

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(render_report(material, excluded, var_df))

    n_explained = sum(1 for m in material if m["evidence"])
    print(f"Variance rows computed: {len(var_df)}")
    print(f"Excluded as suspected data errors: {len(excluded)}")
    print(f"Material items: {len(material)} "
          f"({len(episodes)} episodes, {len(single_months)} single months)")
    print(f"  with grounded evidence: {n_explained}")
    print(f"  no clear driver identified: {len(material) - n_explained}")
    print(f"Wrote {TABLE_PATH} and {REPORT_PATH}")


if __name__ == "__main__":
    main()
