"""Build the deployable showcase site into showcase/_site/.

Assembles everything the live page needs from the repo's canonical artifacts,
so each document exists exactly once in version control:

  _site/index.html                  <- showcase/index.html, verbatim
  _site/assets/                     <- charts (docs/), one-pager preview
                                       (showcase/), the four BU PDFs and the
                                       variance/forecast data tables
                                       (output/)
  _site/reports/<name>.html         <- the six generated reports, converted
                                       from output/*.md with the same look as
                                       the main page and a back link. Long
                                       explanation/reason tables are rendered
                                       as a card list instead of a cramped
                                       wide table, and the report's own chart
                                       (if any) is inlined near the top.

Served from the same origin, the PDFs open in the browser's viewer instead of
forcing a download, and the reports are readable pages rather than raw
markdown on GitHub.

Deploy: the gh-pages branch of this repository holds the contents of _site/
verbatim (plus a .nojekyll marker). To redeploy, rebuild, copy _site/ over
a checkout of gh-pages, commit and push; GitHub Pages publishes it at
https://alanvourch.com/fpa-project/.

Run: .venv/Scripts/python.exe showcase/build_site.py
"""

import sys
import html
import re
import shutil
from pathlib import Path

import fitz  # PyMuPDF
import markdown

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "showcase" / "_site"
sys.path.insert(0, str(ROOT / "agents"))
from release_gate import verify_manifest
from commentary_facts import build_facts
import json
import pandas as pd

ASSETS = [
    ROOT / "docs" / "variance_bridge_2025.png",
    ROOT / "docs" / "variance_highlights.png",
    ROOT / "docs" / "variance_history.png",
    ROOT / "docs" / "forecast_outlook.png",
    ROOT / "docs" / "og.png",
    ROOT / "output" / "bu_reports" / "brand_events.pdf",
    ROOT / "output" / "bu_reports" / "corporate_events.pdf",
    ROOT / "output" / "bu_reports" / "digital_influence.pdf",
    ROOT / "output" / "bu_reports" / "government_institutions.pdf",
    ROOT / "output" / "variance_table.csv",
    ROOT / "output" / "forecast.csv",
    ROOT / "output" / "forecast_backtest.csv",
    ROOT / "output" / "reporting_adjustments.csv",
    ROOT / "output" / "reporting_bridge.csv",
]

# Rendered from the PDF at build time, not committed as a static image: a
# hand-taken screenshot silently goes stale the moment the PDF it was taken
# from regenerates with different content (this bit us once already).
ONEPAGER_PREVIEW_SRC = ROOT / "output" / "bu_reports" / "brand_events.pdf"
ONEPAGER_PREVIEW_NAME = "brand_events_onepager.png"

# (source markdown, page title)
REPORTS = [
    ("executive_summary.md", "Executive summary"),
    ("board_pack.md", "Board pack (draft, pending sign-off)"),
    ("variance_report.md", "Variance analysis"),
    ("forecast_report.md", "Rolling forecast"),
    ("data_quality_report.md", "Data quality report"),
    ("qa_report.md", "QA review"),
]

# Report-level chart to inline, and the heading text to insert it before
# (None = insert right after the opening paragraph, before the first
# section heading).
REPORT_CHARTS = {
    "executive_summary.md": (
        "variance_bridge_2025.png",
        "FY2025 operating result waterfall from budget to provisional, with named "
        "variance drivers and a hatched block for items routed to the analyst",
        None,
    ),
    "variance_report.md": (
        "variance_highlights.png",
        "FY2025 monthly items and multi-month episodes, with separate evidence, analyst and unresolved status",
        "Material variances",
    ),
    "forecast_report.md": (
        "forecast_outlook.png",
        "Q3 2026 forecast: gross margin against staff costs and overheads by month, with prior-year reference",
        "Forecast by BU and line item",
    ),
}

# Reports that also link a raw data export next to the doc-note, so a reader
# can pull the full table into Excel/Sheets instead of scrolling a webpage.
REPORT_DOWNLOADS = {
    "variance_report.md": ("variance_table.csv", "the full 1,320-row variance grain"),
    "forecast_report.md": ("forecast.csv", "the full 132-row forecast grain"),
}

PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} &middot; EventCo budget vs actual pack</title>
<style>
  * {{ box-sizing: border-box; margin: 0; }}
  body {{
    background: #fcfcfb; color: #171715;
    font: 15.5px/1.65 "Segoe UI", system-ui, -apple-system, "Helvetica Neue", Arial, sans-serif;
  }}
  .wrap {{ max-width: 880px; margin: 0 auto; padding: 40px 24px 80px; }}
  .back {{
    display: inline-block; margin-bottom: 26px; font-size: 14px; font-weight: 600;
    color: #1d5aa6; text-decoration: none;
  }}
  .back:hover {{ text-decoration: underline; }}
  .doc-note {{
    font-size: 13px; color: #85837d; border: 1px solid #e5e4dd; background: #fff;
    border-radius: 8px; padding: 10px 14px; margin-bottom: 30px;
  }}
  .doc-note .dl {{ display: block; margin-top: 6px; font-weight: 600; color: #1d5aa6; text-decoration: none; }}
  .doc-note .dl:hover {{ text-decoration: underline; }}
  h1 {{ font-size: 27px; line-height: 1.2; margin: 18px 0 12px; letter-spacing: -0.01em; }}
  h2 {{ font-size: 20px; margin: 30px 0 10px; }}
  h3 {{ font-size: 16.5px; margin: 22px 0 8px; }}
  p, li {{ color: #4f4e4a; margin-bottom: 10px; }}
  ul, ol {{ padding-left: 22px; margin-bottom: 12px; }}
  blockquote {{ border-left: 3px solid #2a78d6; padding: 4px 0 4px 16px; margin: 14px 0; }}
  blockquote p {{ color: #171715; }}
  code {{ font: 13px Consolas, "Cascadia Mono", Menlo, monospace; background: #f0efe9; padding: 1px 5px; border-radius: 4px; }}
  .tablewrap {{ overflow-x: auto; margin: 14px 0; border: 1px solid #e5e4dd; border-radius: 8px; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 13px; background: #fff; }}
  th, td {{ padding: 7px 10px; border-bottom: 1px solid #e5e4dd; text-align: left; vertical-align: top; }}
  th {{ color: #85837d; font-weight: 600; white-space: nowrap; }}
  tr:last-child td {{ border-bottom: none; }}
  hr {{ border: none; border-top: 1px solid #e5e4dd; margin: 26px 0; }}
  a {{ color: #1d5aa6; }}
  .report-chart {{ margin: 18px 0 24px; }}
  .report-chart img {{ width: 100%; height: auto; border: 1px solid #e5e4dd; border-radius: 10px; }}

  /* card list: replaces wide tables whose last column is long free text */
  .vcards {{ display: flex; flex-direction: column; gap: 10px; margin: 14px 0 20px; }}
  .vcard {{ border: 1px solid #e5e4dd; background: #fff; border-radius: 10px; padding: 14px 16px; }}
  .vcard-meta {{ display: flex; flex-wrap: wrap; gap: 6px 12px; align-items: center; font-size: 12.5px; color: #85837d; margin-bottom: 8px; }}
  .vcard-meta b {{ color: #171715; font-size: 13.5px; }}
  .vc-badge {{ display: inline-block; font-weight: 700; font-size: 11px; letter-spacing: .02em; border-radius: 5px; padding: 1px 7px; }}
  .vc-badge.f {{ background: #e6f4e6; color: #0a7d0a; }}
  .vc-badge.u {{ background: #fbeaea; color: #a12626; }}
  .vcard-text {{ color: #4f4e4a; margin-bottom: 0; }}
  .vcard-evidence {{ margin-top: 6px; font-size: 12.5px; color: #85837d; margin-bottom: 0; }}
</style>
</head>
<body>
<div class="wrap">
  <a class="back" href="../index.html">&larr; Back to the demo</a>
  <div class="doc-note">Synthetic case study. As of 30 June 2026. Provisional reporting scenario, pending human review.{download}</div>
{body}
</div>
</body>
</html>
"""

TABLE_RE = re.compile(
    r"^\|.+\|[ \t]*\n\|[ \t:|-]+\|[ \t]*\n(?:\|.*\|[ \t]*\n?)+",
    re.MULTILINE,
)


def _split_row(line):
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [c.strip() for c in line.split("|")]


def _render_cards(headers, rows):
    """A wide table whose last column is long free-text prose (an
    explanation or a normalization reason) reads far better as a stack of
    cards than as a cramped table column, especially on a narrow screen."""
    idx = {h: i for i, h in enumerate(headers)}
    text_col = "Explanation" if "Explanation" in idx else "Reason"
    meta_cols = [h for h in headers if h not in (text_col, "Evidence")]
    if "Variance EUR" in idx:
        # Actual/Budget are redundant with Variance EUR/% for a quick scan;
        # still available in full in the CSV export next to the doc-note.
        meta_cols = [h for h in meta_cols if h not in ("Actual", "Budget", "Provisional actual", "Budget comparator")]
    has_evidence = "Evidence" in idx

    out = ['<div class="vcards">']
    for r in rows:
        meta_bits = []
        for h in meta_cols:
            val = html.escape(r[idx[h]])
            if h == "F/U" and val in ("F", "U"):
                cls = "f" if val == "F" else "u"
                label = "Favorable" if val == "F" else "Unfavorable"
                meta_bits.append(f'<span class="vc-badge {cls}">{label}</span>')
            elif h in ("Raw actual", "Source actual", "Provisional input", "Used in history"):
                meta_bits.append(f"{html.escape(h)}: <b>{val}</b>")
            elif h in ("Variance EUR", "Variance %"):
                meta_bits.append(f"<b>{val}</b>")
            else:
                meta_bits.append(val)
        out.append('<div class="vcard">')
        out.append(f'<div class="vcard-meta">{" &middot; ".join(meta_bits)}</div>')
        out.append(f'<p class="vcard-text">{html.escape(r[idx[text_col]])}</p>')
        if has_evidence:
            ev = r[idx["Evidence"]].strip()
            if ev and ev != "-":
                out.append(f'<p class="vcard-evidence">Evidence: {html.escape(ev)}</p>')
        out.append("</div>")
    out.append("</div>")
    return "\n" + "\n".join(out) + "\n\n"


def _cardify_long_tables(text):
    def replace(m):
        lines = m.group(0).rstrip("\n").split("\n")
        headers = _split_row(lines[0])
        if "Explanation" not in headers and "Reason" not in headers:
            return m.group(0)
        rows = [_split_row(l) for l in lines[2:] if l.strip()]
        return _render_cards(headers, rows)

    return TABLE_RE.sub(replace, text)


def _insert_chart(body, asset_name, alt, before_heading):
    img_html = f'<div class="report-chart"><img src="../assets/{asset_name}" alt="{html.escape(alt)}"></div>\n'
    idx = body.find(f"<h2>{before_heading}") if before_heading else -1
    if idx == -1:
        idx = body.find("<h2")
    if idx == -1:
        return body + img_html
    return body[:idx] + img_html + body[idx:]


def convert_report(md_path):
    text = md_path.read_text(encoding="utf-8")
    text = _cardify_long_tables(text)
    body = markdown.markdown(text, extensions=["tables"])
    body = re.sub(r'href="bu_reports/([^"/]+)\.md"', r'href="../assets/\1.pdf"', body)
    # Wide report tables scroll inside their own container instead of
    # stretching the page.
    body = body.replace("<table>", '<div class="tablewrap"><table>')
    body = body.replace("</table>", "</table></div>")
    chart = REPORT_CHARTS.get(md_path.name)
    if chart:
        asset_name, alt, before_heading = chart
        body = _insert_chart(body, asset_name, alt, before_heading)
    return body


def render_onepager_preview(pdf_path, out_path, zoom=2.0):
    doc = fitz.open(pdf_path)
    page = doc[0]
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
    pix.save(out_path)
    doc.close()


def main():
    verify_manifest()
    if SITE.exists():
        if SITE.resolve() != (ROOT / "showcase" / "_site").resolve():
            raise ValueError("Unexpected site output directory")
        shutil.rmtree(SITE)
    (SITE / "assets").mkdir(parents=True)
    (SITE / "reports").mkdir()

    template = (ROOT / "showcase" / "index.html").read_text(encoding="utf-8")
    facts = {f['id']: f for f in build_facts()}
    million = lambda v: f"EUR{abs(v)/1e6:,.1f}M"
    thousand = lambda v: f"EUR{abs(v)/1000:,.0f}k"
    bt = pd.read_csv(ROOT / 'output/forecast_backtest.csv')
    values = dict(FY_BUDGET=million(facts['fy_budget']['amount']), FY_ACTUAL=million(facts['fy_actual']['amount']),
                  FY_GAP=million(facts['fy_gap']['amount']), BRAND_LOSS=thousand(facts['brand_loss']['amount']),
                  Q3_BILLINGS=million(facts['q3_bills_GROUP']['amount']), Q3_RESULT=thousand(facts['q3_op_GROUP']['amount']),
                  AUG_LOSS=thousand(facts['month_2026-08']['amount']), GROWTH_MAE=thousand(bt.absolute_error.mean()),
                  NAIVE_MAE=thousand(bt.naive_error.mean()), MATERIAL_COUNT=str(len(json.loads((ROOT/'output/material_items.json').read_text()))))
    for key,value in values.items():
        template = template.replace('{{'+key+'}}', html.escape(value))
    if re.search(r'\{\{[A-Z_]+\}\}', template):
        raise ValueError('Unresolved landing-page fact')
    (SITE / "index.html").write_text(template,encoding="utf-8")
    for src in ASSETS:
        shutil.copyfile(src, SITE / "assets" / src.name)
    render_onepager_preview(ONEPAGER_PREVIEW_SRC, SITE / "assets" / ONEPAGER_PREVIEW_NAME)
    print(f"assets/{ONEPAGER_PREVIEW_NAME} <- rendered from "
          f"{ONEPAGER_PREVIEW_SRC.relative_to(ROOT).as_posix()}")
    for name, title in REPORTS:
        src = ROOT / "output" / name
        download = ""
        if name in REPORT_DOWNLOADS:
            fname, desc = REPORT_DOWNLOADS[name]
            download = f' <a class="dl" href="../assets/{fname}">Download {fname} &rarr; {desc}, open in Excel or Sheets</a>'
        html_out = PAGE_TEMPLATE.format(title=title, body=convert_report(src), download=download)
        out = SITE / "reports" / (src.stem + ".html")
        out.write_text(html_out, encoding="utf-8")
        print(f"reports/{out.name} <- output/{name}")

    print(f"Site built in {SITE} "
          f"({sum(1 for _ in SITE.rglob('*') if _.is_file())} files)")


if __name__ == "__main__":
    main()
