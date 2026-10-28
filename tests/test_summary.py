import tempfile,unittest
from pathlib import Path
from motionbench.core import make_run,read,save,summarize,cluster_bootstrap,required_ids
def complete_run(d,passing_arm=None):
 """Every attempt succeeded with a dummy final video; the passing arm passes every requirement, the others fail R1."""
 run=Path(d)/'r';make_run(run,'development',1);rows=read(run/'ledger.json');video=Path(d)/'v.mp4';video.write_bytes(b'\0\0\0\x18ftypisom')
 from motionbench.core import sha
 for row in rows:
  ids=required_ids(row['case_id']);ok=row['arm']==passing_arm
  checks={k:('pass' if ok or k!=ids[0] else 'fail') for k in ids}
  row.update(status='succeeded',outputs={'final':{'path':str(video),'sha256':sha(video)}},review={'ratings':[{'rater_id':n,'requirements':checks,'secondary':{'naturalness':4 if n=='A' else 2,'start_continuity':'pass'}} for n in 'AB'],'adjudication':None})
 save(run/'ledger.json',rows);return run
class SummaryTests(unittest.TestCase):
 def test_bootstrap_is_deterministic_and_bounded(self):
  values={f'c{i}':v for i,v in enumerate([0,1,1,0,1,.5])};clusters={c:c for c in values}
  a=cluster_bootstrap(values,clusters,500,1);self.assertEqual(a,cluster_bootstrap(values,clusters,500,1));self.assertTrue(0<=a[0]<=a[1]<=1)
 def test_bootstrap_needs_two_clusters(self):self.assertIsNone(cluster_bootstrap({'a':1,'b':0},{'a':'f','b':'f'},100))
 def test_complete_run_reports_scores_intervals_and_secondary(self):
  with tempfile.TemporaryDirectory() as d:
   s=summarize(complete_run(d,'verified_reference_r2v'),draws=300)
   self.assertEqual(s['arms']['verified_reference_r2v']['primary_case_mean'],1.0);self.assertEqual(s['arms']['direct_i2v']['primary_case_mean'],0.0)
   diff=s['paired_case_mean_differences']['verified_reference_r2v_minus_direct'];self.assertEqual(diff['mean'],1.0);self.assertEqual(diff['ci95_case_bootstrap'],[1.0,1.0])
   self.assertEqual(s['arms']['direct_i2v']['secondary']['naturalness_case_mean'],3.0);self.assertEqual(s['arms']['direct_i2v']['secondary']['start_continuity']['pass_share'],1.0)
 def test_incomplete_run_has_no_interval(self):
  with tempfile.TemporaryDirectory() as d:
   run=Path(d)/'r';make_run(run,'development',1);s=summarize(run,draws=100)
   self.assertIsNone(s['arms']['direct_i2v']['primary_ci95_case_bootstrap']);self.assertEqual(s['paired_case_mean_differences'],{})
 def test_failure_stages_counted(self):
  with tempfile.TemporaryDirectory() as d:
   run=Path(d)/'r';make_run(run,'development',1);rows=read(run/'ledger.json')
   for r in rows:r.update(status='blocked',failure_stage='reference_review')
   save(run/'ledger.json',rows);self.assertEqual(summarize(run,draws=50)['arms']['verified_reference_r2v']['failure_stages'],{'reference_review':8})
if __name__=='__main__':unittest.main()
