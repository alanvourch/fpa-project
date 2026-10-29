"""Adversarial checks for financial judgment, source integrity and release failure."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'agents'))
import forecast_agent as forecast
import reporting_basis
import release_gate
import orchestrator
from agents.grounding_check import run_all_checks
from ingestion_agent import detect_outliers, remove_duplicates
from variance_agent import build_variance_table, find_material_items, LINE_ITEMS


class FinancialControls(unittest.TestCase):
    def test_source_gaps_preserved(self):
        source=pd.read_csv('data/eventco_monthly_cleaned.csv')
        vt=pd.read_csv('output/variance_table.csv')
        self.assertEqual(source.isna().sum().sum(),9)
        self.assertEqual(vt[['actual','budget']].isna().sum().sum(),9)
        for line,actual,budget,_ in LINE_ITEMS:
            for column,name in [(actual,'actual'),(budget,'budget')]:
                g=vt[vt.line_item==line].copy()
                g.month=g.month+'-01'
                merged=g.merge(source,on=['month','business_unit'])
                self.assertTrue(np.allclose(merged[name],merged[column],equal_nan=True))

    def test_strict_reporting_rejects_gaps(self):
        source=pd.read_csv('data/eventco_monthly_cleaned.csv',parse_dates=['month'])
        with self.assertRaises(ValueError):
            reporting_basis.provisional_scenario(source,enabled=False)

    def test_no_future_observation_in_estimates(self):
        source=pd.read_csv('data/eventco_monthly_cleaned.csv',parse_dates=['month'])
        scenario,_=reporting_basis.provisional_scenario(source,True)
        cutoff=pd.Timestamp('2025-12-01')
        changed=source.copy()
        cols=changed.columns.difference(['month','business_unit'])
        changed.loc[changed.month>cutoff,cols]=999999999
        other,_=reporting_basis.provisional_scenario(changed,True)
        pd.testing.assert_frame_equal(scenario[scenario.month<=cutoff],other[other.month<=cutoff])
        pd.testing.assert_frame_equal(source,pd.read_csv('data/eventco_monthly_cleaned.csv',parse_dates=['month']))

    def test_low_ratio_is_retained_as_possible_business_event(self):
        source=pd.read_csv('data/eventco_monthly_cleaned.csv',parse_dates=['month']).fillna(100)
        source.loc[0,'revenue_actual']=source.loc[0,'revenue_budget']*.10
        vt=build_variance_table(source)
        row=vt[(vt.business_unit==source.loc[0,'business_unit']) & (vt.month==source.loc[0,'month']) & (vt.line_item=='Net billings')].iloc[0]
        self.assertTrue(row.suspected_data_error)
        self.assertFalse(row.withheld_from_analysis)
        episodes,singles=find_material_items(vt)
        self.assertTrue(any(row.month in i['months'] and i['business_unit']==row.business_unit and i['line_item']=='Net billings' for i in episodes+singles))

    def test_conflicting_duplicate_fails(self):
        source=pd.read_csv('data/eventco_monthly_cleaned.csv',parse_dates=['month']).iloc[:1]
        dup=pd.concat([source,source],ignore_index=True)
        dup.loc[1,'revenue_actual']+=1
        with self.assertRaises(ValueError):
            remove_duplicates(dup,{})

    def test_unresolved_and_concluded_episode_retained(self):
        df=forecast.load_variance_table()
        g=df[(df.business_unit=='Corporate Events') & (df.line_item=='Opex - Marketing')]
        normalized,audit=forecast.normalize_history(g,df.month.max(),[])
        pd.testing.assert_series_equal(normalized,g.actual)
        self.assertTrue(all(a['classification']=='unresolved' for a in audit))

    def test_recurrence_approval_rules(self):
        df=forecast.load_variance_table()
        g=df[(df.business_unit=='Digital/Influence') & (df.line_item=='Net billings')]
        key=g[g.month==pd.Timestamp('2025-09-01')].index[0]
        review=dict(business_unit='Digital/Influence',line_item='Net billings',month='2025-09',classification='confirmed one-off',status='proposed',reviewer='test',reviewed_at='2025-10-01',evidence='test fixture',replacement=1234)
        kept,_=forecast.normalize_history(g,df.month.max(),[review])
        self.assertEqual(kept.loc[key],g.loc[key,'actual'])
        review['status']='approved'
        adjusted,_=forecast.normalize_history(g,df.month.max(),[review])
        self.assertEqual(adjusted.loc[key],1234)
        review['reviewed_at']='2026-10-29'
        future,_=forecast.normalize_history(g,df.month.max(),[review])
        self.assertEqual(future.loc[key],g.loc[key,'actual'])
        review['reviewed_at']='2025-10-01'
        for classification in ['continuing structural effect','timing shift','unresolved']:
            review['classification']=classification
            kept,_=forecast.normalize_history(g,df.month.max(),[review])
            self.assertEqual(kept.loc[key],g.loc[key,'actual'])

    def test_backtest_does_not_use_future_data(self):
        df=forecast.load_variance_table()
        cutoff=pd.Timestamp('2025-12-01')
        first,*_=forecast.build_forecast(df,reviews=[],cutoff=cutoff)
        changed=df.copy()
        changed.loc[changed.month>cutoff,['actual','source_actual','budget']]=999999999
        second,*_=forecast.build_forecast(changed,reviews=[],cutoff=cutoff)
        pd.testing.assert_frame_equal(first,second)

    def test_marketing_cause_not_assigned_to_earlier_or_later_months(self):
        vt=pd.read_csv('output/variance_table.csv').fillna({'evidence_notes':''})
        rows=vt[(vt.business_unit=='Corporate Events') & (vt.line_item=='Opex - Marketing')]
        cited=rows[rows.evidence_notes.str.contains('N12')]
        self.assertTrue(((cited.month>='2025-07') & (cited.month<='2025-12')).all())
        self.assertFalse(cited.empty)

    def test_commentary_rejects_wrong_claims(self):
        text=Path('output/executive_summary.md').read_text(encoding='utf-8')
        self.assertTrue(all(ok for ok,_ in run_all_checks('','',text)))
        mutations={
            'wrong business unit':text.replace('Group Q3 2026 net billings forecast:','Brand Events Q3 2026 net billings forecast:',1),
            'wrong period':text.replace('FY2025 provisional group','FY2024 provisional group',1),
            'wrong sign':text.replace('Brand Events records a provisional FY2025 operating loss','Brand Events records a provisional FY2025 operating profit',1),
            'omitted loss':text.replace(next(f['statement'] for f in json.loads(Path('output/narrative_claims.json').read_text(encoding='utf-8'))['facts'] if f['id']=='month_2026-08'),''),
            'unsupported reassurance':text+'Performance does not reflect deterioration.\n',
            'invented amount':text+'Brand Events Q3 billings are EUR999M.\n',
        }
        for name,mutated in mutations.items():
            with self.subTest(name=name):
                self.assertNotEqual(text,mutated)
                self.assertFalse(all(ok for ok,_ in run_all_checks('','',mutated)))

    def test_tampered_statement_ledger_is_rejected(self):
        text=Path('output/executive_summary.md').read_text(encoding='utf-8')
        original=json.loads(Path('output/narrative_claims.json').read_text(encoding='utf-8'))
        for field,value in [('business_unit','Brand Events'),('period','FY2024'),('amount',-999),('direction','negative'),('evidence',['wrong source'])]:
            ledger=copy.deepcopy(original)
            ledger['facts'][0][field]=value
            with self.subTest(field=field),patch('agents.grounding_check.Path') as ledger_path:
                ledger_path.return_value.read_text.return_value=json.dumps(ledger)
                self.assertFalse(run_all_checks('','',text)[0][0])

    def test_provisional_bridge_independently_reconciles(self):
        vt=pd.read_csv('output/variance_table.csv')
        y=vt[vt.month.str.startswith('2025')]
        sign=y.line_item.map(lambda line: 1 if line=='Net billings' else -1)
        source=(y.actual*sign).sum()
        provisional=(y.provisional_actual*sign).sum()
        bridge=pd.read_csv('output/reporting_bridge.csv')
        self.assertAlmostEqual(bridge.amount.iloc[0],source,places=2)
        self.assertAlmostEqual(bridge.amount.iloc[:3].sum(),provisional,places=2)
        self.assertAlmostEqual(bridge.amount.iloc[3],provisional,places=2)
        self.assertIn('incomplete',bridge.component.iloc[0])

    def test_manifest_requires_passed_current_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            status=Path(tmp)/'status.json'
            with patch.object(release_gate,'STATUS',status),patch.object(release_gate,'artifact_hashes',return_value={'a':'one'}):
                release_gate.stamp_manifest(False)
                with self.assertRaises(ValueError): release_gate.verify_manifest()
                release_gate.stamp_manifest(True)
                release_gate.verify_manifest()
                with patch.object(release_gate,'artifact_hashes',return_value={'a':'changed'}):
                    with self.assertRaises(ValueError): release_gate.verify_manifest()

    def test_orchestrator_returns_failure_and_blocks_pack(self):
        old=os.getcwd()
        with tempfile.TemporaryDirectory() as tmp:
            try:
                os.chdir(tmp)
                with patch.object(orchestrator,'STEPS',[('qa','QA gate')]),patch.object(orchestrator,'run_step',return_value=subprocess.CompletedProcess([],1,'failed check','')),patch.object(orchestrator,'stamp_manifest') as stamp,patch.object(sys,'argv',['orchestrator.py']),patch('builtins.print'):
                    self.assertEqual(orchestrator.main(),1)
                    self.assertFalse(stamp.call_args.args[0])
                    self.assertIn('FAILED REVIEW',Path('output/board_pack.md').read_text())
            finally:
                os.chdir(old)


if __name__=='__main__':
    unittest.main()
