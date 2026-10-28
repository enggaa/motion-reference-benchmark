"""Evaluator-side check of planned initial poses against benchmark/evaluator ground truth.
Reads evaluator files, so its output must never go back into planning, retrieval, repair or finetuning. Development split only."""
import json,math,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def lean(P):return math.degrees(math.atan2(P['neck'][0]-P['pelvis'][0],P['neck'][2]-P['pelvis'][2]))
def compare(run):
 run=Path(run);meta=json.loads((run/'run.json').read_text(encoding='utf-8'))
 if meta['split']!='development':raise SystemExit('initial_pose_error is for the development split only')
 cases={c['id']:c for c in json.loads((ROOT/'benchmark/cases.json').read_text(encoding='utf-8-sig'))};rows=[]
 for d in sorted((run/'plans').iterdir()):
  if not (d/'plan.json').is_file():continue
  case=json.loads((d/'request.json').read_text(encoding='utf-8'))['case_id'];plan=json.loads((d/'plan.json').read_text(encoding='utf-8'))
  est={q['joint']:tuple(q[k] for k in 'xyz') for q in plan['initial_pose']['joints']}
  gt={k:tuple(v) for k,v in json.loads((ROOT/f'benchmark/evaluator/{case}_initial_pose.json').read_text(encoding='utf-8')).items() if k=='joints' for k,v in v.items()}
  err={j:math.dist(est[j],gt[j]) for j in gt};worst=max(err,key=err.get)
  rows.append({'case_id':case,'pose_truth':cases[case]['initial_pose'],'pose_class':plan['initial_pose']['pose_class'],'mean_joint_error_m':round(sum(err.values())/len(err),3),'worst_joint':worst,'worst_error_m':round(err[worst],3),
   'lateral_lean_deg':{'estimate':round(lean(est)),'truth':round(lean(gt))},'left_right_order_ok':all(est['R'+j][0]<est['L'+j][0] for j in ('shoulder','wrist','hip'))})
 return rows
if __name__=='__main__':print(json.dumps(compare(sys.argv[1]),indent=2,ensure_ascii=False))
