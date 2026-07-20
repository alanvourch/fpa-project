"""Chart generation for the README.

Reads the pipeline's own outputs (output/variance_table.csv, output/forecast.csv)
and writes the three PNGs in docs/. Committed so the charts are reproducible the
same way every report in this repo is: re-run the pipeline, re-run this script,
same images. Never reads data/ground_truth.md.

Charts:
  1. docs/variance_bridge_2025.png  - FY2025 group net result, budget-to-actual
     waterfall. The conventional FP&A variance walk: anchors at budget and
     actual, one block per named driver, one honest block for material items
     with no documented driver, a residual block for everything below
     materiality. Reconciles exactly (asserted).
  2. docs/variance_highlights.png   - all material variances as P&L impact
     (favorable always right, unfavorable always left), hatched when no
     documented driver exists.
  3. docs/forecast_outlook.png      - Q3 2026 revenue vs total costs by month,
     with the normalized same-month-last-year revenue as a reference marker.

Colors follow a validated palette (CVD-checked): anchors #2a78d6, favorable
#0ca30c, unfavorable #d03b3b; every block carries a direct value label so color
is never the only channel.

Run: .venv/Scripts/python.exe make_charts.py
"""

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd

VARIANCE_TABLE_PATH = "output/variance_table.csv"
FORECAST_PATH = "output/forecast.csv"

BRIDGE_PNG = "docs/variance_bridge_2025.png"
HIGHLIGHTS_PNG = "docs/variance_highlights.png"
FORECAST_PNG = "docs/forecast_outlook.png"

# Palette (light surface #fcfcfb; validated for CVD separation and contrast)
SURFACE = "#fcfcfb"
ANCHOR = "#2a78d6"      # budget/actual anchor bars
FAVORABLE = "#0ca30c"
UNFAVORABLE = "#d03b3b"
FAVORABLE_INK = "#006300"    # tone-on-tone hatch ink
UNFAVORABLE_INK = "#8f2424"
COSTS = "#eb6834"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Segoe UI", "DejaVu Sans", "Arial"],
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE,
    "axes.edgecolor": BASELINE,
    "axes.labelcolor": INK_2,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "text.color": INK,
    "axes.grid": False,
    "svg.fonttype": "none",
})


def load_variance_table():
    v = pd.read_csv(VARIANCE_TABLE_PATH)
    v["materiality"] = v["materiality"].fillna("")
    v["evidence_notes"] = v["evidence_notes"].fillna("")
    v["is_cost"] = v["line_item"] != "Revenue"
    # P&L impact: favorable is positive regardless of line type
    v["impact"] = v.apply(
        lambda r: -r["variance_eur"] if r["is_cost"] else r["variance_eur"], axis=1)
    return v


def style_axes(ax):
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.tick_params(length=0)


def fig_titles(fig, title, subtitle, top):
    """Figure-level title + muted subtitle, left-aligned, with reserved headroom
    so they never collide with the axes."""
    fig.text(0.02, 0.985, title, fontsize=15, fontweight="bold", color=INK,
             ha="left", va="top")
    fig.text(0.02, 0.985 - 0.033, subtitle, fontsize=8.5, color=MUTED,
             ha="left", va="top")
    fig.subplots_adjust(top=top)


# ---------------------------------------------------------------- chart 1


