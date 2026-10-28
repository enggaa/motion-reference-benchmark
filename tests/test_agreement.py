import tempfile,unittest
from pathlib import Path
from motionbench.core import make_run,read,save,artifact,ROOT
from motionbench.agreement import agreement,kappa
MP4=b'\0\0\0\x18ftypisom'
def rating(status):return {'R1':status,'R2':'pass','R3':'pass','R4':'pass','R5':'pass','S1':'pass','S2':'pass'}
class AgreementTests(unittest.TestCase):
 def test_kappa(self):
  self.assertEqual(kappa([('pass','pass'),('fail','fail')]),1.0);self.assertIsNone(kappa([]))
  self.assertLess(kappa([('pass','fail'),('fail','pass'),('pass','pass'),('fail','fail')]),.5)
 def test_matches_contract_quotes_and_counts_missed_failures(self):
  with tempfile.TemporaryDirectory() as d:
   run=Path(d)/'r';make_run(run,'development',1);rows=[r for r in read(run/'ledger.json') if r['case_id']=='D01' and r['arm']!='direct_i2v']
   ref=Path(d)/'reference.mp4';ref.write_bytes(MP4)
   for r in rows:artifact(run,r['attempt_id'],'reference_initial',ref)
   c=next(r for r in rows if r['arm']=='verified_reference_r2v');contract=next(x for x in read(ROOT/'benchmark/evaluator/contracts.json') if x['case_id']=='D01')
   quotes=[q['quote'] for q in contract['requirements']]
   gate={'steps':[{'step':'review_initial','verdict':{'requirements':[{'id':'a','quote':quotes[0]+' extra','status':'pass','evidence':''}]+[{'id':str(i),'quote':q,'status':'pass','evidence':''} for i,q in enumerate(quotes[1:])]}}]}
   g=Path(d)/'gate.json';save(g,gate);artifact(run,c['attempt_id'],'gate_decision',g)
   human={'ratings':[{'rater_id':'A','requirements':rating('fail')},{'rater_id':'B','requirements':rating('fail')}],'adjudication':None}
   save(run/'reference_reviews.json',{'x1':{'attempts':[r['attempt_id'] for r in rows],'case_id':'D01','source':str(ref),'review':human,'verdict':'fail'}})
   out=agreement(run);self.assertEqual(out['pairs'],5);self.assertEqual(out['missed_failures'],1);self.assertEqual(out['human_failures'],1)
   self.assertEqual(out['confusion_verifier_to_human']['pass->fail'],1);self.assertEqual(out['raw_agreement'],.8)
if __name__=='__main__':unittest.main()
