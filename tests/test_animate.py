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
if __name__=='__main__':unittest.main()
