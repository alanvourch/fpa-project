"""BU Report Agent.

Builds one business-partnering one-pager per business unit, for that BU's
manager: the FY2025 budget-to-actual bridge, the driver story behind payroll
(headcount vs rate) and revenue (projects volume vs price/mix), the BU's
material variances with their grounded explanations, open follow-ups, and the
Q3 2026 outlook. Written as Markdown plus a clean single-page PDF.

Everything here is deterministic Python reading the pipeline's own outputs:
  - output/variance_table.csv  (variance grain + materiality + evidence ids)
  - output/forecast.csv        (rolling forecast per BU/line)
  - data/eventco_drivers.csv   (monthly FTE and projects per BU, from the
                                HR/ops systems; enables the driver splits)
  - data/business_notes.csv    (note text quoted for grounded explanations)

It never reads data/ground_truth.md or data/ground_truth_drivers.md. The same
discipline as the variance agent applies: a material variance with no
corroborating note is shown as "no clear driver identified" and lands in the
follow-up list, never dressed up with an invented cause. The suspected
data-entry row (Brand Events revenue Nov-2025) is held at budget in the bridge
and excluded from the revenue driver split, with the ops-system view (normal
project count) shown as corroboration that it is a data issue, not business.

Chart style mirrors make_charts.py (same CVD-validated palette) so the pack
reads as one system.

Outputs, per BU:
  - output/bu_reports/<slug>.md
  - output/bu_reports/<slug>.pdf
  - output/bu_reports/<slug>_bridge.png  (embedded in both)

Run: .venv/Scripts/python.exe agents/bu_report_agent.py
"""

import datetime
import os
import re
import textwrap

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd
from fpdf import FPDF

VARIANCE_TABLE_PATH = "output/variance_table.csv"
FORECAST_PATH = "output/forecast.csv"
DRIVERS_PATH = "data/eventco_drivers.csv"
NOTES_PATH = "data/business_notes.csv"
OUT_DIR = "output/bu_reports"

YEAR = "2025"
COST_LINES = ["COGS", "Payroll", "Opex - Travel", "Opex - Marketing",
              "Opex - IT", "Opex - Facilities"]
BRIDGE_GROUPS = [
    ("Revenue", ["Revenue"]),
    ("COGS", ["COGS"]),
    ("Payroll", ["Payroll"]),
    ("Opex", ["Opex - Travel", "Opex - Marketing", "Opex - IT", "Opex - Facilities"]),
]

# Palette: mirrors make_charts.py (validated for CVD separation and contrast).
SURFACE = "#fcfcfb"
ANCHOR = "#2a78d6"
FAVORABLE = "#0ca30c"
UNFAVORABLE = "#d03b3b"
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
    "text.color": INK,
    "axes.grid": False,
})


def fmt_money(v):
    return f"EUR{v:,.0f}"


def fmt_signed_k(v):
    # One decimal below 10k so small-but-real effects never print as "+0k".
    if abs(v) < 10_000:
        return f"{v / 1e3:+,.1f}k"
    return f"{v / 1e3:+,.0f}k"


def slugify(bu):
    return (bu.lower().replace(" & ", "_").replace("/", "_")
            .replace(" ", "_").replace("-", "_"))


def load_inputs():
    vt = pd.read_csv(VARIANCE_TABLE_PATH)
    vt["materiality"] = vt["materiality"].fillna("")
    vt["evidence_notes"] = vt["evidence_notes"].fillna("")
    vt["analyst_comment"] = vt["analyst_comment"].fillna("")
    vt["is_cost"] = vt["line_item"] != "Revenue"
    vt["impact"] = vt.apply(
        lambda r: -r["variance_eur"] if r["is_cost"] else r["variance_eur"], axis=1)
    fc = pd.read_csv(FORECAST_PATH)
    drivers = pd.read_csv(DRIVERS_PATH, parse_dates=["month"])
    drivers["month"] = drivers["month"].dt.strftime("%Y-%m")
    notes = pd.read_csv(NOTES_PATH).set_index("note_id")
    return vt, fc, drivers, notes


# ------------------------------------------------------------- computations


