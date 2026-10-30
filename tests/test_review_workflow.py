"""The public agent example must remain scoped, reproducible and unapproved."""
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'agents'))
import review_workflow as agent


class AgentChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Explicit test doubles exercise the protocol without claiming a live run.
        calls=iter([
            {'action':'request','requests':[{'name':'scorecard','business_unit':'Brand Events','note_ids':[]},
                                          {'name':'driver_splits','business_unit':'Brand Events','note_ids':[]},
                                          {'name':'business_notes','business_unit':'Brand Events','note_ids':['N11','N13']}],
             'fact_ids':[],'evidence_ids':[],'questions':[]},
            {'action':'finish','requests':[],'fact_ids':['brand_loss','basis','overrun'],'evidence_ids':['N11','N13'],
             'questions':['Can the controller confirm the source billings entry?']},
            {'action':'finish','requests':[],'fact_ids':['brand_loss','basis','overrun'],'evidence_ids':['N11','N13'],
             'questions':['What project recovery remains open with the client?']},
            {'fact_ids':['brand_loss','basis','overrun'],'action_ids':['project_recovery','source_verification'],
             'questions':['Who will confirm the source billings entry?']}])
        cls.record=agent.run_workflow(lambda *args:(next(calls),{'model':'explicit test double'}))

    def test_record_recomputes_every_tool_result(self):
        self.assertEqual(agent.replay_record(self.record),self.record)
        if agent.RECORD.exists():
            captured=agent.read_json(agent.RECORD)
            self.assertEqual(agent.replay_record(captured),captured)
            self.assertEqual(agent.read_json('output/agent_review.json'),captured)

    def test_context_and_instructions_are_bound_to_inputs(self):
        altered=copy.deepcopy(self.record)
        altered['input_hashes']['data/company_context.json']='changed'
        with self.assertRaisesRegex(ValueError,'stale'):
            agent.replay_record(altered)

    def test_git_line_endings_do_not_invalidate_text_inputs(self):
        normalized={path:Path(path).read_bytes().replace(b'\r\n',b'\n') for path in agent.INPUTS}
        expected=agent.fingerprint()
        with patch.object(Path,'read_bytes',lambda path:normalized[path.as_posix()].replace(b'\n',b'\r\n')):
            self.assertEqual(agent.fingerprint(),expected)

    def test_tampered_result_is_rejected(self):
        altered=copy.deepcopy(self.record)
        event=next(e for e in altered['events'] if e.get('results'))
        event['results'][0]['result']={'made_up':123}
        with self.assertRaises(ValueError):
            agent.replay_record(altered)

    def test_wrong_unit_and_unknown_tool_fail(self):
        tools=agent.FinancialTools('Brand Events')
        for name,unit in [('scorecard','Corporate Events'),('write_source','Brand Events'),('../../data/ground_truth.md','Brand Events')]:
            with self.subTest(name=name,unit=unit),self.assertRaises(ValueError):
                tools.call(dict(name=name,business_unit=unit,note_ids=[]))

    def test_other_unit_evidence_is_not_available(self):
        tools=agent.FinancialTools('Brand Events')
        with self.assertRaisesRegex(ValueError,'another unit'):
            tools.call(dict(name='business_notes',business_unit='Brand Events',note_ids=['N12']))

    def test_generated_question_cannot_supply_money(self):
        for question in ['Could we explain the EUR500k recovery?', 'Did margin rise 10%?', 'Could this require a 500000 recovery?', 'The overrun is solved.']:
            with self.assertRaises(ValueError):
                agent.check_questions([question])

    def test_missing_loss_or_unretrieved_citation_fails(self):
        for field,value in [('fact_ids',[]),('evidence_ids',['N99'])]:
            altered=copy.deepcopy(self.record)
            event=next(e for e in altered['events'] if e['role']=='investigator' and e['decision']['action']=='finish')
            event['decision'][field]=value
            with self.assertRaises(ValueError):
                agent.replay_record(altered)

    def test_questions_and_actions_are_pending_review(self):
        self.assertIn('Pending analyst review',self.record['approval_status'])
        self.assertIn('illustrative',self.record['scenario']['label'].lower())
        report=agent.render_report(self.record)
        self.assertIn('AI-generated and need human review',report)
        for fact in self.record['selected_facts']:
            self.assertIn(f"Scope: {fact['business_unit']} | {fact['period']}",report)
        self.assertIn('Note N13 already records a signed change order',report)
        for event in self.record['events']:
            self.assertIn(event['role'],['investigator','reporter'])
            self.assertIn('model',event['provider'])

    def test_generated_questions_cannot_inject_html(self):
        altered=copy.deepcopy(self.record)
        altered['questions']=['Could <script>alert(1)</script> change this review?']
        report=agent.render_report(altered)
        self.assertNotIn('<script>',report)
        self.assertIn('&lt;script&gt;',report)

    def test_bounded_loop_cannot_run_forever(self):
        request={'action':'request','requests':[{'name':'scorecard','business_unit':'Brand Events','note_ids':[]}],
                 'fact_ids':[],'evidence_ids':[],'questions':[]}
        with self.assertRaisesRegex(ValueError,'decision limit'):
            agent.run_workflow(lambda *args:(request,{'model':'test fixture'}))


if __name__=='__main__':
    unittest.main()
