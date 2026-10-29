"""Bound, inspectable statements for this case study's constrained commentary."""
import json
from pathlib import Path

import pandas as pd
try:
    from .reporting_basis import load_reporting_table
except ImportError:
    from reporting_basis import load_reporting_table


def money(value):
    return f"-EUR{abs(value)/1000:,.0f}k" if value < 0 else f"EUR{value/1000:,.0f}k"


def build_facts():
    vt = load_reporting_table()
    fc = pd.read_csv("output/forecast.csv")
    items = json.loads(Path("output/material_items.json").read_text(encoding="utf-8"))
    facts = []
    def add(key, section, unit, period, metric, value, evidence, statement):
        facts.append(dict(id=key, section=section, business_unit=unit, period=period, metric=metric,
                          amount=None if value is None else round(float(value), 2),
                          direction="context" if value is None else ("negative" if value < 0 else "positive" if value > 0 else "zero"),
                          evidence=evidence, statement=statement))
    y = vt[vt.month.str.startswith("2025")]
    def result(g, col):
        return g.loc[g.line_item == "Net billings", col].sum()-g.loc[g.line_item != "Net billings", col].sum()
    actual, budget = result(y, "actual"), result(y, "budget")
    add("fy_actual", "FY2025 assessment", "GROUP", "FY2025", "provisional operating result", actual, ["variance_table.csv"],
        f"FY2025 provisional group operating result is {money(actual)}.")
    add("fy_budget", "FY2025 assessment", "GROUP", "FY2025", "provisional budget operating result", budget, ["variance_table.csv"],
        f"The budget comparator is {money(budget)} and includes estimates for missing budget cells.")
    add("fy_gap", "FY2025 assessment", "GROUP", "FY2025", "operating result variance", actual-budget, ["variance_table.csv"],
        f"The shortfall is {money(budget-actual)}, an adverse variance.")
    brand = result(y[y.business_unit == 'Brand Events'], 'actual')
    add("brand_loss", "FY2025 assessment", "Brand Events", "FY2025", "provisional operating result", brand, ["variance_table.csv"],
        f"Brand Events records a provisional FY2025 operating {'loss' if brand < 0 else 'profit'} of {money(abs(brand))}.")
    add("basis", "FY2025 assessment", "GROUP", "FY2025", "reporting basis", None, ["reporting_adjustments.csv", "reporting_policy.json"],
        "These results use unapproved estimates for missing source cells and a budget placeholder for November 2025 Brand Events billings. The source amount remains unconfirmed. Totals are a provisional demonstration scenario, pending source verification.")
    for key, bu, note, label in [('overrun','Brand Events','N11','project cost overrun'), ('fx','Digital/Influence','N08','FX billings shortfall'), ('marketing','Corporate Events','N12','marketing underspend in the documented period')]:
        g = y[(y.business_unit == bu) & y.evidence_notes.fillna('').str.contains(note)]
        value = ((g.actual-g.budget) * g.line_item.map(lambda l: 1 if l == 'Net billings' else -1)).sum()
        period = f"{g.month.min()}..{g.month.max()}"
        first,last = pd.Period(g.month.min()),pd.Period(g.month.max())
        display_period = first.strftime('%b %Y') if first==last else first.strftime('%b')+'-'+last.strftime('%b %Y')
        add(key, "Financial drivers", bu, period, label, value, [note],
            f"{bu}: {money(abs(value))} {'adverse' if value < 0 else 'favorable'} P&L impact from the {label} during {display_period}.")
    quiet = y[(y.materiality.fillna('') == '') & (~y.withheld_from_analysis) & y.line_item.isin(['Net billings','Cost of sales'])]
    value = ((quiet.actual-quiet.budget) * quiet.line_item.map(lambda l: 1 if l == 'Net billings' else -1)).sum()
    add('quiet_margin','Financial drivers','GROUP','FY2025','gross margin variance below monthly materiality',value,['variance_table.csv'],
        f"Gross-margin variances below monthly materiality total {money(abs(value))} adverse in FY2025 and need review alongside the largest project item.")
    add('marketing_scope','Financial drivers','Corporate Events','2025-04..2026-02','cause-period limitation',None,['N12','N16'],
        "The Corporate Events marketing run spans April 2025-February 2026. In-housing is documented from July through December 2025. The earlier and later months need separate explanation; the detector cannot establish that the saving has ended.")
    for item in items:
        if item['status'] == 'unresolved':
            value = item['variance_eur'] * (1 if item['line_item'] == 'Net billings' else -1)
            key = f"open_{len(facts)}"
            add(key,'Open items',item['business_unit'],item['period'],item['line_item']+' variance',value,['material_items.json'],
                f"{item['business_unit']} {item['line_item']}, {item['period']}: {money(abs(value))} {'favorable' if value > 0 else 'adverse'}, still unexplained. The BU controller owns the follow-up.")
    add('open_count','Open items','GROUP','2024-01..2026-06','unresolved material item count',sum(i['status']=='unresolved' for i in items),['material_items.json'],
        f"{sum(i['status']=='unresolved' for i in items)} material items remain unresolved in the full historical review. Analyst explanations elsewhere are illustrative manual input on synthetic data.")
    for bu in ['GROUP'] + sorted(fc.business_unit.unique()):
        g = fc if bu == 'GROUP' else fc[fc.business_unit == bu]
        bills = g.loc[g.line_item == 'Net billings','forecast'].sum()
        op = bills-g.loc[g.line_item != 'Net billings','forecast'].sum()
        add(f'q3_bills_{bu}','Q3 2026 outlook',bu,'Q3 2026','net billings forecast',bills,['forecast.csv'],
            f"{'Group' if bu == 'GROUP' else bu} Q3 2026 net billings forecast: {money(bills)}.")
        add(f'q3_op_{bu}','Q3 2026 outlook',bu,'Q3 2026','operating result forecast',op,['forecast.csv'],
            f"{'Group' if bu == 'GROUP' else bu} Q3 2026 operating {'loss' if op < 0 else 'profit'} forecast: {money(abs(op))}.")
    for month, g in fc.groupby('month'):
        value = g.loc[g.line_item == 'Net billings','forecast'].sum()-g.loc[g.line_item != 'Net billings','forecast'].sum()
        add(f'month_{month}','Q3 2026 outlook','GROUP',month,'operating result forecast',value,['forecast.csv'],
            f"Group {pd.Period(month).strftime('%B %Y')} operating {'loss' if value < 0 else 'profit'} forecast: {money(abs(value))}.")
    add('outlook_risk','Q3 2026 outlook','GROUP','Q3 2026','forecast limitation',None,['forecast_report.md'],
        "The selected forecast retains unresolved historical effects. The August operating loss needs review by BU managers and group FP&A. A seasonal pattern does not establish that the loss is commercially acceptable; compare the raw baseline and unapproved sensitivity in the forecast report.")
    add('actions','Management actions','GROUP','As of 2026-06-30','owners',None,['reporting_policy.json','material_items.json'],
        "Brand Events' manager should review project recovery and margin controls with group FP&A. The Corporate Events manager should review the forecast loss and document the savings period. BU controllers should resolve the two unexplained items; the finance data owner should confirm missing cells and November billings before approval.")
    return facts


def render_summary(facts, order=None):
    order = [f['id'] for f in facts] if order is None else order
    if len(order) != len(facts) or set(order) != {f['id'] for f in facts}:
        raise ValueError('Commentary must include each bound fact exactly once')
    lookup = {f['id']: f for f in facts}
    lines = ['# Executive summary', '', 'Synthetic case study. As of 30 June 2026. Provisional; pending human review.', '']
    for section in dict.fromkeys(f['section'] for f in facts):
        lines += ['## '+section, '']
        entries = [lookup[key] for key in order if lookup[key]['section'] == section]
        if section == 'FY2025 assessment':
            lines += [' '.join(e['statement'] for e in entries[:4]), '', entries[4]['statement'], '']
        elif section == 'Q3 2026 outlook':
            for unit in dict.fromkeys(e['business_unit'] for e in entries if e['id'].startswith('q3_')):
                lines += [' '.join(e['statement'] for e in entries if e['id'].startswith('q3_') and e['business_unit']==unit), '']
            lines += [' '.join(e['statement'] for e in entries if e['id'].startswith('month_')), '', lookup['outlook_risk']['statement'], '']
        else:
            lines += [e['statement']+'\n' for e in entries]
    return '\n'.join(lines).rstrip()+'\n'
