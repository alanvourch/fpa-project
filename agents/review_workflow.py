"""Read-only Claude investigation and reporting agents, with a replayable public example.

Live mode calls Claude through narrative_agent.py. Default mode replays the
captured responses and recomputes every tool result for the same inputs. It
never substitutes a fabricated conversation for an unavailable provider.
"""
import argparse
import hashlib
import html
import json
from pathlib import Path
import re

import pandas as pd
from bu_report_agent import load_inputs, fy_slice, scorecard, payroll_driver_split, revenue_driver_split
from commentary_facts import build_facts
from narrative_agent import ask_claude_json

RECORD=Path('data/agent_run.json')
OUTPUT=Path('output/agent_review.json')
INPUTS=['data/company_context.json','data/review_scenario.json','data/business_notes.csv',
        'data/eventco_drivers.csv','output/variance_table.csv','output/forecast.csv','output/material_items.json',
        'agents/review_workflow.py','agents/narrative_agent.py','agents/instructions/investigator.md','agents/instructions/reporter.md']
TOOLS=['scorecard','material_items','business_notes','driver_splits','forecast']
ACTIONS={
 'project_recovery':'BU manager and group FP&A: review project recovery and scope-change controls.',
 'source_verification':'Finance data owner: verify the November billings entry and missing source amounts before approval.',
 'driver_review':'BU controller: investigate the rate and price/mix residuals before assigning a cause.',
 'forecast_review':'BU manager and FP&A: challenge the forecast assumptions; no recurrence adjustment is approved.'}


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def fingerprint():
    # All agent inputs are text. Git's Windows checkout conversion must not
    # invalidate an otherwise identical recorded investigation.
    return {path:hashlib.sha256(Path(path).read_bytes().replace(b'\r\n',b'\n')).hexdigest() for path in INPUTS}


def plain(value):
    return json.loads(json.dumps(value, default=lambda v: v.item() if hasattr(v,'item') else str(v), allow_nan=False))


def check_questions(questions):
    if not isinstance(questions,list) or not 1<=len(questions)<=3:
        raise ValueError('One to three questions are required')
    for question in questions:
        if not isinstance(question,str) or not 10<=len(question)<=320 or not question.endswith('?'):
            raise ValueError('Follow-ups must be concise questions')
        if re.search(r'\d|EUR|\u20ac|\$|%|\b(?:million|thousand)\b',question,re.I):
            raise ValueError('Financial amounts must come from bound facts, not generated questions')


class FinancialTools:
    def __init__(self,unit):
        self.unit=unit
        self.vt,self.fc,self.drivers,self.notes=load_inputs()
        self.used=set()
        self.retrieved=set()

    def call(self,request):
        if set(request)!={'name','business_unit','note_ids'} or request['business_unit']!=self.unit:
            raise ValueError('Tool request outside the authorized business unit or schema')
        name=request['name']
        if name not in TOOLS or not isinstance(request['note_ids'],list):
            raise ValueError('Unknown tool or invalid note selection')
        if name!='business_notes' and request['note_ids']:
            raise ValueError('Note IDs apply only to the business_notes tool')
        if name=='scorecard':
            result=scorecard(fy_slice(self.vt,self.unit))
            result={'period':'FY2025','basis':'provisional; unapproved estimates and billings placeholder',**result}
        elif name=='driver_splits':
            result={'period':'FY2025','payroll':payroll_driver_split(self.vt,self.drivers,self.unit),
                    'billings':revenue_driver_split(self.vt,self.drivers,self.unit),
                    'limitation':'Rate and price/mix are arithmetic residuals, not verified causes.'}
        elif name=='material_items':
            result=[i for i in read_json('output/material_items.json') if i['business_unit']==self.unit]
        elif name=='forecast':
            g=self.fc[self.fc.business_unit==self.unit]
            result={'period':'Q3 2026','basis':'Unresolved effects retained; provisional history',
                    'billings':g.loc[g.line_item=='Net billings','forecast'].sum(),
                    'operating_result':g.loc[g.line_item=='Net billings','forecast'].sum()-g.loc[g.line_item!='Net billings','forecast'].sum()}
        else:
            ids=request['note_ids']
            if not ids or len(ids)>5 or len(set(ids))!=len(ids):
                raise ValueError('Select one to five distinct note IDs')
            result=[]
            for note_id in ids:
                if note_id not in self.notes.index:
                    raise ValueError('Unknown evidence note')
                note=self.notes.loc[note_id].to_dict()
                if note['business_unit'] not in (self.unit,'Group') or note['date']>'2026-06-30':
                    raise ValueError('Evidence belongs to another unit or future reporting period')
                result.append(dict(note_id=note_id,**note))
            self.retrieved.update(ids)
        self.used.add(name)
        return plain(result)