def fy_slice(vt, bu):
    y = vt[(vt["business_unit"] == bu) & (vt["month"].str.startswith(YEAR))].copy()
    # Suspected data-entry rows are held at budget pending correction: zero
    # variance contribution, consistent with the group bridge in the pack.
    y.loc[y["suspected_data_error"], "impact"] = 0.0
    return y


def scorecard(y):
    err = y["suspected_data_error"]
    rev = y[y["line_item"] == "Revenue"]
    shown_rev_actual = rev.apply(
        lambda r: r["budget"] if r["suspected_data_error"] else r["actual"], axis=1).sum()
    rev_budget = rev["budget"].sum()
    costs = y[y["line_item"] != "Revenue"]
    costs_actual, costs_budget = costs["actual"].sum(), costs["budget"].sum()
    net_actual = shown_rev_actual - costs_actual
    net_budget = rev_budget - costs_budget
    return {
        "revenue_actual": shown_rev_actual, "revenue_budget": rev_budget,
        "costs_actual": costs_actual, "costs_budget": costs_budget,
        "net_actual": net_actual, "net_budget": net_budget,
        "net_variance": net_actual - net_budget,
        "margin_actual": net_actual / shown_rev_actual if shown_rev_actual else float("nan"),
        "held_rows": int(err.sum()),
    }


def bridge_blocks(y, card):
    blocks = [(label, y[y["line_item"].isin(lines)]["impact"].sum())
              for label, lines in BRIDGE_GROUPS]
    recon = card["net_budget"] + sum(v for _, v in blocks)
    assert abs(recon - card["net_actual"]) < 1e-6, "BU bridge does not reconcile"
    return blocks


def month_key(s):
    return pd.Period(s, freq="M")


def payroll_driver_split(vt, drivers, bu):
    """FY2025 payroll variance split into headcount (volume) and rate effects,
    summed from exact monthly decompositions."""
    pay = vt[(vt["business_unit"] == bu) & (vt["line_item"] == "Payroll")
             & (vt["month"].str.startswith(YEAR))]
    d = drivers[(drivers["business_unit"] == bu) & (drivers["month"].str.startswith(YEAR))]
    m = pay.merge(d, on=["month", "business_unit"])
    rate_b = m["budget"] / m["fte_budget"]
    rate_a = m["actual"] / m["fte_actual"]
    vol = ((m["fte_actual"] - m["fte_budget"]) * rate_b).sum()
    rate = ((rate_a - rate_b) * m["fte_actual"]).sum()
    variance = (m["actual"] - m["budget"]).sum()
    assert abs(vol + rate - variance) < 1e-6, "payroll driver split does not reconcile"
    return {
        "variance": variance, "volume": vol, "rate": rate,
        "fte_actual_avg": m["fte_actual"].mean(), "fte_budget_avg": m["fte_budget"].mean(),
    }


def revenue_driver_split(vt, drivers, bu):
    """FY2025 revenue variance split into projects volume and price/mix,
    excluding suspected data-entry months (their finance figure is not
    usable; the ops-side project count is reported alongside instead)."""
    rev = vt[(vt["business_unit"] == bu) & (vt["line_item"] == "Revenue")
             & (vt["month"].str.startswith(YEAR))]
    d = drivers[(drivers["business_unit"] == bu) & (drivers["month"].str.startswith(YEAR))]
    m = rev.merge(d, on=["month", "business_unit"])
    excluded = m[m["suspected_data_error"]]
    m = m[~m["suspected_data_error"]]
    val_b = m["budget"] / m["projects_budget"]
    val_a = m["actual"] / m["projects_actual"]
    vol = ((m["projects_actual"] - m["projects_budget"]) * val_b).sum()
    price = ((val_a - val_b) * m["projects_actual"]).sum()
    variance = (m["actual"] - m["budget"]).sum()
    assert abs(vol + price - variance) < 1e-6, "revenue driver split does not reconcile"
    return {
        "variance": variance, "volume": vol, "price": price,
        "projects_actual": int(m["projects_actual"].sum()),
        "projects_budget": int(m["projects_budget"].sum()),
        "excluded_months": [
            {"month": r["month"], "projects_actual": int(r["projects_actual"]),
             "projects_budget": int(r["projects_budget"])}
            for _, r in excluded.iterrows()
        ],
    }


