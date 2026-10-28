import tempfile,unittest,json,copy
from pathlib import Path
from motionbench.core import ROOT,ARMS,validate,make_run,read,save,summarize,consensus,record,artifact
class BenchmarkTests(unittest.TestCase):
 def test_manifest_assets_and_coverage(self):self.assertTrue(validate()['valid'],validate())
 def test_unseen_test_families_disjoint(self):
  cases=read(ROOT/'benchmark/cases.json');test={c['action_family'] for c in cases if c['split']=='test' and c['dictionary_relationship']=='unseen'};other={c['action_family'] for c in cases if c['split']!='test'};self.assertFalse(test&other)
 def test_generator_has_no_ground_truth(self):
  with tempfile.TemporaryDirectory() as d:
   make_run(Path(d)/'r','development',1);packets=read(Path(d)/'r/generator_inputs.json');self.assertEqual(len(packets),24)
   for p in packets:self.assertFalse({'requirements','joints','expected','contracts'}&set(p))
 def test_pending_is_not_zero_performance(self):
  with tempfile.TemporaryDirectory() as d:
   run=Path(d)/'r';make_run(run,'development',1);s=summarize(run)
   self.assertTrue(all(a['primary_case_mean'] is None for a in s['arms'].values()))
 def test_failed_attempts_stay_in_denominator(self):
  with tempfile.TemporaryDirectory() as d:
   run=Path(d)/'r';make_run(run,'development',1);rows=read(run/'ledger.json')
   for row in rows:row['status']='failed';row['failure_stage']='planning'
   save(run/'ledger.json',rows);s=summarize(run);self.assertTrue(all(a['primary_case_mean']==0 and a['assigned']==8 for a in s['arms'].values()))
 def test_same_rater_cannot_vote_twice(self):
  r={'ratings':[{'rater_id':'A','requirements':{'R1':'pass'}},{'rater_id':'A','requirements':{'R1':'pass'}}]}
  with self.assertRaises(ValueError):consensus(r,['R1'])
 def test_disagreement_not_hidden_by_overall_pass(self):
  r={'ratings':[{'rater_id':'A','requirements':{'R1':'pass','R2':'fail'}},{'rater_id':'B','requirements':{'R1':'fail','R2':'pass'}}]};self.assertEqual(consensus(r,['R1','R2']),'disputed')
 def test_uncertain_not_pass(self):
  r={'ratings':[{'rater_id':name,'requirements':{'R1':'uncertain'}} for name in ['A','B']]};self.assertEqual(consensus(r,['R1']),'uncertain')
 def test_missing_requirement_rejected(self):
  r={'ratings':[{'rater_id':name,'requirements':{'R1':'pass'}} for name in ['A','B']]}
  with self.assertRaises(ValueError):consensus(r,['R1','R2'])
 def test_independent_adjudicator(self):
  r={'ratings':[{'rater_id':'A','requirements':{'R1':'pass'}},{'rater_id':'B','requirements':{'R1':'fail'}}],'adjudication':{'rater_id':'A','requirements':{'R1':'pass'}}}
  with self.assertRaises(ValueError):consensus(r,['R1'])
 def test_fake_success_without_video_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   run=Path(d)/'r';make_run(run,'development',1)
   with self.assertRaises(ValueError):record(run,'0001','succeeded')
 def test_terminal_attempt_cannot_be_overwritten(self):
  with tempfile.TemporaryDirectory() as d:
   run=Path(d)/'r';make_run(run,'development',1);record(run,'0001','blocked','planning')
   with self.assertRaises(ValueError):record(run,'0001','failed','retargeting')
 def test_reference_arms_share_candidate_group(self):
  with tempfile.TemporaryDirectory() as d:
   run=Path(d)/'r';make_run(run,'test',1);rows=read(run/'ledger.json')
   for cid in {r['case_id'] for r in rows}:
    refs=[r['paired_reference_group'] for r in rows if r['case_id']==cid and r['arm']!='direct_i2v'];self.assertEqual(refs[0],refs[1])
 def test_changed_benchmark_binding_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   run=Path(d)/'r';make_run(run,'development',1);meta=read(run/'run.json');meta['cases_sha256']='wrong';save(run/'run.json',meta)
   with self.assertRaises(ValueError):summarize(run)
 def test_pair_cannot_register_different_initial_references(self):
  with tempfile.TemporaryDirectory() as d:
   run=Path(d)/'r';make_run(run,'development',1);rows=read(run/'ledger.json');refs=[r for r in rows if r['case_id']=='D01' and r['arm']!='direct_i2v']
   a=Path(d)/'a.mp4';b=Path(d)/'b.mp4';a.write_bytes(b'\0\0\0\x18ftypisomfixtureA');b.write_bytes(b'\0\0\0\x18ftypisomfixtureB')
   artifact(run,refs[0]['attempt_id'],'reference_initial',a)
   with self.assertRaises(ValueError):artifact(run,refs[1]['attempt_id'],'reference_initial',b)
 def test_unverified_arm_cannot_repair(self):
  with tempfile.TemporaryDirectory() as d:
   run=Path(d)/'r';make_run(run,'development',1);row=next(r for r in read(run/'ledger.json') if r['arm']=='llm_reference_r2v');p=Path(d)/'a.mp4';p.write_bytes(b'\0\0\0\x18ftypisomfixture')
   with self.assertRaises(ValueError):artifact(run,row['attempt_id'],'reference_repaired',p)
if __name__=='__main__':unittest.main()
