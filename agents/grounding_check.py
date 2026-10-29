"""Validate constrained statements against independently recomputed scoped facts.

This does not infer the semantics of arbitrary prose. Free prose or an altered
statement fails closed and requires a reviewed template change. Each catalogue
entry binds business unit, period, metric, signed amount, direction and evidence.
"""
import json
import re
from pathlib import Path

try:
    from .commentary_facts import build_facts, render_summary
except ImportError:
    from commentary_facts import build_facts, render_summary


def parse_money_matches(text):
    return re.findall(r'[+-]?(?:EUR|€)[\d,.]+(?:k|M)?', text)


def parse_percent_matches(text):
    return re.findall(r'[+-]?[\d.]+%', text)


def run_all_checks(variance_text, forecast_text, narrative_text):
    try:
        facts = build_facts()
        ledger = json.loads(Path('output/narrative_claims.json').read_text(encoding='utf-8'))
        expected = render_summary(facts, ledger['order'])
    except (OSError, ValueError, KeyError) as error:
        return [(False, f'Bound commentary data unavailable or invalid: {error}')]
    return [
        (ledger['facts'] == facts, 'Statement ledger matches recomputed facts keyed by BU, period, metric, signed amount, direction and evidence'),
        (narrative_text == expected, 'Every statement matches its bound template; changed attribution, period, sign, omitted losses and added reassurance fail this check'),
        (all(f['statement'] in narrative_text for f in facts if f['section'] == 'Open items'),
         'Structured unresolved items and their count are all present'),
        (all(f['statement'] in narrative_text for f in facts if f['id'] in ('basis','brand_loss','fy_gap','outlook_risk')),
         'Provisional basis, annual shortfall, Brand Events result and outlook risk are present'),
    ]
