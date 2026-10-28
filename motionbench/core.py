import hashlib,json,random,datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ARMS=('direct_i2v','llm_reference_r2v','verified_reference_r2v')
TERMINAL=('succeeded','failed','blocked')
def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def save(path,obj):Path(path).write_text(json.dumps(obj,indent=2,ensure_ascii=False,allow_nan=False),encoding='utf-8')
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def ensure_binding(run,root=ROOT):
 meta=read(Path(run)/'run.json');root=Path(root)
 for field,file in [('cases_sha256','cases.json'),('contracts_sha256','evaluator/contracts.json'),('dictionary_sha256','seed_dictionary.json')]:
  if meta[field]!=sha(root/'benchmark'/file):raise ValueError('Benchmark changed after run planning: '+field)
def validate(root=ROOT):
 root=Path(root);cases=read(root/'benchmark/cases.json');contracts=read(root/'benchmark/evaluator/contracts.json');errors=[];seen=set();images=set()
 byid={c['case_id']:c for c in contracts};groups={};families={};cells=set()
 for c in cases:
  if c['id'] in seen:errors.append('duplicate case '+c['id'])
  seen.add(c['id']);path=(root/'benchmark'/c['image']).resolve()
  if not path.is_relative_to((root/'benchmark/images').resolve()):errors.append('image outside asset directory');continue
  if not path.is_file() or sha(path)!=c['image_sha256']:errors.append('image missing/hash mismatch '+c['id'])
  if c['image_sha256'] in images:errors.append('duplicate image bytes '+c['id'])
  images.add(c['image_sha256'])
  groups.setdefault(c['variant_group'],set()).add(c['split'])
  if c['dictionary_relationship']=='unseen':families.setdefault(c['action_family'],set()).add(c['split'])
  if c['split']=='test':cells.add((c['dictionary_relationship'],c['initial_pose']))
  if c['id'] not in byid:errors.append('missing contract '+c['id']);continue
  reqs=byid[c['id']]['requirements']
  if len({r['id'] for r in reqs})!=len(reqs):errors.append('duplicate requirement id '+c['id'])
  for r in reqs:
   if r['quote'] not in c['request']:errors.append('unbound requirement '+c['id'])
 if any(len(s)>1 for s in groups.values()):errors.append('variant group crosses split')
 if any('test' in s and len(s)>1 for s in families.values()):errors.append('unseen test family leaked into development/calibration')
 if len(cells)!=12:errors.append('test coverage is not 3 novelty x 4 poses')
 freeze=root/'benchmark/freeze.json'
 if freeze.exists():
  for name,expected in read(freeze)['files'].items():
   path=(root/name).resolve()
   if not path.is_relative_to(root.resolve()) or not path.is_file() or sha(path)!=expected:errors.append('frozen asset changed: '+name)
 return {'valid':not errors,'errors':errors,'cases':len(cases),'test_cells':len(cells),'split_counts':{s:sum(c['split']==s for c in cases) for s in ['development','calibration','test']}}
