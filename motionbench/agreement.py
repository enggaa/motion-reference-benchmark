"""Verifier vs. human agreement on references (calibration of the condition C gate). Evaluation side only: reads evaluator contracts and
human reference ratings (reference_reviews.json from import-ratings --kind reference) and compares them with the gate's recorded verdicts.
The verifier splits the request itself, so each contract requirement is matched to the verifier requirement whose quote contains its quote."""
from pathlib import Path
from .core import ROOT,read
LABELS=('pass','fail','uncertain')
def _match(contract_quote,verifier_requirements):
 hits=[r for r in verifier_requirements if contract_quote in r.get('quote','') or r.get('quote','') in contract_quote]
 return min(hits,key=lambda r:len(r['quote']))['status'] if hits else None
def _human(review):
 """Consensus per requirement: agreed value, or the adjudicator's when the two raters differ, else None (disputed)."""
 a,b=[r['requirements'] for r in review['ratings']];adj=(review.get('adjudication') or {}).get('requirements') or {}
 return {k:(a[k] if a[k]==b.get(k) else adj.get(k)) for k in a}
def kappa(pairs):
 n=len(pairs)
 if not n:return None
 po=sum(x==y for x,y in pairs)/n;pe=sum((sum(x==l for x,_ in pairs)/n)*(sum(y==l for _,y in pairs)/n) for l in LABELS)
 return round((po-pe)/(1-pe),3) if pe<1 else None
def agreement(run,root=ROOT):
 run=Path(run);contracts={c['case_id']:c for c in read(Path(root)/'benchmark/evaluator/contracts.json')};rows={r['attempt_id']:r for r in read(run/'ledger.json')}
 items=read(run/'reference_reviews.json');pairs=[];detail=[];unmatched=0
 for item in items.values():
  if 'review' not in item:continue
  human=_human(item['review']);attempt=rows[item['attempts'][0]]
  # The item is one reference file; find the gate review that judged those exact bytes.
  gate_path=next((rows[a]['outputs']['gate_decision']['path'] for a in item['attempts'] if 'gate_decision' in rows[a]['outputs']),None)
  if not gate_path:continue
  gate=read(gate_path);kind='review_repaired' if item['source'].replace('\\','/').endswith('repaired/reference.mp4') else 'review_initial'
  verdict=next((s['verdict'] for s in gate['steps'] if s['step']==kind and s.get('verdict')),None)
  if not verdict:continue
  for req in contracts[attempt['case_id']]['requirements']:
   machine=_match(req['quote'],verdict['requirements']);h=human.get(req['id'])
   if machine is None:unmatched+=1
   if machine is None or h is None:continue
   pairs.append((machine,h));detail.append({'case_id':attempt['case_id'],'reference':kind,'requirement':req['id'],'quote':req['quote'],'verifier':machine,'human':h})
 confusion={f'{m}->{h}':sum(1 for x,y in pairs if (x,y)==(m,h)) for m in LABELS for h in LABELS}
 # The gate's job is to stop references people would fail: how often a human fail got a verifier pass is the costly miss.
 human_fail=[p for p in pairs if p[1]=='fail']
 return {'pairs':len(pairs),'unmatched_requirements':unmatched,'raw_agreement':round(sum(x==y for x,y in pairs)/len(pairs),3) if pairs else None,'cohen_kappa':kappa(pairs),
  'missed_failures':sum(1 for x,_ in human_fail if x=='pass'),'human_failures':len(human_fail),'confusion_verifier_to_human':confusion,'detail':detail,
  'note':'Contract requirements only (shared S1/S2 have no quote). Small samples: report counts, not just kappa.'}
