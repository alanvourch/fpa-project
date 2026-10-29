"""Validate constrained, scoped commentary. Arbitrary prose fails closed."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from agents.grounding_check import run_all_checks


def main():
    results = run_all_checks('', '', Path('output/executive_summary.md').read_text(encoding='utf-8'))
    for ok, message in results:
        print(('PASS: ' if ok else 'FAIL: ')+message)
    return int(not all(ok for ok,_ in results))


if __name__ == '__main__':
    raise SystemExit(main())
