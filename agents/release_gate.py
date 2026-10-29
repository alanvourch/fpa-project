"""Local build gate: passing QA tied to exact source and generated artifacts."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / 'output/release_status.json'


def artifact_hashes():
    paths = []
    for folder in ('agents','tests','data','output','docs','showcase'):
        paths += [p for p in (ROOT/folder).rglob('*') if p.is_file()
                  and '_site' not in p.parts and '__pycache__' not in p.parts
                  and p.suffix in {'.py','.md','.csv','.json','.png','.pdf','.html'} and p != STATUS]
    paths += [ROOT/name for name in ('orchestrator.py','make_charts.py','README.md','FIGURES.md','requirements.txt')]
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}


def stamp_manifest(passed, reason=''):
    STATUS.write_text(json.dumps(dict(qa_passed=passed, status='verified local draft' if passed else 'BLOCKED: failed review',
                                     publication_approved=False, reason=reason,
                                     hashes=artifact_hashes() if passed else {}),indent=2),encoding='utf-8')


def verify_manifest():
    state = json.loads(STATUS.read_text(encoding='utf-8'))
    if not state.get('qa_passed') or state.get('hashes') != artifact_hashes():
        raise ValueError('Site build blocked: QA failed, is missing, or artifacts changed since validation. Rerun orchestrator.py --provisional.')
    return state
