"""Render constrained commentary locally; optionally ask AI to order bound facts.

The AI option sends the structured statement catalogue, which may contain
business names and context, to the configured provider. It is opt-in and is
suitable here because all data is synthetic. Aggregation is not anonymization.
"""
import argparse
import json
import os
from pathlib import Path

from commentary_facts import build_facts, render_summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--ai', action='store_true', help='Send synthetic statement catalogue to configured AI provider for ordering only')
    args = parser.parse_args()
    facts = build_facts()
    order = [f['id'] for f in facts]
    if args.ai:
        import anthropic
        client = anthropic.Anthropic()
        response = client.messages.create(model=os.environ.get('FPA_NARRATIVE_MODEL', 'claude-sonnet-5'), max_tokens=2048,
            system='Return only a JSON array containing every supplied statement id exactly once, ordered for readability. No other text.',
            messages=[{'role':'user','content':json.dumps(facts)}])
        order = json.loads(next(b.text for b in response.content if b.type == 'text'))
    summary = render_summary(facts, order)
    Path('output/narrative_claims.json').write_text(json.dumps(dict(facts=facts, order=order), indent=2), encoding='utf-8')
    Path('output/executive_summary.md').write_text(summary, encoding='utf-8')
    print(f'Commentary: {len(facts)} bound statements; '+('AI ordering' if args.ai else 'local deterministic rendering'))


if __name__ == '__main__':
    main()
