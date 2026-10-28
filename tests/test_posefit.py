import math,tempfile,unittest
from pathlib import Path
from unittest import mock
from motionbench.core import make_run,read
from motionbench.planner import plan_run,_joints
from motionbench import posefit
from motionbench.posefit import POSE_SCHEMA,STEPS,transform,iou,score
from motionbench.animate import segment_lengths
from tests.test_planner import POSE,points,valid_plan,request_text
class PoseBackend:
 """Answers the pose call with a slightly wrong standing pose and the plan call with a valid plan."""
 name='fake';model='fixture'
 def __init__(self,pose_error=None):self.calls=[];self.pose_error=pose_error
 def call(self,request):
  self.calls.append(request)
  if request.get('schema') is POSE_SCHEMA:
   if self.pose_error:return {'transport_error':self.pose_error,'stdout':''}
   return {'plan':{'pose_class':'standing','observations':[],'uncertainties':[],'joints':points(dict(POSE,pelvis=(0,0,.95))),'contacts':[]},'stdout':''}
  return {'plan':valid_plan(request_text(request)),'stdout':''}
def fake_fit(image,pose,blender,workdir=None):
 return dict(pose,joints=points(POSE)),{'score_start':.5,'score_end':.8}
class PoseFitTests(unittest.TestCase):
 def test_rotations_keep_segment_lengths(self):
  moved=transform(POSE,{'lean_side':20,'lean_front':-10,'Larm_side':30,'Rarm_front':-40,'Lelbow':25,'Relbow':-60});rest=segment_lengths(POSE)
  for seg,length in segment_lengths(moved).items():self.assertAlmostEqual(length,rest[seg],places=9)
 def test_lean_keeps_arms_hanging(self):
  moved=transform(POSE,{'lean_side':20})
  for s in 'LR':
   before=[POSE[s+'wrist'][i]-POSE[s+'shoulder'][i] for i in range(3)];after=[moved[s+'wrist'][i]-moved[s+'shoulder'][i] for i in range(3)]
   self.assertLess(math.dist(before,after),1e-9)
  self.assertGreater(moved['neck'][0],POSE['neck'][0])
 def test_scale_keeps_feet_on_floor_line(self):
  moved=transform(POSE,{'scale':.1});self.assertAlmostEqual(moved['Lankle'][2],POSE['Lankle'][2]*1.1)
  self.assertAlmostEqual(moved['pelvis'][0],POSE['pelvis'][0])
 def test_score_is_mean_of_silhouette_and_skin(self):
  a=([True,True,False,False],[True,False,False,False]);b=([True,False,False,False],[True,False,False,False])
  self.assertAlmostEqual(iou(a[0],b[0]),.5);self.assertAlmostEqual(score(a,b),.75)
 def test_steps_cover_stages(self):self.assertEqual(set(posefit.STAGES[-1]),set(STEPS))
 def test_fitted_pose_is_fixed_in_plan(self):
  with tempfile.TemporaryDirectory() as d:
   run=Path(d)/'r';make_run(run,'development',1);backend=PoseBackend()
   with mock.patch.object(posefit,'fit',fake_fit):result=plan_run(run,backend,max_calls=1,pose_fit='blender')
   self.assertEqual(result['groups'][0]['status'],'planned');self.assertEqual(len(backend.calls),2)
   self.assertIn('already fitted',backend.calls[1]['text'])
   plan=read(run/'plans/D01-01/plan.json');self.assertEqual(plan['keyframes'][0]['joints'],points(POSE));self.assertEqual(plan['initial_pose']['joints'],points(POSE))
   log=read(run/'plans/D01-01/log.json');self.assertEqual(log['variant'],'posefit-v1');self.assertEqual([t['stage'] for t in log['tries']],['initial_pose','planning'])
   self.assertEqual(read(run/'run.json')['configuration']['planner_variant'],'posefit-v1')
 def test_pose_call_failure_recorded_as_initial_pose_stage(self):
  with tempfile.TemporaryDirectory() as d:
   run=Path(d)/'r';make_run(run,'development',1)
   with mock.patch.object(posefit,'fit',fake_fit):plan_run(run,PoseBackend(pose_error='timeout'),max_calls=1,pose_fit='blender')
   rows=[r for r in read(run/'ledger.json') if r['case_id']=='D01' and r['arm']!='direct_i2v']
   self.assertTrue(all(r['status']=='failed' and r['failure_stage']=='initial_pose' for r in rows))
 def test_variants_not_mixed_in_one_run(self):
  with tempfile.TemporaryDirectory() as d:
   run=Path(d)/'r';make_run(run,'development',1)
   with mock.patch.object(posefit,'fit',fake_fit):plan_run(run,PoseBackend(),max_calls=1,pose_fit='blender')
   with self.assertRaises(ValueError):plan_run(run,PoseBackend(),max_calls=1)
if __name__=='__main__':unittest.main()
