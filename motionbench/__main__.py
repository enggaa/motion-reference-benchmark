import argparse,json,sys
from pathlib import Path
from .core import ROOT,validate,make_run,record,summarize,read,save,consensus,sha,artifact,ensure_binding,review_attempt
from .planner import plan_run,DryRunBackend,ClaudeCodeBackend
from .reference import render_group,find_blender
from .verify import verify_group
from .blind import package,import_ratings
from .video import generate_run
from .freeze import freeze_run
def main():
 p=argparse.ArgumentParser(prog='python -m motionbench');sub=p.add_subparsers(dest='command',required=True)
 sub.add_parser('validate')
 c=sub.add_parser('plan');c.add_argument('--split',choices=['development','calibration','test'],required=True);c.add_argument('--out',required=True);c.add_argument('--repeats',type=int,default=3);c.add_argument('--seed',type=int,default=20261029)
 c=sub.add_parser('record');c.add_argument('--run',required=True);c.add_argument('--attempt',required=True);c.add_argument('--status',choices=['succeeded','failed','blocked'],required=True);c.add_argument('--stage');c.add_argument('--output')
 c=sub.add_parser('review');c.add_argument('--run',required=True);c.add_argument('--attempt',required=True);c.add_argument('--file',required=True)
 c=sub.add_parser('summarize');c.add_argument('--run',required=True);c.add_argument('--out');c.add_argument('--bootstrap',type=int,default=2000)
 c=sub.add_parser('review-template');c.add_argument('--case',required=True);c.add_argument('--out',required=True)
 c=sub.add_parser('artifact');c.add_argument('--run',required=True);c.add_argument('--attempt',required=True);c.add_argument('--kind',required=True);c.add_argument('--file',required=True)
 c=sub.add_parser('planner');c.add_argument('--run',required=True);c.add_argument('--backend',choices=['dry-run','claude-code'],default='dry-run');c.add_argument('--model',default='sonnet');c.add_argument('--max-calls',type=int,default=8);c.add_argument('--group');c.add_argument('--pose-fit',action='store_true')
 c=sub.add_parser('render-reference');c.add_argument('--run',required=True);c.add_argument('--group',required=True);c.add_argument('--blender');c.add_argument('--fps',type=int,default=24);c.add_argument('--register',action='store_true')
 c=sub.add_parser('verify-reference');c.add_argument('--run',required=True);c.add_argument('--group',required=True);c.add_argument('--model',default='sonnet')
 c=sub.add_parser('package-review');c.add_argument('--run',required=True);c.add_argument('--out',required=True);c.add_argument('--mapping',required=True);c.add_argument('--kind',choices=['final','reference'],default='final');c.add_argument('--seed',type=int)
 c=sub.add_parser('import-ratings');c.add_argument('--run',required=True);c.add_argument('--mapping',required=True);c.add_argument('--rater',action='append',required=True);c.add_argument('--adjudication')
 c=sub.add_parser('generate');c.add_argument('--run',required=True);c.add_argument('--resolution',choices=['480p','720p'],default='480p');c.add_argument('--execute',action='store_true');c.add_argument('--max-usd',type=float);c.add_argument('--attempt',action='append')
 c=sub.add_parser('freeze-pipeline');c.add_argument('--run',required=True);c.add_argument('--planner-model',required=True);c.add_argument('--planner-variant',choices=['single-call-v1','posefit-v1'],required=True);c.add_argument('--video-resolution',choices=['480p','720p'],required=True);c.add_argument('--max-usd',type=float,required=True)
 a=p.parse_args()
 if a.command=='validate':result=validate()
 elif a.command=='plan':result=make_run(a.out,a.split,a.repeats,a.seed)
 elif a.command=='record':result=record(a.run,a.attempt,a.status,a.stage,a.output)
 elif a.command=='planner':result=plan_run(a.run,DryRunBackend() if a.backend=='dry-run' else ClaudeCodeBackend(a.model),a.max_calls,a.group,find_blender() if a.pose_fit and a.backend!='dry-run' else None)
 elif a.command=='render-reference':result=render_group(a.run,a.group,a.blender,a.fps,a.register)
 elif a.command=='verify-reference':result=verify_group(a.run,a.group,ClaudeCodeBackend(a.model))
 elif a.command=='package-review':result=package(a.run,a.out,a.mapping,a.kind,a.seed)
 elif a.command=='import-ratings':result=import_ratings(a.run,a.mapping,a.rater,a.adjudication)
 elif a.command=='generate':result=generate_run(a.run,resolution=a.resolution,execute=a.execute,max_usd=a.max_usd,attempts=a.attempt)
 elif a.command=='freeze-pipeline':result=freeze_run(a.run,a.planner_model,a.planner_variant,a.video_resolution,a.max_usd)
 elif a.command=='artifact':result=artifact(a.run,a.attempt,a.kind,a.file)
 elif a.command=='summarize':
  result=summarize(a.run,draws=a.bootstrap)
  if a.out:save(a.out,result)
 elif a.command=='review-template':
  contract=next(c for c in read(ROOT/'benchmark/evaluator/contracts.json') if c['case_id']==a.case)
  keys=[r['id'] for r in contract['requirements']+contract['shared_requirements']]
  result={'ratings':[{'rater_id':None,'requirements':dict.fromkeys(keys),'notes':None} for _ in range(2)],'adjudication':None};save(a.out,result)
 elif a.command=='review':result=review_attempt(a.run,a.attempt,read(a.file))
 print(json.dumps(result,indent=2,ensure_ascii=False))
 return 1 if a.command=='validate' and not result['valid'] else 0
if __name__=='__main__':
 try:sys.exit(main())
 except (ValueError,RuntimeError,KeyError,StopIteration,FileNotFoundError,FileExistsError) as e:print('ERROR:',str(e),file=sys.stderr);sys.exit(2)
