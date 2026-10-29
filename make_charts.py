"""Chart generation for the README.

Reads the pipeline's own outputs (output/variance_table.csv, output/forecast.csv)
and writes the three PNGs in docs/. Committed so the charts are reproducible the
same way every report in this repo is: re-run the pipeline, re-run this script,
same images. Never reads data/ground_truth.md.

Charts:
  1. docs/variance_bridge_2025.png  - FY2025 group operating result, budget-to-actual
     waterfall. The conventional FP&A variance walk: anchors at budget and
     actual, one block per named driver, one honest block for material items
     with no documented driver, a residual block for everything below
     materiality. Reconciles exactly (asserted).
  2. docs/variance_highlights.png   - all material variances as P&L impact
     (favorable always right, unfavorable always left), hatched when no
     documented driver exists.
  3. docs/forecast_outlook.png      - Q3 2026 revenue vs total costs by month,
     with the normalized same-month-last-year revenue as a reference marker.
  4. docs/og.png                    - 1200x630 link-preview card for the case
     study page: the FY2025 headline result, computed from the same table.

Colors follow a validated palette (CVD-checked): anchors #2a78d6, favorable
#0ca30c, unfavorable #d03b3b; every block carries a direct value label so color
is never the only channel.

Run: .venv/Scripts/python.exe make_charts.py
"""

import textwrap

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd
import sys
from pathlib import Path
from matplotlib.ticker import FuncFormatter
sys.path.insert(0, str(Path(__file__).resolve().parent / "agents"))
from reporting_basis import load_reporting_table

VARIANCE_TABLE_PATH = "output/variance_table.csv"
FORECAST_PATH = "output/forecast.csv"

BRIDGE_PNG = "docs/variance_bridge_2025.png"
HIGHLIGHTS_PNG = "docs/variance_highlights.png"
FORECAST_PNG = "docs/forecast_outlook.png"
OG_PNG = "docs/og.png"

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
    v = load_reporting_table(VARIANCE_TABLE_PATH)
    v["materiality"] = v["materiality"].fillna("")
    v["evidence_notes"] = v["evidence_notes"].fillna("")
    v["analyst_comment"] = v["analyst_comment"].fillna("")
    v["is_cost"] = v["line_item"] != "Net billings"
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


def bridge_components(v):
    """FY2025 group walk from budgeted to actual operating result, as (label, value,
    hatched) blocks that reconcile exactly. Shared by the bridge chart and
    the link-preview card so both quote the same figures."""
    y = v[v["month"].str.startswith("2025")].copy()
    err = y["withheld_from_analysis"]
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
    # Everything below materiality, split so the reader can see whether the
    # residual is gross margin landing a little under plan month after month
    # or staff costs and overheads drifting: the two read very differently.
    quiet = (y["materiality"] == "") & (~err)
    margin_lines = y["line_item"].isin(["Net billings", "Cost of sales"])
    other_revenue = y.loc[quiet & margin_lines, "impact"].sum()
    other_costs = y.loc[quiet & ~margin_lines, "impact"].sum()
    actual_net = budget_net + y["impact"].sum()

    deltas = [
        ("Project overrun", falcon, False),
        ("FX billings", fx, False),
        ("Marketing Jul-Dec", savings, False),
        ("Other material items", unexplained, True),
        ("Other gross margin", other_revenue, False),
        ("Other staff / overheads", other_costs, False),
    ]
    recon = budget_net + sum(d[1] for d in deltas)
    assert abs(recon - actual_net) < 1e-6, "bridge does not reconcile"
    return budget_net, actual_net, deltas


