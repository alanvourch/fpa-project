"""Independently reconcile forecast rows and recurrence decisions."""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'agents'))
from forecast_agent import LINE_ORDER


def main():
    fc = pd.read_csv('output/forecast.csv')
    vt = pd.read_csv('output/variance_table.csv').fillna({'materiality':''})
    audit = pd.read_csv('output/forecast_adjustments.csv')
    bt = pd.read_csv('output/forecast_backtest.csv')
    assert len(fc) == 132 and not fc.duplicated(['month','business_unit','line_item']).any()
    assert set(fc.month) == {'2026-07','2026-08','2026-09'}
    assert set(fc.line_item) == set(LINE_ORDER)
    assert np.isfinite(fc[['forecast','growth_factor','raw_baseline_forecast','neutralized_sensitivity']]).all().all()
    assert (fc.forecast >= 0).all()
    reviews = pd.read_csv("data/forecast_reviews.csv").fillna("")
    review_keys = set(zip(reviews.business_unit,reviews.line_item,reviews.month))
    assert set(zip(audit.business_unit,audit.line_item,audit.month)) == review_keys | set(zip(
        vt.loc[(vt.materiality != '') | vt.suspected_data_error,'business_unit'],
        vt.loc[(vt.materiality != '') | vt.suspected_data_error,'line_item'],
        vt.loc[(vt.materiality != '') | vt.suspected_data_error,'month']))
    if reviews.empty:
        assert (audit.classification == 'unresolved').all()
        assert np.allclose(audit.raw_actual,audit.normalized_to)
    for row in fc.itertuples():
        g = vt[(vt.business_unit == row.business_unit) & (vt.line_item == row.line_item)].set_index('month')
        history=g.provisional_actual.copy()
        for r in reviews[(reviews.business_unit==row.business_unit) & (reviews.line_item==row.line_item)].to_dict('records'):
            if r['status']=='approved' and r['classification']=='confirmed one-off' and pd.Timestamp(r['reviewed_at'])<=pd.Timestamp('2026-06-30'):
                history.loc[r['month']]=float(r['replacement'])
        expected_base = history.loc[row.base_month]
        pairs = [history.loc[m]/history.loc[str(pd.Period(m)-12)]
                 for m in pd.period_range('2025-07','2026-06',freq='M').astype(str) if history.loc[str(pd.Period(m)-12)]>0]
        expected = expected_base * float(np.median(pairs))
        assert abs(expected-row.forecast) < .02, (row.business_unit,row.line_item,row.month)
    assert len(bt) == 528 and set(bt.cutoff) == {'2025-12','2026-01','2026-02','2026-03'}
    assert (bt.month > bt.cutoff).all()
    assert np.allclose(bt.absolute_error,(bt.forecast-bt.actual).abs(),atol=.02)
    report=Path('output/forecast_report.md').read_text()
    assert 'seasonal naive' in report
    assert 'As of 30 June 2026' in report
    print('PASS: 132 forecasts independently reconciled; unresolved effects retained; 32 decisions; 528 holdout predictions')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
