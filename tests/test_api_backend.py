import json,sys,types,unittest
from pathlib import Path
from unittest import mock
from motionbench.core import ROOT
from motionbench.planner import PLAN_SCHEMA,SYSTEM_PROMPT
def fake_sdk():
 m=types.ModuleType('anthropic')
 class APIConnectionError(Exception):pass
 class RateLimitError(Exception):pass
 class APIStatusError(Exception):
  def __init__(self,msg,status_code):super().__init__(msg);self.status_code=status_code
 m.APIConnectionError,m.RateLimitError,m.APIStatusError=APIConnectionError,RateLimitError,APIStatusError
 m.Anthropic=lambda:None
 return m
class Usage:
 def to_dict(self):return {'input_tokens':1000,'output_tokens':2000}
class Message:
 def __init__(self,text,stop='end_turn'):self.model='claude-sonnet-5-5';self.usage=Usage();self.stop_reason=stop;self.content=[types.SimpleNamespace(type='text',text=text)];self._request_id='req_1'
class Client:
 def __init__(self,result):self.result=result;self.kwargs=None;self.messages=self
 def stream(self,**kwargs):
  self.kwargs=kwargs;client=self
  class Ctx:
   def __enter__(s):
    if isinstance(client.result,Exception):raise client.result
    return types.SimpleNamespace(get_final_message=lambda:client.result)
   def __exit__(s,*a):return False
  return Ctx()
IMAGE=str(ROOT/'benchmark/images/D01.png')
class APIBackendTests(unittest.TestCase):
 def backend(self,result):
  sdk=fake_sdk()
  with mock.patch.dict(sys.modules,{'anthropic':sdk}):
   from motionbench.planner import AnthropicAPIBackend
   return AnthropicAPIBackend('sonnet',client=Client(result(sdk) if callable(result) else result)),sdk
 def test_request_shape_and_parsed_plan(self):
  b,_=self.backend(Message('{"a": 1}'));out=b.call({'image':IMAGE,'text':'hello'});k=b.client.kwargs
  self.assertEqual(out['plan'],{'a':1});self.assertEqual(k['model'],'claude-sonnet-5-5');self.assertEqual(k['system'],SYSTEM_PROMPT)
  self.assertEqual(k['output_config']['format'],{'type':'json_schema','schema':PLAN_SCHEMA});self.assertNotIn('fallbacks',k);self.assertNotIn('tool_choice',k)
  self.assertEqual([c['type'] for c in k['messages'][0]['content']],['image','text']);self.assertAlmostEqual(out['estimated_usd'],.022)
 def test_refusal_is_not_retried_or_parsed(self):
  b,_=self.backend(Message('',stop='refusal'));out=b.call({'image':IMAGE,'text':'x'})
  self.assertIsNone(out['plan']);self.assertNotIn('transport_error',out);self.assertIn('refusal',out)
 def test_rate_limit_is_transport_error(self):
  b,_=self.backend(lambda sdk:sdk.RateLimitError('slow down'));self.assertIn('transport_error',b.call({'image':IMAGE,'text':'x'}))
 def test_bad_request_is_not_transport(self):
  b,_=self.backend(lambda sdk:sdk.APIStatusError('bad schema',400));out=b.call({'image':IMAGE,'text':'x'})
  self.assertNotIn('transport_error',out);self.assertIn('error',out)
 def test_custom_schema_and_images_passed_through(self):
  b,_=self.backend(Message('{}'));b.call({'images':[IMAGE,IMAGE],'text':'x','system_prompt':'S','schema':{'type':'object'}})
  self.assertEqual(b.client.kwargs['system'],'S');self.assertEqual(len(b.client.kwargs['messages'][0]['content']),3)
if __name__=='__main__':unittest.main()