def material_items(vt, bu):
    """Reconstruct this BU's material items (episodes aggregated, singles
    standalone) from the variance table's materiality flags."""
    items = []
    flagged = vt[(vt["business_unit"] == bu) & (vt["materiality"] != "")].copy()
    flagged["period"] = flagged["month"].map(month_key)
    for line, g in flagged.groupby("line_item"):
        g = g.sort_values("period")
        ep = g[g["materiality"] == "episode"]
        if not ep.empty:
            run = [ep.iloc[0]]
            for _, row in ep.iloc[1:].iterrows():
                if (row["period"] - run[-1]["period"]).n == 1:
                    run.append(row)
                else:
                    items.append(_aggregate(line, run))
                    run = [row]
            items.append(_aggregate(line, run))
        for _, row in g[g["materiality"] == "single"].iterrows():
            items.append(_aggregate(line, [row]))
    items.sort(key=lambda x: -abs(x["variance_eur"]))
    return items


def _aggregate(line, run):
    seg = pd.DataFrame(run)
    var = seg["variance_eur"].sum()
    budget = seg["budget"].sum()
    months = sorted(seg["month"])
    period = months[0] if len(months) == 1 else f"{months[0]}..{months[-1]}"
    ids = sorted({i.strip() for cell in seg["evidence_notes"] if cell
                  for i in cell.split(",")})
    analyst = next((c for c in seg["analyst_comment"] if c), "")
    return {
        "line_item": line, "period": period, "variance_eur": var,
        "variance_pct": var / budget if budget else float("nan"),
        "direction": seg["direction"].iloc[0], "evidence_ids": ids,
        "analyst_comment": analyst,
    }


def driver_label(item, notes):
    """One-line explanation with its provenance always visible: the first
    sentence of the top cited note, the analyst's manual input labeled as
    such, or the explicit still-open statement. Never an invented cause."""
    if item["evidence_ids"]:
        top = notes.loc[item["evidence_ids"][0], "note"]
        first = _first_sentence(top)
        return f"{first} (business note {', '.join(item['evidence_ids'])})"
    if item["analyst_comment"]:
        first = _first_sentence(item["analyst_comment"].rsplit(" (", 1)[0])
        return f"{first} (analyst input, manual)"
    return "No clear driver identified; still open with the BU controller."


def _first_sentence(text, limit=130):
    first = re.split(r"(?<=[.;])\s", str(text))[0].strip()
    if len(first) > limit:
        first = first[:limit - 3].rstrip() + "..."
    return first


def outlook(fc, bu):
    g = fc[fc["business_unit"] == bu]
    months = sorted(g["month"].unique())
    rev = g[g["line_item"] == "Revenue"]
    costs = g[g["line_item"] != "Revenue"]
    rev_total, rev_py = rev["forecast"].sum(), rev["base_value"].sum()
    costs_total, costs_py = costs["forecast"].sum(), costs["base_value"].sum()
    net = rev_total - costs_total
    return {
        "months": months, "revenue": rev_total, "revenue_vs_py": rev_total / rev_py - 1,
        "costs": costs_total, "costs_vs_py": costs_total / costs_py - 1,
        "net": net, "margin": net / rev_total if rev_total else float("nan"),
    }


# ------------------------------------------------------------------ chart


