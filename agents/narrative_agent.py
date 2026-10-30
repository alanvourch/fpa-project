"""Render constrained commentary locally; optionally ask AI to order bound facts.

The AI option sends the structured statement catalogue, which may contain
business names and context, to the configured provider. It is opt-in and is
suitable here because all data is synthetic. Aggregation is not anonymization.
"""
import argparse
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from commentary_facts import build_facts, render_summary


_API_SPEND = 0.0


def api_key():
    key = os.environ.get('ANTHROPIC_API_KEY', '').strip()
    if not key and Path('.env').exists():
        for line in Path('.env').read_text(encoding='utf-8-sig').splitlines():
            name, separator, value = line.partition('=')
            if separator and name.strip() == 'ANTHROPIC_API_KEY':
                key = value.strip().strip('"').strip("'")
    return key


def ask_api_json(system, payload, schema, key):
    """Use an explicit key, bypassing the expired OAuth profile, with a spend guard.

    Guard estimates use published Sonnet 5 base rates: $2/MTok input,
    $10/MTok output. No retries; no extended thinking. Each request reserves
    its maximum output allowance before it runs. The default run cap is $1.
    """
    global _API_SPEND
    import anthropic
    model = 'claude-sonnet-5'
    client = anthropic.Anthropic(api_key=key, auth_token=None, timeout=45, max_retries=0)
    request = dict(model=model, system=system,
                   messages=[{'role':'user','content':json.dumps(payload)}],
                   tools=[{'name':'return_decision','description':'Return the structured financial-agent decision.', 'input_schema':schema}],
                   tool_choice={'type':'tool','name':'return_decision'})
    count = client.messages.count_tokens(**request).input_tokens
    maximum_output = 2000
    estimated_maximum = (count*2+maximum_output*10)/1_000_000
    limit = float(os.environ.get('FPA_AGENT_BUDGET_USD','1.00'))
    if _API_SPEND+estimated_maximum > limit:
        raise RuntimeError('Agent API spend guard reached; no further generation request was sent.')
    response = client.messages.create(**request,max_tokens=maximum_output)
    usage = response.usage
    cost = (usage.input_tokens*2+usage.output_tokens*10)/1_000_000
    _API_SPEND += cost
    blocks = [block for block in response.content if block.type=='tool_use' and block.name=='return_decision']
    if response.stop_reason!='tool_use' or len(blocks)!=1 or not isinstance(blocks[0].input,dict):
        raise RuntimeError('API response was incomplete or did not return the expected decision.')
    return blocks[0].input, dict(model=model,provider='Anthropic API',cost_usd=cost,
                                usage=dict(input_tokens=usage.input_tokens,output_tokens=usage.output_tokens))


def ask_claude_json(system, payload, schema):
    """One bounded model decision. Provider code stays in this module.

    The installed CLI can use an existing subscription login. Safe mode removes
    project/user customizations; built-in tools and MCP are disabled. Python
    alone dispatches the narrow read-only tools in review_workflow.py.
    """
    key = api_key()
    if key:
        return ask_api_json(system,payload,schema,key)
    executable = shutil.which('claude')
    if not executable:
        raise RuntimeError('Claude Code CLI is required for --live-agents; authenticate with claude auth login.')
    command = [executable, '--safe-mode', '-p', '--output-format', 'json',
               '--json-schema', json.dumps(schema), '--system-prompt', system,
               '--tools', '', '--strict-mcp-config', '--mcp-config', '{"mcpServers":{}}',
               '--disable-slash-commands', '--no-chrome', '--no-session-persistence',
               '--setting-sources', '', '--model', os.environ.get('FPA_AGENT_MODEL', 'sonnet'), '--effort', 'low']
    with tempfile.TemporaryDirectory(prefix='fpa-agent-') as directory:
        try:
            response = subprocess.run(command, input=json.dumps(payload), capture_output=True,
                                      text=True, encoding='utf-8', cwd=directory, timeout=120)
        except subprocess.TimeoutExpired:
            raise RuntimeError('Claude request timed out. Check the Claude Code connection/login before retrying; no agent record was saved.') from None
    if response.returncode:
        raise RuntimeError('Claude request failed. Check the Claude Code login and connection; no agent record was saved.')
    envelope = json.loads(response.stdout)
    if envelope.get('is_error') or not isinstance(envelope.get('structured_output'), dict):
        raise RuntimeError('Claude did not return a valid structured decision: '+str(envelope.get('result',''))[:500])
    return envelope['structured_output'], dict(model=os.environ.get('FPA_AGENT_MODEL', 'sonnet'),
                                               cost_usd=envelope.get('total_cost_usd'), usage=envelope.get('usage'))


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
