import json,shutil,subprocess,tempfile,unittest
from pathlib import Path
from motionbench.core import make_run,read,record,artifact
from motionbench.blind import package,import_ratings
def tiny_mp4(path,colour):
 subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i',f'color=c={colour}:s=64x64:d=0.2','-metadata','encoder=provider-x','-c:v','libx264','-pix_fmt','yuv420p',str(path)],check=True)
@unittest.skipUnless(shutil.which('ffmpeg'),'ffmpeg required')
class BlindTests(unittest.TestCase):
 def setup_final(self,d):
  run=Path(d)/'r';make_run(run,'development',1);rows=[r for r in read(run/'ledger.json') if r['case_id']=='D01']
  for i,row in enumerate(rows):
   v=Path(d)/f'v{i}.mp4';tiny_mp4(v,['red','green','blue'][i]);record(run,row['attempt_id'],'succeeded',output=v)
  return run,rows
 def test_package_hides_conditions_and_paths(self):
  with tempfile.TemporaryDirectory() as d:
   run,rows=self.setup_final(d);result=package(run,Path(d)/'pkg',Path(d)/'private/mapping.json','final',seed=1)
   self.assertEqual(result['items'],3);text=''.join(p.read_text(encoding='utf-8') for p in (Path(d)/'pkg').glob('*.json'))+(Path(d)/'pkg/README.txt').read_text(encoding='utf-8')
   for word in ('direct_i2v','llm_reference','verified','attempt',str(run)):self.assertNotIn(word,text)
   self.assertNotIn(b'provider-x',next((Path(d)/'pkg/videos').glob('*.mp4')).read_bytes())
   mapping=read(Path(d)/'private/mapping.json');self.assertEqual(sorted(a for m in mapping['items'].values() for a in m['attempts']),sorted(r['attempt_id'] for r in rows))
 def test_mapping_must_live_outside_package(self):
  with tempfile.TemporaryDirectory() as d:
   run,_=self.setup_final(d)
   with self.assertRaises(ValueError):package(run,Path(d)/'pkg',Path(d)/'pkg/mapping.json')
 def test_import_two_raters_into_ledger(self):
  with tempfile.TemporaryDirectory() as d:
   run,rows=self.setup_final(d);package(run,Path(d)/'pkg',Path(d)/'mapping.json',seed=2);template=read(Path(d)/'pkg/ratings_template.json');files=[]
   for name in ('A','B'):
    sheet=json.loads(json.dumps(template));sheet['rater_id']=name
    for item in sheet['items'].values():
     item['requirements']={k:'pass' for k in item['requirements']};item['secondary']={'naturalness':4,'appearance_preserved':'pass','start_continuity':'pass','no_temporal_artifacts':'uncertain'}
    f=Path(d)/f'{name}.json';f.write_text(json.dumps(sheet),encoding='utf-8');files.append(f)
   result=import_ratings(run,Path(d)/'mapping.json',files);self.assertEqual(set(result['verdicts'].values()),{'pass'})
   self.assertTrue(all(r['review'] for r in read(run/'ledger.json') if r['case_id']=='D01'))
 def test_bad_secondary_value_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   run,_=self.setup_final(d);package(run,Path(d)/'pkg',Path(d)/'mapping.json',seed=3);template=read(Path(d)/'pkg/ratings_template.json');files=[]
   for name in ('A','B'):
    sheet=json.loads(json.dumps(template));sheet['rater_id']=name
    for item in sheet['items'].values():item['requirements']={k:'pass' for k in item['requirements']};item['secondary']={'naturalness':7}
    f=Path(d)/f'{name}.json';f.write_text(json.dumps(sheet),encoding='utf-8');files.append(f)
   with self.assertRaises(ValueError):import_ratings(run,Path(d)/'mapping.json',files)
 def test_reference_package_dedups_shared_initial(self):
  with tempfile.TemporaryDirectory() as d:
   run=Path(d)/'r';make_run(run,'development',1);refs=[r for r in read(run/'ledger.json') if r['case_id']=='D01' and r['arm']!='direct_i2v']
   v=Path(d)/'ref.mp4';tiny_mp4(v,'white')
   for r in refs:artifact(run,r['attempt_id'],'reference_initial',v)
   package(run,Path(d)/'pkg',Path(d)/'mapping.json','reference',seed=4);mapping=read(Path(d)/'mapping.json')
   self.assertEqual(len(mapping['items']),1);self.assertEqual(len(next(iter(mapping['items'].values()))['attempts']),2)
if __name__=='__main__':unittest.main()
