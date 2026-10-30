"""Validate generated local site links and copied artifacts without external requests."""
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit, unquote
import hashlib
import re

ROOT=Path(__file__).resolve().parents[1]
SITE=ROOT/'showcase/_site'


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls=[]
    def handle_starttag(self,tag,attrs):
        for name,value in attrs:
            if name in ('href','src'):
                self.urls.append(value)


def main():
    checked=0
    for page in SITE.rglob('*.html'):
        text=page.read_text(encoding='utf-8')
        assert not re.search(r'\{\{[A-Z_]+\}\}',text),page
        parser=Links(); parser.feed(text)
        for url in parser.urls:
            parsed=urlsplit(url)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            target=(page.parent/unquote(parsed.path)).resolve()
            assert target.is_relative_to(SITE.resolve()),(page,url)
            assert target.exists(),(page,url)
            checked+=1
    for src in list((ROOT/'docs').glob('*.png'))+list((ROOT/'output/bu_reports').glob('*.pdf'))+[ROOT/'output'/name for name in ['variance_table.csv','forecast.csv','forecast_backtest.csv','reporting_adjustments.csv','reporting_bridge.csv']]:
        copied=SITE/'assets'/src.name
        assert copied.read_bytes()==src.read_bytes(),src
    forecast=(SITE/'reports/forecast_report.html').read_text(encoding='utf-8')
    assert all(label in forecast for label in ['Source actual:', 'Provisional input:', 'Used in history:'])
    html=(SITE/'index.html').read_text(encoding='utf-8')
    assert 'provisional' in html.lower() and 'Paris' not in html and 'director was' not in html.lower()
    assert 'EUR663k' in html and 'EUR193k' in html
    assert html.index('id="workflow"') < html.index('id="reports"')
    assert 'Claude agents' in html and 'Analyst review' in html
    assert 'illustrative' in html and 'recorded Claude run' in html
    assert (SITE/'assets/agent_review.json').read_bytes()==(ROOT/'output/agent_review.json').read_bytes()
    print(f'PASS: {checked} local link/image targets; copied PDFs/charts/CSVs match canonical artifacts; no unresolved landing-page values')


if __name__=='__main__':
    main()
