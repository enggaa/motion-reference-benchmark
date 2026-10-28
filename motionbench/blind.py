"""Blinded review packages (docs/ADAPTER_CONTRACT.md, docs/RUBRIC.md). Raters get random item ids, the input image, the request, the scoring
criteria and a metadata-stripped video copy; condition names, plans, gate results and source paths stay in a mapping file kept apart.
kind='final' packages succeeded final videos; kind='reference' packages each distinct reference (B/C share one initial reference, C may add a repair)."""
import random,shutil,subprocess
from pathlib import Path
from .core import ROOT,read,save,sha,ensure_binding,consensus,required_ids,review_attempt
SECONDARY={'naturalness':'1-5 (RUBRIC: 1 large abnormal bends or jumps, 3 recognisable but awkward, 5 nothing unnatural)','appearance_preserved':'pass/fail/uncertain','start_continuity':'pass/fail/uncertain','no_temporal_artifacts':'pass/fail/uncertain'}
README="""평가 안내 (조건 비공개)

각 항목은 입력 이미지, 원문 요청, 영상 1개입니다. 영상이 어떤 방법으로 만들어졌는지는 알려 주지 않습니다.
items.json의 각 요구(requirements)를 pass / fail / uncertain으로 판정하세요. 가림이나 구도 때문에 판단할 수 없으면 uncertain이며, 잘 됐을 것이라고 추정하지 않습니다.
부 결과(secondary)는 요구 판정과 별개로 기록합니다. naturalness는 1-5 정수, 나머지는 pass / fail / uncertain입니다.
ratings_template.json을 복사해 rater_id에 본인 식별자를 적고 채운 뒤 제출하세요. 다른 평가자와 상의하지 마세요.
판정 기준: docs/RUBRIC.md 와 같은 앵커를 사용합니다.
"""
def _strip_copy(src,dst):
 # Re-mux without container metadata (encoder tags can reveal the provider); the video stream itself is unchanged.
 subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(src),'-map','0:v','-map_metadata','-1','-c','copy','-fflags','+bitexact',str(dst)],check=True)
def _items(run,kind):
 rows=read(Path(run)/'ledger.json')
 if kind=='final':return [(r['case_id'],Path(r['outputs']['final']['path']),[r['attempt_id']],r['outputs']['final']['sha256']) for r in rows if r['status']=='succeeded' and 'final' in r['outputs']]
 if kind!='reference':raise ValueError('kind must be final or reference')
 seen={};out=[]
 for r in rows:
  for k in ('reference_initial','reference_repaired'):
   if k in r['outputs']:
    h=r['outputs'][k]['sha256']
    if h in seen:seen[h][2].append(r['attempt_id'])
    else:seen[h]=(r['case_id'],Path(r['outputs'][k]['path']),[r['attempt_id']],h);out.append(seen[h])
 return out
def package(run,out,mapping_out,kind='final',seed=None,root=ROOT):
 ensure_binding(run,root);out=Path(out).resolve();mapping_out=Path(mapping_out).resolve()
 if mapping_out.is_relative_to(out):raise ValueError('The mapping must be stored outside the rater package')
 if out.exists():raise ValueError('Package directory already exists')
 items=_items(run,kind)
 if not items:raise ValueError('Nothing to package for kind '+kind)
 cases={c['id']:c for c in read(Path(root)/'benchmark/cases.json')};contracts={c['case_id']:c for c in read(Path(root)/'benchmark/evaluator/contracts.json')}
 rng=random.Random(seed);rng.shuffle(items);(out/'videos').mkdir(parents=True);(out/'inputs').mkdir();listing=[];template={};mapping={}
 for case_id,src,attempts,digest in items:
  if sha(src)!=digest:raise ValueError('Registered video changed: '+str(src))
  item=f'{rng.getrandbits(40):010x}';_strip_copy(src,out/'videos'/f'{item}.mp4')
  image=out/'inputs'/f'{case_id}.png'
  if not image.exists():shutil.copy(Path(root)/'benchmark'/cases[case_id]['image'],image)
  c=contracts[case_id];reqs=[{'id':r['id'],'criterion':r['criterion']} for r in c['requirements']+c['shared_requirements']]
  listing.append({'item_id':item,'case_id':case_id,'request':cases[case_id]['request'],'input_image':f'inputs/{case_id}.png','video':f'videos/{item}.mp4','requirements':reqs,'ambiguity_policy':c['ambiguity_policy'],'completion_policy':c['completion_policy']})
  template[item]={'requirements':dict.fromkeys(r['id'] for r in reqs),'secondary':dict.fromkeys(SECONDARY),'notes':None}
  mapping[item]={'attempts':attempts,'case_id':case_id,'source':str(src),'sha256':digest,'packaged_sha256':sha(out/'videos'/f'{item}.mp4')}
 listing.sort(key=lambda x:x['item_id'])
 save(out/'items.json',{'kind':kind,'secondary_scales':SECONDARY,'items':listing});save(out/'ratings_template.json',{'rater_id':None,'items':template});(out/'README.txt').write_text(README,encoding='utf-8')
 mapping_out.parent.mkdir(parents=True,exist_ok=True);save(mapping_out,{'kind':kind,'run':str(Path(run).resolve()),'seed':seed,'items':mapping,'note':'Keep away from raters until all ratings are in.'})
 return {'kind':kind,'items':len(listing),'package':str(out),'mapping':str(mapping_out)}
def _check_secondary(values):
 for k,v in (values or {}).items():
  if k not in SECONDARY:raise ValueError('Unknown secondary field '+k)
  if v is None:continue
  if k=='naturalness' and v not in (1,2,3,4,5):raise ValueError('naturalness must be 1-5')
  if k!='naturalness' and v not in ('pass','fail','uncertain'):raise ValueError(k+' must be pass/fail/uncertain')
def import_ratings(run,mapping,raters,adjudication=None,root=ROOT):
 """raters: two filled ratings files from different people. Final videos go into the ledger through review_attempt; reference ratings go to reference_reviews.json."""
 mapping=read(mapping);sheets=[read(r) for r in raters];adj=read(adjudication) if adjudication else None
 if len(sheets)!=2:raise ValueError('Exactly two rater files are required')
 results={}
 for item,info in mapping['items'].items():
  ratings=[]
  for sheet in sheets:
   entry=sheet['items'].get(item)
   if entry is None:raise ValueError(f'Rater {sheet.get("rater_id")} did not rate {item}')
   _check_secondary(entry.get('secondary'));ratings.append({'rater_id':sheet.get('rater_id'),'requirements':entry['requirements'],'secondary':entry.get('secondary'),'notes':entry.get('notes')})
  review={'ratings':ratings,'adjudication':None}
  if adj and item in adj['items']:review['adjudication']={'rater_id':adj.get('rater_id'),'requirements':adj['items'][item]['requirements'],'notes':adj['items'][item].get('notes')}
  if mapping['kind']=='final':results[item]=review_attempt(run,info['attempts'][0],review,root)['verdict']
  else:results[item]=consensus(review,required_ids(info['case_id'],root))
  info['review']=review;info['verdict']=results[item]
 if mapping['kind']=='reference':
  path=Path(run)/'reference_reviews.json';existing=read(path) if path.exists() else {}
  if set(existing)&set(mapping['items']):raise ValueError('Reference ratings already imported for some items')
  existing.update(mapping['items']);save(path,existing)
 return {'kind':mapping['kind'],'verdicts':results}