def bridge_chart(v):
    budget_net, actual_net, deltas = bridge_components(v)

    fig, ax = plt.subplots(figsize=(12.5, 6.4), dpi=150)

    # Labels are wrapped at a fixed width so none can run into its neighbour:
    # eight slots across the axis leave about 1.4 inches each at this size.
    def wrap(text):
        return "\n".join(textwrap.wrap(text, 16))

    labels = (["FY2025 budget\noperating result"] + [wrap(d[0]) for d in deltas]
              + ["FY2025 provisional\noperating result"])
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
    y0, y1 = min(0, lo) - pad * 0.1, hi + pad * 0.9

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
    ax.set_xticklabels(labels, fontsize=10.5, color=INK_2)
    ax.axhline(0, color=INK_2, linewidth=1)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v/1e6:.1f}"))
    ax.set_ylabel("EUR millions", fontsize=10)
    style_axes(ax)
    ax.spines["left"].set_visible(False)

    fig_titles(
        fig,
        "FY2025 operating result: budget to provisional",
        "Synthetic case study. Provisional scenario includes unapproved missing-cell estimates and a November billings budget placeholder.\n"
        "Marketing attribution covers Jul-Dec only; other material items include the unexplained portions of the detected run. Zero baseline shown.",
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
    from bu_report_agent import material_items as bu_items
    items = []
    for bu in sorted(v.business_unit.unique()):
        for it in bu_items(v, bu):
            status = 'documented' if it['evidence_ids'] else ('analyst' if it['analyst_comment'] else 'unresolved')
            impact = it['variance_eur'] * (1 if it['line_item'] == 'Net billings' else -1)
            items.append(dict(label=f"{bu}: {it['line_item']} ({it['period']})", period=it['period'], impact=impact, status=status))
    def draw(path, history):
        groups = ([(f'{year} single months', [i for i in items if i['period'].startswith(year) and '..' not in i['period']]) for year in ('2024','2025','2026')]
                  if history else [('FY2025 single months', [i for i in items if i['period'].startswith('2025') and '..' not in i['period']])])
        groups += [('Multi-month episodes (cumulative; separate scale)', [i for i in items if '..' in i['period']])]
        fig, axes = plt.subplots(len(groups), 1, figsize=(13, 4+len(groups)*2.0), gridspec_kw={'height_ratios':[max(2,len(g)) for _,g in groups]})
        for ax, (title, subset) in zip(axes, groups):
            subset.sort(key=lambda it: it['impact'])
            for n, it in enumerate(subset):
                value = it['impact']/1000
                ax.barh(n, value, color=FAVORABLE if value > 0 else UNFAVORABLE,
                        hatch={'documented':'', 'analyst':'//', 'unresolved':'xx'}[it['status']], edgecolor=INK_2, linewidth=0.2)
                ax.annotate(f"{value:+,.0f}k",(value,n),xytext=(5 if value > 0 else -5,0), textcoords='offset points',
                            ha='left' if value > 0 else 'right', va='center',fontsize=9)
            ax.set_yticks(range(len(subset)),[i['label'] for i in subset],fontsize=9)
            ax.set_title(title,loc='left',fontsize=11)
            ax.axvline(0,color=BASELINE)
            ax.margins(x=0.20)
            ax.set_xlabel('P&L impact, EURk; favorable right',fontsize=9)
            style_axes(ax)
        fig.suptitle('Historical material variances as of 30 June 2026',x=.02,ha='left',fontsize=15)
        fig.text(.02,.015,'Solid: dated evidence (marketing partly documented) | //: illustrative analyst explanation | xx: unresolved. Each panel has its own scale.',fontsize=9)
        fig.tight_layout(rect=(0,.04,1,.95),h_pad=2.2)
        fig.savefig(path,bbox_inches='tight')
        plt.close(fig)
    draw(HIGHLIGHTS_PNG,False)
    draw('docs/variance_history.png',True)
    print(f'Variance rankings: FY2025 view and full-history appendix ({len(items)} items)')


# ---------------------------------------------------------------- chart 3


def forecast_chart():
    fc = pd.read_csv(FORECAST_PATH)
    months = sorted(fc["month"].unique())
    by_line = fc.groupby(["line_item", "month"])[["forecast", "base_value"]].sum()
    rev = by_line.loc["Net billings"] - by_line.loc["Cost of sales"]
    costs = fc[~fc["line_item"].isin(["Net billings", "Cost of sales"])
               ].groupby("month")["forecast"].sum()
    net = rev["forecast"].sum() - costs.sum()
    margin = net / rev["forecast"].sum()

    x = range(len(months))
    w = 0.36
    fig, ax = plt.subplots(figsize=(9, 5.4), dpi=150)
    ax.bar([i - w / 2 for i in x], rev.loc[months, "forecast"] / 1e6, width=w,
           color=ANCHOR, zorder=3, label="Gross margin (forecast)")
    ax.bar([i + w / 2 for i in x], costs.loc[months] / 1e6, width=w,
           color=COSTS, zorder=3, label="Staff costs and overheads (forecast)")
    ax.scatter([i - w / 2 for i in x], rev.loc[months, "base_value"] / 1e6,
               marker="D", s=42, color=MUTED, edgecolor=SURFACE, linewidth=1.5,
               zorder=4, label="Gross margin same month last year (provisional)")

    for i, m in enumerate(months):
        monthly_net = rev.loc[m, 'forecast'] - costs.loc[m]
        ax.text(i, max(rev.loc[m,'forecast'],costs.loc[m])/1e6+.32,
                f"Operating result {monthly_net/1000:+,.0f}k",ha='center',fontsize=9.5,fontweight='bold')
        ax.text(i - w / 2, rev.loc[m, "forecast"] / 1e6 + 0.05,
                f"{rev.loc[m, 'forecast'] / 1e6:,.1f}", ha="center",
                fontsize=9.5, color=INK)

    ax.set_ylim(0, max(rev["forecast"].max(),costs.max())/1e6+.75)
    ax.set_xticks(list(x))
    ax.set_xticklabels([pd.Period(m).strftime("%b %Y") for m in months],
                       fontsize=10, color=INK_2)
    ax.set_ylabel("EUR millions", fontsize=9.5)
    ax.grid(axis="y", color=GRID, linewidth=1, zorder=0)
    ax.set_axisbelow(True)
    style_axes(ax)
    ax.legend(loc="upper left", bbox_to_anchor=(0,-0.12), frameon=False, fontsize=9)

    fig_titles(
        fig,
        "Rolling forecast: Q3 2026",
        f"Provisional seasonal baseline; unresolved effects retained. See raw baseline and sensitivity in forecast report.\n"
        f"Quarter operating result EUR{net / 1e6:,.1f}M, {margin:.1%} of gross margin.",
        top=0.86,
    )
    fig.subplots_adjust(bottom=0.25)
    fig.savefig(FORECAST_PNG, bbox_inches="tight")
    plt.close(fig)
    print(f"Wrote {FORECAST_PNG} (net EUR{net / 1e6:,.1f}M, margin {margin:.1%})")


# ---------------------------------------------------------------- chart 4


def og_image(v):
    """Link-preview card (1200x630) for the case study page. The headline is
    computed from the variance table, never typed in, so it cannot go stale
    when the dataset regenerates."""
    budget_net, actual_net, deltas = bridge_components(v)
    gap = actual_net - budget_net
    largest = max(deltas[:3], key=lambda d: abs(d[1]))
    fig = plt.figure(figsize=(12, 6.3), dpi=100)
    fig.patch.set_facecolor(SURFACE)
    fig.text(0.06, 0.82, "ALAN VOURC'H | SYNTHETIC CASE STUDY", fontsize=14,
             color=ANCHOR, fontweight="bold", va="top")
    fig.text(0.06, 0.71, "FP&A reporting automation", fontsize=34,fontweight='bold',color=INK,va='top')
    fig.text(0.06, 0.57, "Variance analysis and a three-month forecast", fontsize=23,color=INK_2,va='top')
    fig.text(0.06, 0.40,
             f"Synthetic FY2025 provisional result: EUR{actual_net/1e6:.1f}M vs EUR{budget_net/1e6:.1f}M budget.\n"
             "Source checks, business-line reviews and explicit forecast assumptions.\n"
             "Includes unapproved estimates and a billings placeholder; pending review.",
             fontsize=16,color=INK_2,va='top',linespacing=1.6)
    fig.add_artist(plt.Line2D([0.06, 0.94], [0.21, 0.21], color=GRID, linewidth=1.2))
    fig.text(0.06, 0.15, "Alan Vourc'h   |   alanvourch.com/fpa-project   |   FP&A and data",
             fontsize=12.5, color=MUTED, va="top")
    fig.savefig(OG_PNG, dpi=100, facecolor=SURFACE)
    plt.close(fig)
    print(f"Wrote {OG_PNG} (1200x630, FY2025 gap {gap:+,.0f})")


def main():
    v = load_variance_table()
    bridge_chart(v)
    highlights_chart(v)
    forecast_chart()
    og_image(v)


if __name__ == "__main__":
    main()
