import tempfile,unittest
from pathlib import Path
from unittest import mock
from motionbench.core import make_run,read,save,artifact
from motionbench import reference,verify
from motionbench.verify import VERDICT_SCHEMA,verify_group
from motionbench.planner import PLAN_SCHEMA
from tests.test_planner import valid_plan,request_text
MP4=b'\0\0\0\x18ftypisom'
def fake_render(plan,duration_s,image,out,blender=None,fps=24,root=None):
 out=Path(out);out.mkdir(parents=True,exist_ok=True);(out/'reference.mp4').write_bytes(MP4+repr(plan['keyframes'][1]['time_s']).encode())
 for name in ('grid_input.png','grid_front.png'):(out/name).write_bytes(b'png')
 t={'grid_times_s':[0,1],'first_frame_match':.9,'unreachable_targets':{}};save(out/'telemetry.json',t);return t
class Reviewer:
 """Scripted reviewer: verdicts are consumed in order; plan requests get a valid plan with a shifted keyframe so the repaired video differs."""
 name='fake';model='fixture'
 def __init__(self,verdicts):self.verdicts=list(verdicts);self.calls=[]
 def call(self,request):
  self.calls.append(request)
  if request.get('schema') is VERDICT_SCHEMA:
   v=self.verdicts.pop(0);return {'plan':None if v is None else {'requirements':[{'id':'r1','quote':'오른손','status':'pass' if v=='pass' else 'fail','evidence':'frames 2-5'}],'first_frame':{'matches_input':True,'notes':''},'verdict':v,'repair_instructions':[] if v=='pass' else ['raise the right hand higher']},'stdout':''}
  plan=valid_plan(request_text(request));plan['keyframes'][1]['time_s']=2.5;return {'plan':plan,'stdout':''}
class VerifyTests(unittest.TestCase):
 def setup_run(self,d):
  run=Path(d)/'r';make_run(run,'development',1);plan=valid_plan(read(run/'generator_inputs.json')[0]['request'])
  (run/'plans/D01-01').mkdir(parents=True);save(run/'plans/D01-01/plan.json',plan)
  fake_render(plan,6,None,run/'references/D01-01');return run
 def rows(self,run):return {r['arm']:r for r in read(run/'ledger.json') if r['case_id']=='D01'}
 def test_pass_keeps_initial_reference_for_both_arms(self):
  with tempfile.TemporaryDirectory() as d:
   run=self.setup_run(d);backend=Reviewer(['pass'])
   with mock.patch.object(reference,'render_plan',fake_render):result=verify_group(run,'D01-01',backend)
   self.assertEqual(result['decision'],'pass');self.assertEqual(len(backend.calls),1);rows=self.rows(run)
   self.assertEqual(rows['llm_reference_r2v']['outputs']['reference_initial']['sha256'],rows['verified_reference_r2v']['outputs']['reference_initial']['sha256'])
   self.assertNotIn('reference_repaired',rows['verified_reference_r2v']['outputs']);self.assertIn('gate_decision',rows['verified_reference_r2v']['outputs'])
   self.assertNotIn('gate_decision',rows['llm_reference_r2v']['outputs'])
 def test_repair_then_pass_registers_repaired_on_c_only(self):
  with tempfile.TemporaryDirectory() as d:
   run=self.setup_run(d);backend=Reviewer(['repair','pass'])
   with mock.patch.object(reference,'render_plan',fake_render):result=verify_group(run,'D01-01',backend)
   self.assertEqual(result['decision'],'pass');self.assertEqual(result['reference_for_final'],'repaired');self.assertEqual(len(backend.calls),3)
   self.assertIn('Reviewer findings',backend.calls[1]['text']);rows=self.rows(run)
   self.assertIn('reference_repaired',rows['verified_reference_r2v']['outputs']);self.assertNotIn('reference_repaired',rows['llm_reference_r2v']['outputs'])
   self.assertEqual(rows['verified_reference_r2v']['status'],'pending')
 def test_second_failure_blocks_c_not_b(self):
  with tempfile.TemporaryDirectory() as d:
   run=self.setup_run(d)
   with mock.patch.object(reference,'render_plan',fake_render):result=verify_group(run,'D01-01',Reviewer(['repair','repair']))
   self.assertEqual(result['decision'],'blocked');rows=self.rows(run)
   self.assertEqual(rows['verified_reference_r2v']['status'],'blocked');self.assertEqual(rows['verified_reference_r2v']['failure_stage'],'reference_review')
   self.assertEqual(rows['llm_reference_r2v']['status'],'pending')
 def test_unreadable_review_blocks(self):
  with tempfile.TemporaryDirectory() as d:
   run=self.setup_run(d)
   with mock.patch.object(reference,'render_plan',fake_render):result=verify_group(run,'D01-01',Reviewer([None,None]))
   self.assertEqual(result['decision'],'blocked')
 def test_reviewer_gets_rendered_frames_not_plan(self):
  with tempfile.TemporaryDirectory() as d:
   run=self.setup_run(d);backend=Reviewer(['pass'])
   with mock.patch.object(reference,'render_plan',fake_render):verify_group(run,'D01-01',backend)
   call=backend.calls[0];self.assertEqual([Path(i).name for i in call['images'][1:]],['grid_input.png','grid_front.png'])
   self.assertNotIn('keyframes',call['text']);self.assertNotIn('evaluator',call['text'])
 def test_second_run_is_skipped(self):
  with tempfile.TemporaryDirectory() as d:
   run=self.setup_run(d)
   with mock.patch.object(reference,'render_plan',fake_render):
    verify_group(run,'D01-01',Reviewer(['pass']));self.assertIn('skipped',verify_group(run,'D01-01',Reviewer(['pass'])))
if __name__=='__main__':unittest.main()