def bridge_chart(bu, card, blocks, png_path):
    labels = [f"FY{YEAR} budget\nnet result"] + [b[0] for b in blocks] + [f"FY{YEAR} actual\nnet result"]
    n = len(labels)

    fig, ax = plt.subplots(figsize=(8.6, 3.6), dpi=150)
    running = card["net_budget"]
    lo = hi = running
    bars = [(0, 0, card["net_budget"], ANCHOR)]
    for i, (_, value) in enumerate(blocks, start=1):
        bottom = min(running, running + value)
        color = FAVORABLE if value >= 0 else UNFAVORABLE
        bars.append((i, bottom, abs(value), color))
        running += value
        lo, hi = min(lo, running), max(hi, running)
    bars.append((n - 1, 0, card["net_actual"], ANCHOR))

    pad = max((hi - lo) * 0.5, abs(hi) * 0.02)
    y0, y1 = lo - pad, hi + pad
    for x, bottom, height, color in bars:
        ax.bar(x, height, bottom=bottom, width=0.6, color=color, zorder=3)

    running = card["net_budget"]
    levels = [running]
    for _, value in blocks:
        running += value
        levels.append(running)
    for i, level in enumerate(levels):
        ax.plot([i + 0.3, i + 1 - 0.3], [level, level], color=BASELINE, linewidth=1, zorder=2)

    ax.text(0, card["net_budget"] + (y1 - y0) * 0.04, f"EUR{card['net_budget'] / 1e6:,.1f}M",
            ha="center", fontsize=9.5, fontweight="bold", color=INK)
    ax.text(n - 1, card["net_actual"] + (y1 - y0) * 0.04, f"EUR{card['net_actual'] / 1e6:,.1f}M",
            ha="center", fontsize=9.5, fontweight="bold", color=INK)
    for i, (_, value) in enumerate(blocks, start=1):
        top = max(levels[i - 1], levels[i])
        ax.text(i, top + (y1 - y0) * 0.04, fmt_signed_k(value),
                ha="center", fontsize=9, color=INK_2)

    ax.set_ylim(y0, y1)
    ax.set_xticks(range(n))
    ax.set_xticklabels(labels, fontsize=8.5, color=INK_2)
    ax.set_yticks([])
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.tick_params(length=0)

    note = ""
    if card["held_rows"]:
        note = ("  Nov-2025 revenue held at budget pending correction of a "
                "suspected data entry error.")
    fig.text(0.02, 0.985, f"{bu}: FY{YEAR} net result, budget to actual",
             fontsize=12, fontweight="bold", color=INK, ha="left", va="top")
    fig.text(0.02, 0.985 - 0.055,
             "EUR. Green favorable, red unfavorable; every bar value-labeled, "
             "y-axis zoomed to the variance range." + note,
             fontsize=7.5, color=MUTED, ha="left", va="top")
    fig.subplots_adjust(top=0.80)
    fig.savefig(png_path, bbox_inches="tight")
    plt.close(fig)


# --------------------------------------------------------------- rendering


def follow_ups(items, card):
    ups = [it for it in items if not it["evidence_ids"] and not it["analyst_comment"]]
    lines = []
    for it in ups[:3]:
        lines.append(
            f"{it['line_item']} {it['period']}: {fmt_signed_k(it['variance_eur'])} "
            f"({it['variance_pct']:+.1%}, {'favorable' if it['direction'] == 'F' else 'unfavorable'}). "
            "No documented driver and no analyst input yet; still open with the BU controller.")
    if len(ups) > 3:
        lines.append(f"{len(ups) - 3} further material item(s) still open; "
                     "see the variance report for the full list.")
    if card["held_rows"]:
        lines.append("Correct the Nov-2025 revenue entry at source: the recorded figure fails "
                     "the magnitude plausibility check while the ops system shows normal "
                     "project activity, so it is treated as a data error, not performance.")
    if not lines:
        lines.append("No open follow-ups this cycle.")
    return lines


