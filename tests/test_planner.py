import tempfile,unittest,json,copy
from pathlib import Path
from motionbench.core import ROOT,make_run,read,save
from motionbench.planner import JOINTS,SYSTEM_PROMPT,DryRunBackend,build_request,check_plan,plan_run,public_dictionary
POSE={'pelvis':(0,0,.99),'neck':(0,0,1.48),'head':(0,-.015,1.69)}
for s,x in [('L',1),('R',-1)]:POSE.update({s+'hip':(x*.12,0,.98),s+'knee':(x*.13,-.015,.55),s+'ankle':(x*.14,0,.12),s+'shoulder':(x*.23,0,1.43),s+'elbow':(x*.31,-.01,1.17),s+'wrist':(x*.35,-.07,.96)})
def points(pose):return [{'joint':j,'x':pose[j][0],'y':pose[j][1],'z':pose[j][2]} for j in JOINTS]
def valid_plan(request):
 raised=dict(POSE,Relbow=(-.45,-.05,1.40),Rwrist=(-.50,-.10,1.62))
 return {'initial_pose':{'pose_class':'standing','observations':['arms down'],'uncertainties':[],'joints':points(POSE),'contacts':['both feet on floor']},
  'actions':[{'id':'a1','request_quote':request[:5],'side':'right','repetitions':2,'completion':'hand back down'}],
  'retrieval':[{'entry_id':'wave_right','used_for':'raise-wave-lower'}],
  'keyframes':[{'time_s':0,'origin':'observed','action_id':None,'description':'start','joints':points(POSE),'contacts':[]},{'time_s':2,'origin':'retrieved','action_id':'a1','description':'raised','joints':points(raised),'contacts':[]},{'time_s':5,'origin':'retrieved','action_id':'a1','description':'down','joints':points(POSE),'contacts':[]}],
  'assumptions':[],'unsupported_requirements':[]}
class FakeBackend:
 name='fake';model='fixture'
 def __init__(self,plan=None,transport_error=None):self.plan=plan;self.transport_error=transport_error;self.calls=0
 def call(self,request):
  self.calls+=1
  if self.transport_error:return {'transport_error':self.transport_error,'stdout':''}
  return {'plan':self.plan(request) if callable(self.plan) else self.plan,'stdout':''}