def make_run(out,split,repeats=3,seed=20261029,root=ROOT):
 root=Path(root);validation=validate(root)
 if not validation['valid']:raise ValueError(validation['errors'])
 if split not in ('development','calibration','test'):raise ValueError('Unknown split')
 if not 1<=repeats<=10:raise ValueError('Repeats must be 1..10')
 out=Path(out);out.mkdir(parents=True,exist_ok=False);rng=random.Random(seed);rows=[];inputs=[]
 for case in read(root/'benchmark/cases.json'):
  if case['split']!=split:continue
  for replicate in range(1,repeats+1):
   arms=list(ARMS);rng.shuffle(arms)
   initial_ref_group=f"{case['id']}-{replicate:02d}"
   for arm in arms:
    aid=f'{len(rows)+1:04d}';row={'attempt_id':aid,'case_id':case['id'],'arm':arm,'replicate':replicate,'paired_reference_group':initial_ref_group if arm!='direct_i2v' else None,'status':'pending','failure_stage':None,'outputs':{},'model_ids':{},'cost':None,'latency_s':None,'review':None}
    rows.append(row)
    # Generator packet intentionally excludes evaluator contracts, ground-truth pose and expected answers.
    inputs.append({'attempt_id':aid,'case_id':case['id'],'request':case['request'],'image':str((root/'benchmark'/case['image']).resolve()),'image_sha256':case['image_sha256'],'duration_s':case['duration_s'],'arm':arm,'dictionary_version':'seed-v0.1','paired_reference_group':row['paired_reference_group']})
 save(out/'ledger.json',rows);save(out/'generator_inputs.json',inputs)
 save(out/'run.json',{'version':'0.1.0','split':split,'repeats':repeats,'seed':seed,'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'cases_sha256':sha(root/'benchmark/cases.json'),'contracts_sha256':sha(root/'benchmark/evaluator/contracts.json'),'dictionary_sha256':sha(root/'benchmark/seed_dictionary.json'),'configuration':{'planner_model':None,'video_model':None,'numeric_cost_cap':None,'conditioning_modes_confirmed':False},'execution_enabled':False,'note':'Planning does not execute models. Reference arms share one initial LLM candidate per replicate; only verified arm may inspect/repair it.'})
 return {'attempts':len(rows),'out':str(out)}
def record(run,attempt,status,stage=None,output=None,root=ROOT):
 ensure_binding(run,root)
 run=Path(run);rows=read(run/'ledger.json');row=next((r for r in rows if r['attempt_id']==attempt),None)
 if row is None:raise ValueError('Unknown attempt')
 if status not in TERMINAL:raise ValueError('Only terminal status accepted')
 if row['status'] in TERMINAL:raise ValueError('Terminal attempt is immutable; record a new run rather than overwrite')
 if status=='succeeded' and not output:raise ValueError('Successful final attempt requires a real output file')
 if status!='succeeded' and stage not in ('initial_pose','contract','planning','retargeting','reference_review','final_generation','transport'):raise ValueError('Failure stage required')
 if output:
  path=Path(output).resolve()
  if not path.is_file():raise ValueError('Output file does not exist')
  if path.suffix.lower()!='.mp4' or b'ftyp' not in path.read_bytes()[:32]:raise ValueError('Expected MP4 container; full media/semantic review still required')
  row['outputs']['final']={'path':str(path),'sha256':sha(path)}
 row.update(status=status,failure_stage=stage if status!='succeeded' else None);save(run/'ledger.json',rows);return row
def consensus(review,required):
 if not review:return 'unreviewed'
 ratings=review.get('ratings',[])
 if len(ratings)!=2 or len({r.get('rater_id') for r in ratings})!=2 or any(not r.get('rater_id') for r in ratings):raise ValueError('Two distinct raters required')
 outcomes=[]
 for rating in ratings:
  checks=rating.get('requirements',{})
  if set(checks)!=set(required) or any(v not in ('pass','fail','uncertain') for v in checks.values()):raise ValueError('Every requirement must be rated')
  outcomes.append(checks)
 if outcomes[0]!=outcomes[1]:
  adjudication=review.get('adjudication')
  if not adjudication:return 'disputed'
  if adjudication.get('rater_id') in [r['rater_id'] for r in ratings] or not adjudication.get('rater_id'):raise ValueError('Independent adjudicator required')
  checks=adjudication.get('requirements',{})
  if set(checks)!=set(required) or any(v not in ('pass','fail','uncertain') for v in checks.values()):raise ValueError('Incomplete adjudication')
 else:checks=outcomes[0]
 return 'fail' if 'fail' in checks.values() else 'uncertain' if 'uncertain' in checks.values() else 'pass'
def required_ids(case_id,root=ROOT):
 contract=next(c for c in read(Path(root)/'benchmark/evaluator/contracts.json') if c['case_id']==case_id);return [r['id'] for r in contract['requirements']+contract['shared_requirements']]
def review_attempt(run,attempt,review,root=ROOT):
 ensure_binding(run,root)
 ledger=Path(run)/'ledger.json';rows=read(ledger);row=next(r for r in rows if r['attempt_id']==attempt)
 if row['status']!='succeeded':raise ValueError('Only succeeded outputs receive perceptual review')
 if row.get('review'):raise ValueError('Review already recorded; do not overwrite')
 if sha(row['outputs']['final']['path'])!=row['outputs']['final']['sha256']:raise ValueError('Output changed after registration')
 verdict=consensus(review,required_ids(row['case_id'],root));row['review']=review;save(ledger,rows);return {'attempt_id':attempt,'verdict':verdict}
def artifact(run,attempt,kind,path):
 ensure_binding(run)
 if kind not in ('plan','reference_initial','reference_repaired','gate_decision','execution_log'):raise ValueError('Unsupported artifact kind')
 run=Path(run);rows=read(run/'ledger.json');row=next(r for r in rows if r['attempt_id']==attempt);path=Path(path).resolve()
 if not path.is_file():raise ValueError('Artifact missing')
 if kind in row['outputs']:raise ValueError('Artifact already registered')
 if kind.startswith('reference'):
  if row['arm']=='direct_i2v':raise ValueError('Direct I2V cannot receive a reference')
  if kind=='reference_repaired' and row['arm']!='verified_reference_r2v':raise ValueError('Only verified arm may repair')
  if path.suffix.lower()!='.mp4' or b'ftyp' not in path.read_bytes()[:32]:raise ValueError('Reference must be MP4')
 if kind=='reference_initial':
  peers=[r for r in rows if r['paired_reference_group']==row['paired_reference_group'] and kind in r['outputs']]
  if any(r['outputs'][kind]['sha256']!=sha(path) for r in peers):raise ValueError('Paired reference arms must start with identical candidate bytes')
 row['outputs'][kind]={'path':str(path),'sha256':sha(path)};save(run/'ledger.json',rows);return row['outputs'][kind]
def summarize(run,root=ROOT):
 ensure_binding(run,root)
 rows=read(Path(run)/'ledger.json');contracts={x['case_id']:x for x in read(Path(root)/'benchmark/evaluator/contracts.json')};byarm={}
 for arm in ARMS:
  selected=[r for r in rows if r['arm']==arm];counts={k:0 for k in ['pending','failed','blocked','unreviewed','disputed','uncertain','pass','fail']};cases={}
  for row in selected:
   for item in row['outputs'].values():
    if not Path(item['path']).is_file() or sha(item['path'])!=item['sha256']:raise ValueError('Registered artifact changed or missing')
   contract=contracts[row['case_id']];required=[x['id'] for x in contract['requirements']+contract['shared_requirements']]
   outcome=consensus(row.get('review'),required) if row['status']=='succeeded' else row['status'];counts[outcome]+=1;cases.setdefault(row['case_id'],[]).append(outcome)
  complete=not any(counts[k] for k in ['pending','unreviewed','disputed'])
  fractions={c:sum(v=='pass' for v in outcomes)/len(outcomes) for c,outcomes in cases.items()}
  byarm[arm]={'assigned':len(selected),'counts':counts,'complete':complete,'primary_case_mean':sum(fractions.values())/len(fractions) if complete and fractions else None,'case_pass_fractions':fractions if complete else None}
 deltas={}
 if all(v['complete'] for v in byarm.values()):
  for arm in ARMS[1:]:
   a=byarm[arm]['case_pass_fractions'] or {};b=byarm[ARMS[0]]['case_pass_fractions'] or {};shared=set(a)&set(b)
   deltas[arm+'_minus_direct']=sum(a[c]-b[c] for c in shared)/len(shared) if shared else None
 return {'arms':byarm,'paired_case_mean_differences':deltas,'interpretation':'No performance score until assigned attempts are terminal and reviews resolved. Failed/blocked/uncertain attempts count as zero, not dropped. No inferential CI or superiority test implemented in v0.1.'}