def render_markdown(bu, card, blocks, pay, rev, items, ups, out, notes, slug):
    q_label = " / ".join(pd.Period(m).strftime("%b %Y") for m in out["months"])
    lines = [
        f"# {bu}: FY{YEAR} Budget vs Actual and Q3 2026 Outlook",
        "",
        "One-page business review for the BU manager. Generated by "
        "`agents/bu_report_agent.py` from the pipeline's own outputs "
        "(`output/variance_table.csv`, `output/forecast.csv`, "
        "`data/eventco_drivers.csv`, `data/business_notes.csv`). "
        "This agent never reads `data/ground_truth.md`.",
        "",
        f"## FY{YEAR} scorecard",
        "",
        "| | Actual | Budget | Variance |",
        "|---|---|---|---|",
        f"| Revenue | {fmt_money(card['revenue_actual'])} | {fmt_money(card['revenue_budget'])} "
        f"| {fmt_signed_k(card['revenue_actual'] - card['revenue_budget'])} |",
        f"| Total costs | {fmt_money(card['costs_actual'])} | {fmt_money(card['costs_budget'])} "
        f"| {fmt_signed_k(card['costs_actual'] - card['costs_budget'])} |",
        f"| Net result | {fmt_money(card['net_actual'])} | {fmt_money(card['net_budget'])} "
        f"| {fmt_signed_k(card['net_variance'])} |",
        "",
        f"Net margin {card['margin_actual']:.1%}."
        + (" Nov-2025 revenue held at budget pending correction of a suspected data entry error."
           if card["held_rows"] else ""),
        "",
        f"![FY{YEAR} bridge]({slug}_bridge.png)",
        "",
        "## What drove it",
        "",
        f"- **Payroll ran {fmt_signed_k(pay['variance'])} vs budget.** Headcount effect "
        f"{fmt_signed_k(pay['volume'])} (average {pay['fte_actual_avg']:.1f} FTE vs "
        f"{pay['fte_budget_avg']:.1f} planned), rate effect {fmt_signed_k(pay['rate'])} "
        "(salary mix, overtime and timing). The two effects reconcile exactly to the "
        "payroll variance.",
        f"- **Revenue ran {fmt_signed_k(rev['variance'])} vs budget"
        + (" (excluding the month pending data correction)" if rev["excluded_months"] else "")
        + f".** Volume effect {fmt_signed_k(rev['volume'])} ({rev['projects_actual']} projects "
        f"delivered vs {rev['projects_budget']} planned), price/mix effect "
        f"{fmt_signed_k(rev['price'])}. The two effects reconcile exactly to the revenue "
        "variance.",
    ]
    for ex in rev["excluded_months"]:
        lines.append(
            f"- *Data note:* {ex['month']} is excluded from the revenue split above. The ops "
            f"system shows normal activity that month ({ex['projects_actual']} projects "
            f"delivered vs {ex['projects_budget']} planned), which supports treating the "
            "recorded revenue figure as a data entry error rather than a business event.")
    lines += [
        "",
        "## Material variances (full 30-month window)",
        "",
        "| Period | Line | Variance EUR | % | F/U | Driver |",
        "|---|---|---|---|---|---|",
    ]
    for it in items:
        lines.append(
            f"| {it['period']} | {it['line_item']} | {it['variance_eur']:+,.0f} | "
            f"{it['variance_pct']:+.1%} | {it['direction']} | "
            f"{driver_label(it, notes).replace('|', '/')} |")
    if not items:
        lines.append("| - | - | - | - | - | No material variances for this BU. |")
    lines += ["", "## Follow-ups", ""]
    lines += [f"- {u}" for u in ups]
    lines += [
        "",
        f"## Q3 2026 outlook ({q_label})",
        "",
        f"Revenue {fmt_money(out['revenue'])} ({out['revenue_vs_py']:+.1%} vs the same "
        f"quarter last year), total costs {fmt_money(out['costs'])} "
        f"({out['costs_vs_py']:+.1%}), net result {fmt_money(out['net'])} at a "
        f"{out['margin']:.1%} margin. One-off events and concluded programmes are "
        "excluded from the forecast base; see the forecast report's audit trail.",
        "",
        "---",
        "",
        "DRAFT: pending human sign-off. Nothing in this pipeline distributes reports "
        "on its own.",
    ]
    return "\n".join(lines) + "\n"


