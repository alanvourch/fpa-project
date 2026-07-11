"""Validate the BU one-pagers (output/bu_reports/) against the pipeline's own
outputs and the project's honesty rules.

Checks, per BU:
  1. Artifacts exist: .md, .pdf (real PDF magic bytes, non-trivial size),
     _bridge.png.
  2. Scorecard figures on the page match a fresh recomputation from
     output/variance_table.csv (trap rows held at budget, same as the page).
  3. Driver splits on the page match a fresh recomputation from
     data/eventco_drivers.csv, and each split reconciles exactly to its
     line's variance before rounding.
  4. Every material item reconstructed from the variance table appears on
     its BU's page (period + line + formatted EUR), and every item without
     evidence carries the literal "No clear driver identified" language.
  5. The trap month (Production revenue 2025-11) never appears as a material
     row, and the Production page discloses the data note.
  6. Style: no em dashes, no banned buzzwords, in any .md one-pager.

Run: .venv/Scripts/python.exe tests/validate_bu_reports.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agents"))

import bu_report_agent as agent  # noqa: E402

OUT_DIR = ROOT / "output" / "bu_reports"
BUZZWORDS = ["robust", "leverage", "seamless", "streamline", "game-chang",
             "holistic", "data-driven", "cutting-edge", "synerg"]

results = []


def check(ok, msg):
    results.append((bool(ok), msg))


def main():
    vt, fc, drivers, notes = agent.load_inputs()
    bus = sorted(vt["business_unit"].unique())
    check(len(bus) == 4, f"4 BUs found in the variance table (found {len(bus)})")

    for bu in bus:
        slug = agent.slugify(bu)
        md_path, pdf_path = OUT_DIR / f"{slug}.md", OUT_DIR / f"{slug}.pdf"
        png_path = OUT_DIR / f"{slug}_bridge.png"

        ok_files = md_path.exists() and pdf_path.exists() and png_path.exists()
        check(ok_files, f"{bu}: .md, .pdf and _bridge.png all exist")
        if not ok_files:
            continue
        pdf_head = pdf_path.read_bytes()[:5]
        check(pdf_head == b"%PDF-" and pdf_path.stat().st_size > 15_000,
              f"{bu}: PDF is a real, non-trivial PDF ({pdf_path.stat().st_size:,} bytes)")
        md = md_path.read_text(encoding="utf-8")

        # 2. Scorecard recomputation
        y = agent.fy_slice(vt, bu)
        card = agent.scorecard(y)
        for label, value in [("revenue", card["revenue_actual"]),
                             ("costs", card["costs_actual"]),
                             ("net", card["net_actual"])]:
            check(agent.fmt_money(value) in md,
                  f"{bu}: FY2025 {label} figure {agent.fmt_money(value)} appears on the page")
        check(agent.fmt_signed_k(card["net_variance"]) in md,
              f"{bu}: net variance {agent.fmt_signed_k(card['net_variance'])} appears on the page")

        # 3. Driver splits: recompute, reconcile, and match the page
        pay = agent.payroll_driver_split(vt, drivers, bu)
        rev = agent.revenue_driver_split(vt, drivers, bu)
        check(abs(pay["volume"] + pay["rate"] - pay["variance"]) < 1e-6,
              f"{bu}: payroll split reconciles exactly before rounding")
        check(abs(rev["volume"] + rev["price"] - rev["variance"]) < 1e-6,
              f"{bu}: revenue split reconciles exactly before rounding")
        for label, value in [("payroll headcount effect", pay["volume"]),
                             ("payroll rate effect", pay["rate"]),
                             ("revenue volume effect", rev["volume"]),
                             ("revenue price/mix effect", rev["price"])]:
            check(agent.fmt_signed_k(value) in md,
                  f"{bu}: {label} {agent.fmt_signed_k(value)} appears on the page")

        # 4. Material items coverage and honesty language
        items = agent.material_items(vt, bu)
        missing = [f"{it['period']}/{it['line_item']}" for it in items
                   if not (it["period"] in md and f"{it['variance_eur']:+,.0f}" in md)]
        check(not missing,
              f"{bu}: all {len(items)} material item(s) appear on the page"
              if not missing else f"{bu}: material item(s) MISSING from the page: {missing}")
        n_unexplained = sum(1 for it in items if not it["evidence_ids"])
        if n_unexplained:
            check(md.count("No clear driver identified") >= n_unexplained,
                  f"{bu}: 'No clear driver identified' appears for each of the "
                  f"{n_unexplained} unexplained item(s)")

        # 6. Style rules
        check("—" not in md, f"{bu}: no em dashes on the page")
        hits = [w for w in BUZZWORDS if w in md.lower()]
        check(not hits, f"{bu}: no buzzwords on the page"
              if not hits else f"{bu}: buzzword(s) found: {hits}")

    # 5. Trap handling on the Production page
    prod_md = (OUT_DIR / "production.md").read_text(encoding="utf-8")
    trap_rows = [l for l in prod_md.splitlines()
                 if l.startswith("|") and "2025-11" in l and "Revenue" in l]
    check(not trap_rows,
          "Production: the trap month never appears as a material variance row")
    check("data entry error" in prod_md,
          "Production: the page discloses the Nov-2025 data note")
    check("18 projects" in prod_md,
          "Production: the ops-system corroboration (normal project count) is shown")

    n_fail = sum(1 for ok, _ in results if not ok)
    for ok, msg in results:
        print(f"  {'PASS' if ok else 'FAIL'} - {msg}")
    print(f"\nRESULT: {'all checks passed.' if not n_fail else f'{n_fail} CHECK(S) FAILED.'}")
    return 1 if n_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
