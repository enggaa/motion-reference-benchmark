"""Condition C gate: review the rendered reference, repair the plan at most once, review again (docs/PROTOCOL.md).
The reviewer sees the input image, the request, frames of the actual rendered reference and the renderer's automatic signals. It never sees
benchmark/evaluator, and it judges the rendered output rather than the plan. B keeps the initial reference whatever C decides."""
import datetime,json
from pathlib import Path
from .core import ROOT,read,save,sha,artifact,record,ensure_binding
from .planner import SYSTEM_PROMPT,PLAN_SCHEMA,build_request,check_plan,_call,_joints
from . import reference
_S={'type':'string'}
VERDICT_SCHEMA={'type':'object','additionalProperties':False,'required':['requirements','first_frame','verdict','repair_instructions'],'properties':{
 'requirements':{'type':'array','items':{'type':'object','additionalProperties':False,'required':['id','quote','status','evidence'],'properties':{'id':_S,'quote':_S,'status':{'type':'string','enum':['pass','fail','uncertain']},'evidence':_S}}},
 'first_frame':{'type':'object','additionalProperties':False,'required':['matches_input','notes'],'properties':{'matches_input':{'type':'boolean'},'notes':_S}},
 'verdict':{'type':'string','enum':['pass','repair']},'repair_instructions':{'type':'array','items':_S}}}
VERIFY_PROMPT="""You review a reference motion video before it is given to a video model, which will copy its motion onto the input image.
Image 1 is the input. Image 2 shows eight frames of the reference from the input camera, row by row, at the listed times. Image 3 shows the same eight frames from a front camera, where the character's right side is on the image left.
1. Split the request into its explicit requirements and copy each quote verbatim from the request.
2. Judge each requirement from the frames only: pass, fail or uncertain, with the frames that show it as evidence. A requirement passes only when you can see it. Count repetitions, check left and right from the character's point of view, check that held states are held and that the final state is visible before the end.
3. Judge whether frame 0 matches the input image: posture, lean direction, arm and leg placement.
4. verdict is "pass" only when every requirement passes and frame 0 matches. Otherwise it is "repair", with concrete instructions for the motion planner: which body part, which direction from the character's point of view, and when."""
def _images(folder):return [Path(folder)/'grid_input.png',Path(folder)/'grid_front.png']
def review(backend,image,request_text,duration_s,folder):
 telemetry=read(Path(folder)/'telemetry.json')
 text=(f"Request (verbatim): {request_text}\nDuration: {duration_s} s\nGrid times (s): {telemetry['grid_times_s']}\n"
  f"Automatic first-frame match with the input (silhouette and skin overlap, 1 = identical): {telemetry['first_frame_match']}\n"
  f"Targets the renderer could not reach: {json.dumps(telemetry['unreachable_targets'])}\nReturn your review.")
 response,tries=_call(backend,{'images':[image]+_images(folder),'text':text,'system_prompt':VERIFY_PROMPT,'schema':VERDICT_SCHEMA})
 verdict=response.get('plan')
 ok=isinstance(verdict,dict) and verdict.get('verdict') in ('pass','repair')
 return (verdict if ok else None),[{k:v for k,v in t.items() if k not in ('stdout','plan')} for t in tries]
def verify_group(run,group,backend,blender=None,root=ROOT):
 ensure_binding(run,root);run=Path(run).resolve();meta=read(run/'run.json');rows={r['attempt_id']:r for r in read(run/'ledger.json')}
 packets=[p for p in read(run/'generator_inputs.json') if p['paired_reference_group']==group]
 if not packets:raise ValueError('Unknown reference group '+group)
 packet=packets[0];c=next(p['attempt_id'] for p in packets if p['arm']=='verified_reference_r2v')
 if 'gate_decision' in rows[c]['outputs'] or rows[c]['status']!='pending':return {'group':group,'skipped':'already reviewed or terminal'}
 folder=run/'references'/group;plan_path=run/'plans'/group/'plan.json'
 if not (folder/'reference.mp4').is_file():raise ValueError('Render the initial reference first')
 for p in packets:
  if 'reference_initial' not in rows[p['attempt_id']]['outputs']:artifact(run,p['attempt_id'],'reference_initial',folder/'reference.mp4')
 log={'group':group,'attempt':c,'backend':backend.name,'model':backend.model,'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'steps':[]}
 first,tries=review(backend,packet['image'],packet['request'],packet['duration_s'],folder);log['steps'].append({'step':'review_initial','verdict':first,'tries':tries})
 decision='blocked';reference_used=None
 if first and first['verdict']=='pass':decision,reference_used='pass','initial'
 elif first:
  plan=read(plan_path);request=build_request(packet,root)
  request['text']+=('\nPrevious plan:\n'+json.dumps(plan,ensure_ascii=False)+'\nReviewer findings on the rendered reference:\n'+json.dumps(first,ensure_ascii=False)
   +'\nReturn a corrected full plan. Keep what passed and fix what the reviewer found.')
  response,t=_call(backend,request);repaired=response.get('plan');step={'step':'repair','tries':[{k:v for k,v in x.items() if k not in ('stdout','plan')} for x in t]}
  if isinstance(repaired,dict) and meta['configuration'].get('planner_variant')=='posefit-v1' and repaired.get('keyframes'):
   # The fitted initial pose stays authoritative in the pose-fit variant; a repair changes the motion, not the measured start.
   repaired['initial_pose']=plan['initial_pose'];repaired['keyframes'][0]['joints']=plan['initial_pose']['joints']
  check=check_plan(repaired,packet,request['dictionary']) if isinstance(repaired,dict) else {'errors':['no plan returned'],'warnings':[]};step['check']=check;log['steps'].append(step)
  if not check['errors']:
   rfolder=folder/'repaired';rfolder.mkdir(exist_ok=True);save(rfolder/'plan.json',repaired)
   telemetry=reference.render_plan(repaired,packet['duration_s'],packet['image'],rfolder,blender,root=root);telemetry.update(group=group,plan_sha256=sha(rfolder/'plan.json'));save(rfolder/'telemetry.json',telemetry)
   artifact(run,c,'reference_repaired',rfolder/'reference.mp4')
   second,tries=review(backend,packet['image'],packet['request'],packet['duration_s'],rfolder);log['steps'].append({'step':'review_repaired','verdict':second,'tries':tries})
   if second and second['verdict']=='pass':decision,reference_used='pass','repaired'
 log.update(decision=decision,reference_for_final=reference_used,note='Gate result only; final-video human review is separate and may still fail.')
 save(folder/'gate_decision.json',log);artifact(run,c,'gate_decision',folder/'gate_decision.json')
 if decision=='blocked':record(run,c,'blocked','reference_review',root=root)
 return {'group':group,'decision':decision,'reference_for_final':reference_used,'steps':[s['step'] for s in log['steps']],
  'initial_failures':[r['quote'] for r in (first or {}).get('requirements',[]) if r['status']!='pass']}