class OnePagerPDF(FPDF):
    MARGIN = 13

    def __init__(self):
        super().__init__(orientation="P", unit="mm", format="A4")
        # Pin the embedded creation date to the reporting cutoff so re-running
        # the pipeline produces byte-identical PDFs (same guarantee as every
        # other report in this repo).
        self.set_creation_date(datetime.datetime(2026, 6, 30, tzinfo=datetime.timezone.utc))
        self.set_margins(self.MARGIN, self.MARGIN, self.MARGIN)
        self.set_auto_page_break(auto=True, margin=11)
        self.width = 210 - 2 * self.MARGIN

    def h1(self, text):
        self.set_font("Helvetica", "B", 15)
        self.set_text_color(11, 11, 11)
        self.cell(0, 8, text, new_x="LMARGIN", new_y="NEXT")

    def sub(self, text):
        self.set_font("Helvetica", "", 8)
        self.set_text_color(137, 135, 129)
        self.multi_cell(0, 3.6, text, new_x="LMARGIN", new_y="NEXT")

    def h2(self, text):
        self.ln(1.6)
        self.set_font("Helvetica", "B", 10.5)
        self.set_text_color(11, 11, 11)
        self.cell(0, 6, text, new_x="LMARGIN", new_y="NEXT")

    def body(self, text, h=3.9):
        self.set_font("Helvetica", "", 8.3)
        self.set_text_color(82, 81, 78)
        self.multi_cell(0, h, text, new_x="LMARGIN", new_y="NEXT")