def request_text(request):return request['text'].split('Request (verbatim): ',1)[1].split('\n',1)[0]
class PlannerTests(unittest.TestCase):
 def run_dir(self,d,split='development'):run=Path(d)/'r';make_run(run,split,1);return run
 def test_request_has_no_evaluator_content(self):
  with tempfile.TemporaryDirectory() as d:
   run=self.run_dir(d);contracts=read(ROOT/'benchmark/evaluator/contracts.json')
   for packet in read(run/'generator_inputs.json'):
    if not packet['paired_reference_group']:continue
    body=json.dumps(build_request(packet),ensure_ascii=False)+SYSTEM_PROMPT
    self.assertNotIn('evaluator',body);self.assertNotIn('disallowed_test_families',body)
    for c in contracts:
     for r in c['requirements']+c['shared_requirements']:self.assertNotIn(r['criterion'],body)
 def test_held_out_families_not_in_dictionary(self):
  d=public_dictionary();self.assertFalse({'bow','cross_arms'}&set(json.dumps(d).split('"')))
 def test_dry_run_calls_nothing_and_keeps_pending(self):
  with tempfile.TemporaryDirectory() as d:
   run=self.run_dir(d);result=plan_run(run,DryRunBackend())
   self.assertEqual(len(result['groups']),8);self.assertEqual(result['calls'],0)
   self.assertTrue(all(r['status']=='pending' and not r['outputs'] for r in read(run/'ledger.json')))
   self.assertTrue((run/'plans/D01-01/request.json').is_file());self.assertIsNone(read(run/'run.json')['configuration']['planner_model'])
 def test_valid_plan_shared_by_reference_arms_only(self):
  with tempfile.TemporaryDirectory() as d:
   run=self.run_dir(d);backend=FakeBackend(lambda q:valid_plan(request_text(q)));result=plan_run(run,backend,max_calls=2)
   self.assertEqual(backend.calls,2);self.assertEqual([g['status'] for g in result['groups']],['planned','planned'])
   rows=[r for r in read(run/'ledger.json') if r['case_id']=='D01']
   plans={r['outputs']['plan']['sha256'] for r in rows if r['arm']!='direct_i2v'};self.assertEqual(len(plans),1)
   self.assertFalse([r for r in rows if r['arm']=='direct_i2v'][0]['outputs'])
   self.assertEqual(read(run/'run.json')['configuration']['planner_model'],'fixture')
 def test_reset_pose_plan_recorded_as_planning_failure(self):
  with tempfile.TemporaryDirectory() as d:
   run=self.run_dir(d)
   def bad(q):
    p=valid_plan(request_text(q));p['keyframes'][0]['origin']='inferred';return p
   result=plan_run(run,FakeBackend(bad),max_calls=1);self.assertEqual(result['groups'][0]['status'],'failed')
   rows=[r for r in read(run/'ledger.json') if r['case_id']=='D01' and r['arm']!='direct_i2v']
   self.assertTrue(all(r['status']=='failed' and r['failure_stage']=='planning' and 'plan' not in r['outputs'] and 'execution_log' in r['outputs'] for r in rows))
 def test_transport_retried_once_then_failed(self):
  with tempfile.TemporaryDirectory() as d:
   run=self.run_dir(d);backend=FakeBackend(transport_error='timeout');plan_run(run,backend,max_calls=1)
   self.assertEqual(backend.calls,2);self.assertFalse(read(run/'plans/D01-01/log.json')['ok'])
 def test_planned_group_not_called_again(self):
  with tempfile.TemporaryDirectory() as d:
   run=self.run_dir(d);backend=FakeBackend(lambda q:valid_plan(request_text(q)));plan_run(run,backend,max_calls=1);plan_run(run,backend,max_calls=1)
   self.assertEqual(sorted(p.name for p in (run/'plans').iterdir()),['D01-01','D02-01'])
 def test_quote_must_be_verbatim(self):
  with tempfile.TemporaryDirectory() as d:
   packet=next(p for p in read(self.run_dir(d)/'generator_inputs.json') if p['paired_reference_group'])
   plan=valid_plan(packet['request']);plan['actions'][0]['request_quote']='paraphrase'
   self.assertTrue(any('verbatim' in e for e in check_plan(plan,packet,public_dictionary())['errors']))
 def test_bone_stretch_is_warning(self):
  with tempfile.TemporaryDirectory() as d:
   packet=next(p for p in read(self.run_dir(d)/'generator_inputs.json') if p['paired_reference_group'])
   plan=valid_plan(packet['request']);plan['keyframes'][1]['joints']=points(dict(POSE,Rwrist=(-.35,-.07,.50)))
   check=check_plan(plan,packet,public_dictionary());self.assertFalse(check['errors']);self.assertTrue(check['warnings'])
 def test_test_split_refused(self):
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaises(ValueError):plan_run(self.run_dir(d,'test'),DryRunBackend())
 def test_mixing_planner_models_refused(self):
  with tempfile.TemporaryDirectory() as d:
   run=self.run_dir(d);plan_run(run,FakeBackend(lambda q:valid_plan(request_text(q))),max_calls=1);other=FakeBackend();other.model='other'
   with self.assertRaises(ValueError):plan_run(run,other)
 def test_packet_with_extra_fields_refused(self):
  with tempfile.TemporaryDirectory() as d:
   packet=next(p for p in read(self.run_dir(d)/'generator_inputs.json') if p['paired_reference_group']);packet['requirements']=['leak']
   with self.assertRaises(ValueError):build_request(packet)
if __name__=='__main__':unittest.main()