def bridge_chart(v):
    y = v[v["month"].str.startswith("2025")].copy()
    err = y["suspected_data_error"]
    # The suspected data-entry row (Brand Events revenue 2025-11) is held at
    # budget on both sides pending correction at source: zero variance
    # contribution, budget total stays complete.
    y.loc[err, "impact"] = 0.0

    sign = y["is_cost"].map({True: -1, False: 1})
    budget_net = (y["budget"] * sign).sum()

    falcon = y.loc[y["evidence_notes"].str.contains("N11"), "impact"].sum()
    fx = y.loc[y["evidence_notes"].str.contains("N08"), "impact"].sum()
    savings = y.loc[y["evidence_notes"].str.contains("N12"), "impact"].sum()
    unexplained_mask = (y["materiality"] != "") & (y["evidence_notes"] == "") & (~err)
    unexplained = y.loc[unexplained_mask, "impact"].sum()
    other = y.loc[(y["materiality"] == "") & (~err), "impact"].sum()
    actual_net = budget_net + y["impact"].sum()

    deltas = [
        ("Falcon project\noverrun (COGS)", falcon, False),
        ("FX on USD\ncontract (revenue)", fx, False),
        ("Corp. Events savings\nprogramme (opex)", savings, False),
        (f"Routed to analyst\n(no documented note),\nnet of {unexplained_mask.sum()} items", unexplained, True),
        ("All other,\nbelow materiality", other, False),
    ]
    recon = budget_net + sum(d[1] for d in deltas)
    assert abs(recon - actual_net) < 1e-6, "bridge does not reconcile"

    fig, ax = plt.subplots(figsize=(10.5, 6.2), dpi=150)

    labels = ["FY2025 budget\nnet result"] + [d[0] for d in deltas] + ["FY2025 actual\nnet result"]
    n = len(labels)

    running = budget_net
    lo = hi = budget_net
    bars = []  # (x, bottom, height, color, hatch_ink or None)
    bars.append((0, 0, budget_net, ANCHOR, None))
    for i, (_, value, hatched) in enumerate(deltas, start=1):
        bottom = min(running, running + value)
        height = abs(value)
        color = FAVORABLE if value >= 0 else UNFAVORABLE
        ink = (FAVORABLE_INK if value >= 0 else UNFAVORABLE_INK) if hatched else None
        bars.append((i, bottom, height, color, ink))
        running += value
        lo, hi = min(lo, running), max(hi, running)
    bars.append((n - 1, 0, actual_net, ANCHOR, None))

    # Zoomed y-window: the variance blocks are the story and would vanish on a
    # zero-based axis; every bar carries its value label, so nothing is implied
    # by bar length alone.
    pad = (hi - lo) * 0.45
    y0, y1 = lo - pad, hi + pad * 0.9

    for x, bottom, height, color, hatch_ink in bars:
        kwargs = {}
        if hatch_ink:
            kwargs = {"hatch": "///", "edgecolor": hatch_ink, "linewidth": 0}
        ax.bar(x, height, bottom=bottom, width=0.62, color=color, zorder=3, **kwargs)

    # connectors between consecutive running levels
    running = budget_net
    levels = [budget_net]
    for _, value, _ in deltas:
        running += value
        levels.append(running)
    for i, level in enumerate(levels):
        ax.plot([i + 0.31, i + 1 - 0.31], [level, level],
                color=BASELINE, linewidth=1, zorder=2)

    # direct labels: totals in EURm on anchors, signed EURk on deltas
    ax.text(0, budget_net + (y1 - y0) * 0.03, f"EUR{budget_net / 1e6:,.1f}M",
            ha="center", fontsize=10.5, fontweight="bold", color=INK)
    ax.text(n - 1, actual_net + (y1 - y0) * 0.03, f"EUR{actual_net / 1e6:,.1f}M",
            ha="center", fontsize=10.5, fontweight="bold", color=INK)
    for i, (_, value, _) in enumerate(deltas, start=1):
        top = max(levels[i - 1], levels[i])
        ax.text(i, top + (y1 - y0) * 0.03, f"{value / 1e3:+,.0f}k",
                ha="center", fontsize=10, color=INK_2)

    ax.set_ylim(y0, y1)
    ax.set_xticks(range(n))
    ax.set_xticklabels(labels, fontsize=9, color=INK_2)
    ax.set_yticks([])
    style_axes(ax)
    ax.spines["left"].set_visible(False)

    fig_titles(
        fig,
        "FY2025 net result: budget to actual",
        "EventCo group, EUR. Green favorable, red unfavorable; the hatched block groups "
        "material variances with no documented note, routed to the analyst.\n"
        "Y-axis zoomed to the variance range; every bar is value-labeled. Brand Events "
        "Nov-2025 revenue held at budget pending correction of a suspected data entry error.",
        top=0.84,
    )
    fig.savefig(BRIDGE_PNG, bbox_inches="tight")
    plt.close(fig)
    print(f"Wrote {BRIDGE_PNG} (budget {budget_net:,.0f} -> actual {actual_net:,.0f}, reconciled)")


# ---------------------------------------------------------------- chart 2


def material_items(v):
    """Reconstruct the variance report's material items from the table:
    contiguous episode-flagged runs per BU/line aggregate; singles stand alone."""
    items = []
    flagged = v[v["materiality"] != ""].copy()
    flagged["period"] = pd.PeriodIndex(flagged["month"], freq="M")
    for (bu, line), g in flagged.groupby(["business_unit", "line_item"]):
        g = g.sort_values("period")
        ep = g[g["materiality"] == "episode"]
        if not ep.empty:
            run = [ep.iloc[0]]
            for _, row in ep.iloc[1:].iterrows():
                if (row["period"] - run[-1]["period"]).n == 1:
                    run.append(row)
                else:
                    items.append(_episode_item(bu, line, run))
                    run = [row]
            items.append(_episode_item(bu, line, run))
        for _, row in g[g["materiality"] == "single"].iterrows():
            items.append({
                "label": f"{bu} {line} ({row['month']})",
                "impact": row["impact"],
                "grounded": bool(row["evidence_notes"]),
            })
    return items


def _episode_item(bu, line, run):
    seg = pd.DataFrame(run)
    return {
        "label": f"{bu} {line} ({run[0]['month']}..{run[-1]['month']})",
        "impact": seg["impact"].sum(),
        "grounded": bool(seg["evidence_notes"].str.cat()),
    }


