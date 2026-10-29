"""Build a local draft; any failed required check blocks the site build."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

from agents.release_gate import stamp_manifest

STEPS = [
    ('agents/ingestion_agent.py', 'Source ingestion'),
    ('agents/variance_agent.py', 'Provisional variance analysis'),
    ('agents/forecast_agent.py', 'Recurrence-reviewed forecast'),
    ('agents/bu_report_agent.py', 'Business-line reports'),
    ('agents/narrative_agent.py', 'Bound commentary'),
    ('make_charts.py', 'Charts'),
    ('agents/figures_agent.py', 'Canonical figures and source bridge'),
    ('tests/validate_ingestion.py', 'Ingestion validation'),
    ('tests/validate_variance.py', 'Variance validation'),
    ('tests/validate_forecast.py', 'Forecast validation'),
    ('tests/validate_drivers.py', 'Driver validation'),
    ('tests/validate_bu_reports.py', 'Report validation'),
    ('tests/validate_narrative.py', 'Commentary validation'),
    ('tests/test_financial_controls.py', 'Adversarial and gate regression tests'),
    ('agents/qa_agent.py', 'QA gate'),
]


def run_step(script, extra=None):
    return subprocess.run([sys.executable, script]+(extra or []),capture_output=True,text=True)


def assemble_board_pack():
    lines = ['# EventCo draft management pack', '', '> LOCAL DRAFT: pending human review. Not approved for distribution.', '',
             'As of 30 June 2026. Synthetic data. FY2025 figures use the provisional demonstration scenario; Q3 2026 is the forecast horizon.', '']
    for title, name in [('Executive assessment','executive_summary'),('FY2025 and historical variances','variance_report'),
                        ('Q3 2026 forecast and sensitivities','forecast_report'),('Source quality and provisional assumptions','data_quality_report'),('Validation','qa_report')]:
        lines += ['## '+title, '', Path('output/'+name+'.md').read_text(encoding='utf-8'), '']
    lines += ['## Business-line reports', '']
    for p in sorted(Path('output/bu_reports').glob('*.md')):
        lines.append(f'- [{p.stem.replace("_"," ")}]({p.relative_to("output").as_posix()})')
    lines += ['', '## Sign-off', '', 'Reviewed by: __________________', '', 'Approved for distribution: [ ] Yes [ ] No', '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--provisional', action='store_true', help='Select the unapproved, labelled synthetic reporting scenario')
    parser.add_argument('--ai', action='store_true', help='Opt in to external AI ordering of synthetic statements')
    args = parser.parse_args()
    Path('output').mkdir(exist_ok=True)
    stamp_manifest(False, 'Run in progress; previous validation invalidated')
    log = ['# Local pipeline validation', '', 'No report distribution is performed. Optional --ai sends the statement catalogue externally.', '']
    for script, description in STEPS:
        extra = ['--provisional'] if script == 'agents/variance_agent.py' and args.provisional else []
        if script == 'agents/narrative_agent.py' and args.ai:
            extra = ['--ai']
        result = run_step(script, extra)
        print(f'{description}: '+('PASS' if result.returncode == 0 else 'FAIL'))
        log += ['## '+description, '', f'Exit status: {result.returncode}', '', '```', result.stdout, result.stderr, '```', '']
        if result.returncode:
            Path('output/pipeline_log.md').write_text('\n'.join(log),encoding='utf-8')
            Path('output/board_pack.md').write_text('# FAILED REVIEW: BUILD BLOCKED\n\nRequired step failed: '+description+'. See pipeline_log.md.\n',encoding='utf-8')
            if script != 'agents/qa_agent.py':
                Path('output/qa_report.md').write_text('# FAILED REVIEW: SITE BUILD BLOCKED\n\nRequired step failed: '+description+'. Detailed checks: pipeline_log.md.\n',encoding='utf-8')
            stamp_manifest(False, description+' failed')
            print(result.stdout[-5000:]+result.stderr[-5000:])
            return 1
    Path('output/pipeline_log.md').write_text('\n'.join(log),encoding='utf-8')
    Path('output/board_pack.md').write_text(assemble_board_pack(),encoding='utf-8')
    stamp_manifest(True)
    print('Local draft verified. Review before publication; no report was distributed.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
