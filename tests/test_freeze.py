import tempfile,unittest
from pathlib import Path
from unittest import mock
from motionbench.core import make_run,read,save
from motionbench import freeze
from motionbench.freeze import freeze_run,check_frozen,fingerprint
from motionbench.planner import plan_run,DryRunBackend
from motionbench.video import generate_run
class FreezeTests(unittest.TestCase):
 def frozen_run(self,d):
  run=Path(d)/'r';make_run(run,'test',1)
  with mock.patch.object(freeze,'_git',lambda root,*a:'' if a[0]=='status' else 'abc123'):freeze_run(run,'sonnet','posefit-v1','480p',90)
  return run
 def test_fingerprint_stable(self):self.assertEqual(fingerprint(),fingerprint())
 def test_test_split_refuses_without_freeze(self):
  with tempfile.TemporaryDirectory() as d:
   run=Path(d)/'r';make_run(run,'test',1)
   with self.assertRaises(ValueError):plan_run(run,DryRunBackend())
   with self.assertRaises(ValueError):generate_run(run,max_usd=10)
 def test_frozen_run_accepts_matching_settings_only(self):
  with tempfile.TemporaryDirectory() as d:
   run=self.frozen_run(d);self.assertEqual(check_frozen(run,planner_model='sonnet')['git_head'],'abc123')
   with self.assertRaises(ValueError):check_frozen(run,planner_model='opus')
   with self.assertRaises(ValueError):generate_run(run,resolution='720p',max_usd=10)
   with self.assertRaises(ValueError):generate_run(run,resolution='480p',max_usd=500)
   self.assertEqual(generate_run(run,resolution='480p',max_usd=90)['planned'],12)
 def test_changed_pipeline_detected(self):
  with tempfile.TemporaryDirectory() as d:
   run=self.frozen_run(d);meta=read(run/'run.json');meta['frozen']['code_sha256']='old';save(run/'run.json',meta)
   with self.assertRaises(ValueError):check_frozen(run)
 def test_dirty_tree_and_double_freeze_refused(self):
  with tempfile.TemporaryDirectory() as d:
   run=Path(d)/'r';make_run(run,'test',1)
   with mock.patch.object(freeze,'_git',lambda root,*a:' M motionbench/planner.py' if a[0]=='status' else 'x'):
    with self.assertRaises(ValueError):freeze_run(run,'sonnet','posefit-v1','480p',90)
   run=self.frozen_run(Path(d)/'b')
   with self.assertRaises(ValueError):freeze_run(run,'sonnet','posefit-v1','480p',90)
 def test_cap_required(self):
  with tempfile.TemporaryDirectory() as d:
   run=Path(d)/'r';make_run(run,'test',1)
   with self.assertRaises(ValueError):freeze_run(run,'sonnet','posefit-v1','480p',None)
if __name__=='__main__':unittest.main()