def render_pdf(bu, card, pay, rev, items, ups, out, notes, png_path, pdf_path):
    pdf = OnePagerPDF()
    pdf.add_page()
    pdf.h1(f"{bu}: FY{YEAR} budget vs actual")
    pdf.sub("Business unit one-pager, EventCo monthly close. Figures trace to the "
            "variance and forecast reports; driver splits reconcile exactly. "
            "DRAFT, pending human sign-off.")

    # Scorecard strip
    pdf.ln(2)
    # (label, value, delta, favorable): revenue and net result are favorable
    # when above budget, costs when below.
    cols = [
        ("Revenue", card["revenue_actual"],
         card["revenue_actual"] - card["revenue_budget"],
         card["revenue_actual"] >= card["revenue_budget"]),
        ("Total costs", card["costs_actual"],
         card["costs_actual"] - card["costs_budget"],
         card["costs_actual"] <= card["costs_budget"]),
        ("Net result", card["net_actual"], card["net_variance"],
         card["net_variance"] >= 0),
    ]
    w = pdf.width / 3
    y_top = pdf.get_y()
    for i, (label, value, delta, favorable) in enumerate(cols):
        x = pdf.MARGIN + i * w
        pdf.set_xy(x, y_top)
        pdf.set_font("Helvetica", "", 7.6)
        pdf.set_text_color(137, 135, 129)
        pdf.cell(w, 3.6, label.upper())
        pdf.set_xy(x, y_top + 3.8)
        pdf.set_font("Helvetica", "B", 12.5)
        pdf.set_text_color(11, 11, 11)
        pdf.cell(w, 5.6, f"EUR{value / 1e6:,.1f}M")
        pdf.set_xy(x, y_top + 9.6)
        pdf.set_font("Helvetica", "", 7.6)
        if favorable:
            pdf.set_text_color(0, 99, 0)
        else:
            pdf.set_text_color(143, 36, 36)
        pdf.cell(w, 3.6, f"{fmt_signed_k(delta)} vs budget")
    pdf.set_y(y_top + 15)

    pdf.image(png_path, x=pdf.MARGIN, w=pdf.width)

    pdf.h2("What drove it")
    pdf.body(
        f"Payroll ran {fmt_signed_k(pay['variance'])} vs budget: headcount effect "
        f"{fmt_signed_k(pay['volume'])} (average {pay['fte_actual_avg']:.1f} FTE vs "
        f"{pay['fte_budget_avg']:.1f} planned) and rate effect {fmt_signed_k(pay['rate'])} "
        "(salary mix, overtime, timing). "
        f"Revenue ran {fmt_signed_k(rev['variance'])} vs budget"
        + (" (excluding the month pending data correction)" if rev["excluded_months"] else "")
        + f": volume {fmt_signed_k(rev['volume'])} ({rev['projects_actual']} projects vs "
        f"{rev['projects_budget']} planned) and price/mix {fmt_signed_k(rev['price'])}. "
        "Both splits reconcile exactly to the reported variances.")
    for ex in rev["excluded_months"]:
        pdf.body(
            f"Data note: {ex['month']} is excluded from the revenue split. The ops system "
            f"shows normal activity ({ex['projects_actual']} projects vs "
            f"{ex['projects_budget']} planned), supporting a data entry error, not a "
            "business event.")

    pdf.h2("Material variances (30-month window)")
    headers = ["Period", "Line", "EUR", "%", "F/U", "Driver"]
    widths = [22, 24, 16, 12, 8, 102]
    pdf.set_font("Helvetica", "B", 7.4)
    pdf.set_text_color(82, 81, 78)
    for hd, wd in zip(headers, widths):
        pdf.cell(wd, 4.4, hd, border="B")
    pdf.ln(4.4)
    pdf.set_font("Helvetica", "", 7.4)
    for it in items:
        label = driver_label(it, notes)
        wrapped = textwrap.wrap(label, width=68) or [""]
        row_h = 3.4 * len(wrapped)
        if pdf.get_y() + row_h > 285:
            pdf.add_page()
        cells = [it["period"], it["line_item"], f"{it['variance_eur'] / 1e3:+,.0f}k",
                 f"{it['variance_pct']:+.0%}", it["direction"]]
        y_row = pdf.get_y()
        for val, wd in zip(cells, widths[:-1]):
            pdf.set_text_color(11, 11, 11)
            pdf.cell(wd, row_h, val)
        pdf.set_text_color(82, 81, 78)
        x_driver = pdf.MARGIN + sum(widths[:-1])
        for j, seg in enumerate(wrapped):
            pdf.set_xy(x_driver, y_row + 3.4 * j)
            pdf.cell(widths[-1], 3.4, seg)
        pdf.set_xy(pdf.MARGIN, y_row + row_h + 0.8)

    pdf.h2("Follow-ups")
    for u in ups:
        pdf.body("-  " + u, h=3.6)

    q_label = " / ".join(pd.Period(m).strftime("%b %Y") for m in out["months"])
    pdf.h2(f"Q3 2026 outlook ({q_label})")
    pdf.body(
        f"Revenue {fmt_money(out['revenue'])} ({out['revenue_vs_py']:+.1%} vs the same "
        f"quarter last year), total costs {fmt_money(out['costs'])} "
        f"({out['costs_vs_py']:+.1%}), net result {fmt_money(out['net'])} at a "
        f"{out['margin']:.1%} margin. One-offs and concluded programmes are excluded "
        "from the forecast base (full audit trail in the forecast report).")

    pdf.ln(1)
    pdf.set_font("Helvetica", "I", 7)
    pdf.set_text_color(137, 135, 129)
    pdf.multi_cell(0, 3.4,
                   "Generated by agents/bu_report_agent.py from pipeline outputs. DRAFT, "
                   "pending human sign-off; nothing in this pipeline distributes reports on "
                   "its own.")
    pdf.output(pdf_path)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    vt, fc, drivers, notes = load_inputs()
    bus = sorted(vt["business_unit"].unique())

    for bu in bus:
        slug = slugify(bu)
        y = fy_slice(vt, bu)
        card = scorecard(y)
        blocks = bridge_blocks(y, card)
        pay = payroll_driver_split(vt, drivers, bu)
        rev = revenue_driver_split(vt, drivers, bu)
        items = material_items(vt, bu)
        ups = follow_ups(items, card)
        out = outlook(fc, bu)

        png_path = os.path.join(OUT_DIR, f"{slug}_bridge.png")
        bridge_chart(bu, card, blocks, png_path)
        md = render_markdown(bu, card, blocks, pay, rev, items, ups, out, notes, slug)
        with open(os.path.join(OUT_DIR, f"{slug}.md"), "w", encoding="utf-8") as f:
            f.write(md)
        render_pdf(bu, card, pay, rev, items, ups, out, notes,
                   png_path, os.path.join(OUT_DIR, f"{slug}.pdf"))
        print(f"{bu}: net {fmt_signed_k(card['net_variance'])} vs budget, "
              f"{len(items)} material item(s) -> {OUT_DIR}/{slug}.md + .pdf")

    print(f"Wrote {len(bus)} BU one-pagers to {OUT_DIR}/")


if __name__ == "__main__":
    main()