def decision_schema(fact_ids):
    return {'type':'object','additionalProperties':False,'required':['action','requests','fact_ids','evidence_ids','questions'],
            'properties':{
              'action':{'type':'string','enum':['request','finish']},
              'requests':{'type':'array','maxItems':3,'items':{'type':'object','additionalProperties':False,
                'required':['name','business_unit','note_ids'],'properties':{
                  'name':{'type':'string','enum':TOOLS},'business_unit':{'type':'string','enum':['Brand Events']},
                  'note_ids':{'type':'array','items':{'type':'string'}}}}},
              'fact_ids':{'type':'array','maxItems':10,'items':{'type':'string','enum':fact_ids}},
              'evidence_ids':{'type':'array','items':{'type':'string'}},
              'questions':{'type':'array','maxItems':3,'items':{'type':'string'}}}}


def report_schema(fact_ids):
    return {'type':'object','additionalProperties':False,'required':['fact_ids','action_ids','questions'],
            'properties':{'fact_ids':{'type':'array','minItems':3,'maxItems':7,'items':{'type':'string','enum':fact_ids}},
                          'action_ids':{'type':'array','minItems':2,'maxItems':4,'items':{'type':'string','enum':list(ACTIONS)}},
                          'questions':{'type':'array','minItems':1,'maxItems':2,'items':{'type':'string'}}}}


def selected_facts(ids,facts):
    if not isinstance(ids,list) or not ids or len(set(ids))!=len(ids) or not set(ids)<=set(facts):
        raise ValueError('Invalid fact selection, attribution or duplicate fact')
    return [facts[key] for key in ids]


def run_workflow(provider):
    context=read_json('data/company_context.json')
    scenario=read_json('data/review_scenario.json')
    facts={f['id']:f for f in build_facts() if f['business_unit'] in (scenario['business_unit'],'GROUP')}
    tools=FinancialTools(scenario['business_unit'])
    history=[]
    events=[]
    findings=[]
    for phase,instruction in [('investigation',scenario['instruction']),('analyst_follow_up',scenario['follow_up'])]:
        history.append({'analyst_instruction':instruction,'instruction_status':'illustrative case-study instruction'})
        for step in range(6):
            payload=dict(company_context=context,assignment=scenario['business_unit'],
                         tool_catalogue={'scorecard':'FY2025 provisional P&L','material_items':'Flagged variances and cited note IDs',
                                         'business_notes':'Retrieve selected dated evidence notes','driver_splits':'FY2025 FTE/rate and projects/price-mix splits',
                                         'forecast':'Q3 2026 provisional outlook'},
                         fact_catalogue=list(facts.values()),history=history,
                         protocol='Request checks with action=request and non-empty requests; other arrays empty. Or action=finish, requests empty, select fact_ids/evidence_ids and questions. No source changes or approvals.')
            decision,metadata=provider('investigator',payload,decision_schema(list(facts)))
            if set(decision)!={'action','requests','fact_ids','evidence_ids','questions'}:
                raise ValueError('Unexpected investigation fields')
            event=dict(phase=phase,role='investigator',decision=decision,provider=metadata)
            if decision['action']=='request':
                if not 1<=len(decision['requests'])<=3 or any(decision[k] for k in ('fact_ids','evidence_ids','questions')):
                    raise ValueError('Invalid tool request decision')
                event['results']=[dict(request=r,result=tools.call(r)) for r in decision['requests']]
            elif decision['action']=='finish':
                if decision['requests'] or not {'scorecard','driver_splits','business_notes'}<=tools.used:
                    raise ValueError('Required financial checks are missing')
                selected_facts(decision['fact_ids'],facts)
                if not set(decision['evidence_ids'])<=tools.retrieved:
                    raise ValueError('Unretrieved evidence citation')
                check_questions(decision['questions'])
                findings.append(decision)
            else:
                raise ValueError('Unrecognized agent action')
            history.append(event)
            events.append(event)
            if decision['action']=='finish':
                break
        else:
            raise ValueError('Investigation exceeded its decision limit')
    payload=dict(company_context=context,analyst_instructions=scenario,investigation=history,
                 fact_catalogue=list(facts.values()),action_catalogue=ACTIONS,
                 required_fact_ids=['brand_loss','basis','overrun'],
                 instruction='Draft a manager brief from verified statements and proposed questions. Include the loss, source uncertainty and project overrun. Do not approve it.')
    draft,metadata=provider('reporter',payload,report_schema(list(facts)))
    if set(draft)!={'fact_ids','action_ids','questions'} or not {'brand_loss','basis','overrun'}<=set(draft['fact_ids']):
        raise ValueError('Draft omits a required loss, basis or material driver')
    selected_facts(draft['fact_ids'],facts)
    if not {'project_recovery','source_verification'}<=set(draft['action_ids']) or not set(draft['action_ids'])<=set(ACTIONS):
        raise ValueError('Invalid or incomplete manager actions')
    check_questions(draft['questions'])
    events.append(dict(phase='manager_brief',role='reporter',decision=draft,provider=metadata))
    return plain(dict(schema_version=1,input_hashes=fingerprint(),scenario=scenario,company_context=context,events=events,
                      selected_facts=selected_facts(draft['fact_ids'],facts),questions=draft['questions'],
                      proposed_actions=[ACTIONS[k] for k in draft['action_ids']],approval_status='Pending analyst review; no financial adjustment approved'))


