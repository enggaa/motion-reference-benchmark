import tempfile,unittest
from pathlib import Path
from motionbench.core import make_run,read,save,artifact
from motionbench.video import generate_run,estimate_usd,prompt,MODELS
MP4=b'\0\0\0\x18ftypisom'
class FakeFal:
 name='fake-fal'
 def __init__(self,fail=False):self.calls=[];self.fail=fail
 def generate(self,model,payload,out):
  self.calls.append((model,payload))
  if self.fail:raise RuntimeError('content policy')
  Path(out).write_bytes(MP4+b'final');return {'request_id':'r','seed':1,'latency_s':1.0}
class VideoTests(unittest.TestCase):
 def run_with_refs(self,d,gate=None):
  run=Path(d)/'r';make_run(run,'development',1);ref=Path(d)/'ref.mp4';ref.write_bytes(MP4+b'ref');rows=[r for r in read(run/'ledger.json') if r['case_id']=='D01']
  for r in rows:
   if r['arm']!='direct_i2v':artifact(run,r['attempt_id'],'reference_initial',ref)
  if gate:
   c=next(r for r in rows if r['arm']=='verified_reference_r2v');g=Path(d)/'gate.json';save(g,gate)
   if gate.get('reference_for_final')=='repaired':rep=Path(d)/'rep.mp4';rep.write_bytes(MP4+b'repaired');artifact(run,c['attempt_id'],'reference_repaired',rep)
   artifact(run,c['attempt_id'],'gate_decision',g)
  return run,{r['arm']:r['attempt_id'] for r in rows}
 def test_estimate_matches_token_formula(self):
  self.assertAlmostEqual(estimate_usd('480p',6),480*640*6*24/1024/1000*.014,places=4)
  self.assertLess(estimate_usd('480p',6,6)/2,estimate_usd('480p',6))
 def test_prompts_share_request_and_suffix(self):
  a,b=prompt('direct_i2v','오른손을 흔들어라'),prompt('llm_reference_r2v','오른손을 흔들어라');self.assertIn('오른손을 흔들어라',a);self.assertTrue(b.endswith(a))
  self.assertIn('@Video1',b);self.assertNotIn('@Video1',a);self.assertEqual(prompt('llm_reference_r2v','x'),prompt('verified_reference_r2v','x'))
 def test_dry_run_plans_ready_attempts_only(self):
  with tempfile.TemporaryDirectory() as d:
   run,ids=self.run_with_refs(d);s=generate_run(run,attempts=list(ids.values()))
   self.assertEqual(s['planned'],2);self.assertEqual(s['skipped'],{ids['verified_reference_r2v']:'no gate decision yet'})
   req=read(run/'video_requests'/f"{ids['llm_reference_r2v']}.json");self.assertEqual(req['model'],MODELS['llm_reference_r2v'])
   self.assertNotIn('base64',str(req));self.assertEqual(req['payload']['duration'],'6');self.assertFalse(req['payload']['generate_audio'])
   self.assertTrue(all(r['status']=='pending' for r in read(run/'ledger.json')))
 def test_c_uses_repaired_reference_after_gate(self):
  with tempfile.TemporaryDirectory() as d:
   run,ids=self.run_with_refs(d,{'decision':'pass','reference_for_final':'repaired'});generate_run(run,attempts=[ids['verified_reference_r2v']])
   req=read(run/'video_requests'/f"{ids['verified_reference_r2v']}.json");self.assertTrue(req['payload']['video_urls'][0]['path'].endswith('rep.mp4'))
 def test_budget_cap_blocks_before_any_call(self):
  with tempfile.TemporaryDirectory() as d:
   run,ids=self.run_with_refs(d);fake=FakeFal()
   with self.assertRaises(ValueError):generate_run(run,fake,execute=True,max_usd=.01,attempts=list(ids.values()))
   self.assertEqual(fake.calls,[])
 def test_execute_records_success_and_cost(self):
  with tempfile.TemporaryDirectory() as d:
   run,ids=self.run_with_refs(d);fake=FakeFal();generate_run(run,fake,execute=True,max_usd=5,attempts=[ids['direct_i2v']])
   row=next(r for r in read(run/'ledger.json') if r['attempt_id']==ids['direct_i2v']);self.assertEqual(row['status'],'succeeded');self.assertEqual(row['model_ids']['video'],MODELS['direct_i2v'])
   self.assertIn('estimated_usd',row['cost']);self.assertEqual(fake.calls[0][0],MODELS['direct_i2v']);self.assertIn('image_url',fake.calls[0][1])
 def test_model_error_retried_once_then_failed(self):
  with tempfile.TemporaryDirectory() as d:
   run,ids=self.run_with_refs(d);fake=FakeFal(fail=True);generate_run(run,fake,execute=True,attempts=[ids['direct_i2v']])
   row=next(r for r in read(run/'ledger.json') if r['attempt_id']==ids['direct_i2v']);self.assertEqual(len(fake.calls),2)
   self.assertEqual((row['status'],row['failure_stage']),('failed','final_generation'))
 def test_test_split_needs_frozen_run(self):
  with tempfile.TemporaryDirectory() as d:
   run=Path(d)/'r';make_run(run,'test',1)
   with self.assertRaises(ValueError):generate_run(run,FakeFal(),execute=True)
if __name__=='__main__':unittest.main()