def highlights_chart(v):
    items = material_items(v)
    assert len(items) == 20, f"expected 20 material items, got {len(items)}"
    items.sort(key=lambda x: abs(x["impact"]))

    fig, ax = plt.subplots(figsize=(10.5, 7.5), dpi=150)
    for i, item in enumerate(items):
        value = item["impact"] / 1e3
        color = FAVORABLE if value >= 0 else UNFAVORABLE
        kwargs = {}
        if not item["grounded"]:
            ink = FAVORABLE_INK if value >= 0 else UNFAVORABLE_INK
            kwargs = {"hatch": "///", "edgecolor": ink, "linewidth": 0}
        ax.barh(i, value, height=0.62, color=color, zorder=3, **kwargs)

    ax.axvline(0, color=BASELINE, linewidth=1, zorder=2)
    ax.set_yticks(range(len(items)))
    ax.set_yticklabels([it["label"] for it in items], fontsize=8.5, color=INK_2)
    ax.set_xlabel("P&L impact vs budget (EUR thousands); favorable to the right",
                  fontsize=9.5)
    ax.grid(axis="x", color=GRID, linewidth=1, zorder=0)
    ax.set_axisbelow(True)
    style_axes(ax)
    ax.spines["left"].set_visible(False)

    handles = [
        plt.Rectangle((0, 0), 1, 1, color=FAVORABLE),
        plt.Rectangle((0, 0), 1, 1, color=UNFAVORABLE),
        plt.Rectangle((0, 0), 1, 1, facecolor=SURFACE, hatch="///",
                      edgecolor=INK_2, linewidth=0),
        plt.Rectangle((0, 0), 1, 1, facecolor=SURFACE, edgecolor=INK_2,
                      linewidth=1),
    ]
    ax.legend(handles, ["Favorable", "Unfavorable", "No documented note: analyst follow-up",
                        "Grounded in cited evidence (solid fill)"],
              loc="lower left", frameon=False, fontsize=8.5)

    fig_titles(
        fig,
        "Material budget variances, 2024-2026",
        "All 20 items that met materiality, as P&L impact. Hatched bars have no "
        "corroborating business note: they went to the FP&A analyst as follow-ups "
        "instead of being given an invented cause.",
        top=0.90,
    )
    fig.savefig(HIGHLIGHTS_PNG, bbox_inches="tight")
    plt.close(fig)
    print(f"Wrote {HIGHLIGHTS_PNG} ({len(items)} material items)")


# ---------------------------------------------------------------- chart 3


def forecast_chart():
    fc = pd.read_csv(FORECAST_PATH)
    months = sorted(fc["month"].unique())
    rev = fc[fc["line_item"] == "Revenue"].groupby("month")[["forecast", "base_value"]].sum()
    costs = fc[fc["line_item"] != "Revenue"].groupby("month")["forecast"].sum()
    net = rev["forecast"].sum() - costs.sum()
    margin = net / rev["forecast"].sum()

    x = range(len(months))
    w = 0.36
    fig, ax = plt.subplots(figsize=(9, 5.4), dpi=150)
    ax.bar([i - w / 2 for i in x], rev.loc[months, "forecast"] / 1e6, width=w,
           color=ANCHOR, zorder=3, label="Revenue (forecast)")
    ax.bar([i + w / 2 for i in x], costs.loc[months] / 1e6, width=w,
           color=COSTS, zorder=3, label="Total costs (forecast)")
    ax.scatter([i - w / 2 for i in x], rev.loc[months, "base_value"] / 1e6,
               marker="D", s=42, color=MUTED, edgecolor=SURFACE, linewidth=1.5,
               zorder=4, label="Revenue same month last year (normalized)")

    for i, m in enumerate(months):
        ax.text(i - w / 2, rev.loc[m, "forecast"] / 1e6 + 0.15,
                f"{rev.loc[m, 'forecast'] / 1e6:,.1f}", ha="center",
                fontsize=9.5, color=INK)

    ax.set_xticks(list(x))
    ax.set_xticklabels([pd.Period(m).strftime("%b %Y") for m in months],
                       fontsize=10, color=INK_2)
    ax.set_ylabel("EUR millions", fontsize=9.5)
    ax.grid(axis="y", color=GRID, linewidth=1, zorder=0)
    ax.set_axisbelow(True)
    style_axes(ax)
    ax.legend(loc="upper left", frameon=False, fontsize=9)

    fig_titles(
        fig,
        "Rolling forecast: Q3 2026",
        f"Seasonal base x median year-over-year growth, one-offs excluded from the base. "
        f"Quarter net result EUR{net / 1e6:,.1f}M, a {margin:.1%} margin.",
        top=0.86,
    )
    fig.savefig(FORECAST_PNG, bbox_inches="tight")
    plt.close(fig)
    print(f"Wrote {FORECAST_PNG} (net EUR{net / 1e6:,.1f}M, margin {margin:.1%})")


def main():
    v = load_variance_table()
    bridge_chart(v)
    highlights_chart(v)
    forecast_chart()


if __name__ == "__main__":
    main()
