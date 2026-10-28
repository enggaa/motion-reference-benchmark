import copy,math,tempfile,unittest
from pathlib import Path
from motionbench.core import make_run
from motionbench.animate import animate,segment_lengths,keyframe_poses
from motionbench.reference import render_group
from tests.test_planner import POSE,points,valid_plan
def lengths_of(frame):return segment_lengths({j:tuple(v) for j,v in frame['joints'].items()})
class AnimateTests(unittest.TestCase):
 def test_frame_count_and_start_pose(self):
  plan=valid_plan('오른손을 흔들어라');frames,telemetry=animate(plan,6,24)
  self.assertEqual(len(frames),145);self.assertEqual(telemetry['frames'],145)
  self.assertLess(max(math.dist(frames[0]['joints'][j],POSE[j]) for j in POSE),1e-3)
 def test_segment_lengths_fixed_every_frame(self):
  plan=valid_plan('오른손을 흔들어라');frames,telemetry=animate(plan,6,24);rest=segment_lengths(POSE)
  for f in frames:
   for seg,length in lengths_of(f).items():self.assertAlmostEqual(length,rest[seg],places=3)
  self.assertLess(telemetry['max_segment_length_error_m'],1e-9)
 def test_stretched_plan_is_not_stretched_in_output(self):
  plan=valid_plan('오른손을 흔들어라');plan['keyframes'][1]['joints']=points(dict(POSE,Relbow=(-.23,-.40,1.43),Rwrist=(-.23,-.80,1.43)))
  frames,telemetry=animate(plan,6,24);rest=segment_lengths(POSE)
  self.assertAlmostEqual(lengths_of(frames[48])['Relbow','Rwrist'],rest['Relbow','Rwrist'],places=4)
  self.assertGreater(telemetry['max_keyframe_error_m']['Rwrist'],.2)
 def test_planted_feet_stay_planted(self):
  plan=valid_plan('오른손을 흔들어라');frames,_=animate(plan,6,24)
  for f in frames:
   for a in ('Lankle','Rankle'):self.assertLess(math.dist(f['joints'][a],POSE[a]),1e-4)
 def test_unreachable_ankle_clamped_and_logged(self):
  plan=valid_plan('오른손을 흔들어라');lifted=dict(POSE,pelvis=(0,0,1.6),neck=(0,0,2.09),head=(0,-.015,2.3),Lhip=(.12,0,1.59),Rhip=(-.12,0,1.59))
  plan['keyframes'][1]['joints']=points(lifted);frames,telemetry=animate(plan,6,24)
  self.assertIn('Lankle',telemetry['unreachable_targets']);self.assertAlmostEqual(lengths_of(frames[48])['Lknee','Lankle'],segment_lengths(POSE)['Lknee','Lankle'],places=4)
 def test_chair_prop_from_plan_only(self):
  plan=valid_plan('앉아라');self.assertFalse(animate(plan,6)[1]['props']['chair'])
  plan['initial_pose']['pose_class']='seated';self.assertTrue(animate(plan,6)[1]['props']['chair'])
 def test_render_needs_accepted_plan(self):
  with tempfile.TemporaryDirectory() as d:
   run=Path(d)/'r';make_run(run,'development',1)
   with self.assertRaises(ValueError):render_group(run,'D01-01',blender='unused')
 def test_turning_points_ignore_jitter(self):
  from motionbench.animate import turning_points
  times=[i/10 for i in range(21)];wave=[.1*math.sin(2*math.pi*t)+.005*((-1)**i) for i,t in enumerate(times)]
  turns=turning_points(times,wave,.04);self.assertEqual([k for _,_,k in turns],['max','min','max','min']);self.assertEqual(turning_points(times,[.005*((-1)**i) for i in range(41)],.04),[])
 def test_motion_summary_counts_rendered_waves(self):
  from motionbench.animate import motion_summary
  plan=valid_plan('오른손을 흔들어라');raised=dict(POSE,Relbow=(-.45,-.05,1.40),Rwrist=(-.50,-.10,1.62));inward=dict(raised,Rwrist=(-.30,-.10,1.60))
  plan['keyframes']=[plan['keyframes'][0]]+[{'time_s':t,'origin':'inferred','action_id':'a1','description':'','joints':points(p),'contacts':[]} for t,p in [(1,raised),(1.5,inward),(2,raised),(2.5,inward),(3,raised),(4.5,POSE)]]
  frames,_=animate(plan,6,24);m=motion_summary(frames,24)
  self.assertGreaterEqual(len(m['right_wrist']['lateral_turns']),4);self.assertEqual(m['left_wrist']['lateral_turns'],[])
  self.assertTrue(m['right_wrist']['near_or_above_shoulder_s']);self.assertEqual(m['whole_body_still_s'][-1][1],6.0)
if __name__=='__main__':unittest.main()