def replay_record(record):
    if record.get('input_hashes')!=fingerprint():
        raise ValueError('Agent example is stale. Rerun agents/review_workflow.py --live on the current synthetic inputs.')
    queue=iter(record['events'])
    def provider(role,payload,schema):
        event=next(queue)
        if event['role']!=role:
            raise ValueError('Replay role mismatch')
        return event['decision'],event['provider']
    regenerated=run_workflow(provider)
    if regenerated!=record:
        raise ValueError('Captured agent record does not match recomputed tool evidence or draft')
    if next(queue,None) is not None:
        raise ValueError('Extra agent events in replay record')
    return regenerated


def render_report(record):
    lines=['# Working with agents: a recorded case study','',
           'A real Claude run on synthetic data, with illustrative analyst instructions. Replayed locally against the same inputs; not a live employer review. Final approval remains open.','',
           '## The assignment','',record['scenario']['instruction'],'',
           '## Company context','',record['company_context']['business_model'],'',
           'The agents receive the company metric definitions, reporting date and review rules. Billings are invoiced amounts; rate and price/mix residuals do not establish causes.','',
           '## What the investigation agent checked','']
    for event in record['events']:
        if event['phase']=='analyst_follow_up' and not any('### Analyst follow-up'==line for line in lines):
            lines+=['### Analyst follow-up','',record['scenario']['follow_up'],'']
        for result in event.get('results',[]):
            request=result['request']
            labels={'scorecard':'Checked the provisional annual scorecard','driver_splits':'Requested headcount/rate and project-volume/mix breakdowns',
                    'material_items':'Examined material variances and their evidence references','business_notes':'Read dated business notes: '+', '.join(request['note_ids']),
                    'forecast':'Checked the next-quarter outlook'}
            lines+=['- '+labels[request['name']]+'.']
    lines+=['','## Draft for the manager','']
    for fact in record['selected_facts']:
        lines += [f"Scope: {fact['business_unit']} | {fact['period']}", '', fact['statement'], '']
    lines+=['## Proposed actions','']+['- '+a for a in record['proposed_actions']]
    lines+=['','## Questions requiring analyst review','', '<ul>']+['<li>'+html.escape(q)+'</li>' for q in record['questions']]+['</ul>']
    lines+=['','The proposed questions are AI-generated and need human review. Checks validate tool scope, cited facts and replay consistency; they do not establish that every question or conclusion is commercially sound.','',
            '## Illustrative analyst review point','',
            'Note N13 already records a signed change order for partial recovery. The useful next check is the amount recovered and whether it is already included in billings. Any proposed benefit needs that reconciliation before it can enter the forecast. This review point is part of the synthetic case study; final sign-off remains open.','',
            '## What stays with the analyst','',
            'Check source uncertainty, challenge explanations, choose management actions and approve the report. These agents have no tool for correcting source amounts, changing forecasts or publishing.','']
    return '\n'.join(lines)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--live',action='store_true',help='Call Claude on the synthetic assignment and replace the captured example')
    args=parser.parse_args()
    if args.live:
        def provider(role,payload,schema):
            print('Claude '+role+': requesting decision',flush=True)
            system=Path('agents/instructions/'+role+'.md').read_text(encoding='utf-8')
            return ask_claude_json(system,payload,schema)
        record=run_workflow(provider)
        RECORD.write_text(json.dumps(record,indent=2),encoding='utf-8')
    else:
        record=replay_record(read_json(RECORD))
    OUTPUT.write_text(json.dumps(record,indent=2),encoding='utf-8')
    Path('output/agent_review.md').write_text(render_report(record),encoding='utf-8')
    print(f"Agent review: {len(record['events'])} recorded decisions; tool evidence and scoped facts verified; approval pending")


if __name__=='__main__':
    main()
