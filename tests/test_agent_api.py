import sys,os,unittest
from pathlib import Path
from types import SimpleNamespace as S
from unittest.mock import patch,Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'agents'))
import narrative_agent as agent

class ApiGuardTests(unittest.TestCase):
 def test_explicit_key_and_valid_structured_response(self):
  messages=Mock(); messages.count_tokens.return_value=S(input_tokens=1000)
  messages.create.return_value=S(stop_reason='tool_use',usage=S(input_tokens=1000,output_tokens=100),content=[S(type='tool_use',name='return_decision',input={'action':'finish'})])
  with patch('anthropic.Anthropic',return_value=S(messages=messages)) as factory,patch.object(agent,'_API_SPEND',0),patch.dict(os.environ,{'FPA_AGENT_BUDGET_USD':'1'}):
   result,metadata=agent.ask_api_json('system',{}, {'type':'object'},'test-only-key')
   self.assertEqual(result,{'action':'finish'})
   self.assertAlmostEqual(metadata['cost_usd'],.003)
   self.assertEqual(factory.call_args.kwargs['api_key'],'test-only-key')
   self.assertIsNone(factory.call_args.kwargs['auth_token'])
   self.assertEqual(factory.call_args.kwargs['max_retries'],0)
 def test_guard_stops_before_generation(self):
  messages=Mock(); messages.count_tokens.return_value=S(input_tokens=1000000)
  with patch('anthropic.Anthropic',return_value=S(messages=messages)),patch.object(agent,'_API_SPEND',0),patch.dict(os.environ,{'FPA_AGENT_BUDGET_USD':'1'}):
   with self.assertRaisesRegex(RuntimeError,'spend guard'):agent.ask_api_json('system',{}, {},'test-only-key')
   messages.create.assert_not_called()
 def test_incomplete_response_fails(self):
  messages=Mock(); messages.count_tokens.return_value=S(input_tokens=100)
  messages.create.return_value=S(stop_reason='max_tokens',usage=S(input_tokens=100,output_tokens=2000),content=[])
  with patch('anthropic.Anthropic',return_value=S(messages=messages)),patch.object(agent,'_API_SPEND',0),patch.dict(os.environ,{'FPA_AGENT_BUDGET_USD':'1'}):
   with self.assertRaises(RuntimeError):agent.ask_api_json('system',{}, {},'test-only-key')

if __name__=='__main__':unittest.main()
