import tempfile,unittest
from pathlib import Path
from unittest import mock
from motionbench.core import make_run,save
from motionbench import pipeline
class PipelineTests(unittest.TestCase):
 def test_stages_run_in_order_only_for_planned_groups(self):
  with tempfile.TemporaryDirectory() as d:
   run=Path(d)/'r';make_run(run,'development',1);calls=[]
   def fake_plan(run_,backend,max_groups,pose_fit=None):
    calls.append(('plan',pose_fit));(Path(run_)/'plans/D01-01').mkdir(parents=True);save(Path(run_)/'plans/D01-01/plan.json',{});return {'groups':[]}
   def fake_render(run_,gid,blender,register=False):calls.append(('render',gid,register));return {'first_frame_match':.8}
   def fake_verify(run_,gid,backend,blender):calls.append(('verify',gid));return {'decision':'pass','reference_for_final':'initial'}
   with mock.patch.object(pipeline,'plan_run',fake_plan),mock.patch.object(pipeline,'render_group',fake_render),mock.patch.object(pipeline,'verify_group',fake_verify):
    result=pipeline.run_pipeline(run,object(),blender='blender')
   self.assertEqual(calls,[('plan','blender'),('render','D01-01',True),('verify','D01-01')])
   self.assertEqual(result['groups'],{'D01-01':{'first_frame_match':.8,'gate':'pass','reference_for_final':'initial'}})
if __name__=='__main__':unittest.main()
