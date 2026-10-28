"""LLM planner adapter. Reads only generator_inputs.json packets and the public seed dictionary, never benchmark/evaluator."""
import base64,datetime,hashlib,json,math,os,shutil,subprocess,tempfile,time
from pathlib import Path
from .core import ROOT,read,save,sha,artifact,record,ensure_binding
JOINTS=('pelvis','neck','head')+tuple(s+p for s in 'LR' for p in ('hip','knee','ankle','shoulder','elbow','wrist'))
BONES=[('pelvis','neck'),('neck','head')]+[(a,b) for s in 'LR' for a,b in [(s+'hip',s+'knee'),(s+'knee',s+'ankle'),(s+'shoulder',s+'elbow'),(s+'elbow',s+'wrist')]]
POSE_CLASSES=('standing','seated','leaning','crouched','kneeling','lying','other')
ORIGINS=('observed','retrieved','inferred')
PACKET_KEYS={'attempt_id','case_id','request','image','image_sha256','duration_s','arm','dictionary_version','paired_reference_group'}
BONE_TOLERANCE=.15
def _obj(props):return {'type':'object','properties':props,'required':list(props),'additionalProperties':False}
_S={'type':'string'};_SS={'type':'array','items':_S};_N={'type':'number'}
_POINT=_obj({'joint':{'type':'string','enum':list(JOINTS)},'x':_N,'y':_N,'z':_N})
PLAN_SCHEMA=_obj({
 'initial_pose':_obj({'pose_class':{'type':'string','enum':list(POSE_CLASSES)},'observations':_SS,'uncertainties':_SS,'joints':{'type':'array','items':_POINT},'contacts':_SS}),
 'actions':{'type':'array','items':_obj({'id':_S,'request_quote':_S,'side':{'type':'string','enum':['left','right','both','none']},'repetitions':{'type':['integer','null']},'completion':_S})},
 'retrieval':{'type':'array','items':_obj({'entry_id':_S,'used_for':_S})},
 'keyframes':{'type':'array','items':_obj({'time_s':_N,'origin':{'type':'string','enum':list(ORIGINS)},'action_id':{'type':['string','null']},'description':_S,'joints':{'type':'array','items':_POINT},'contacts':_SS})},
 'assumptions':_SS,'unsupported_requirements':_SS})
SYSTEM_PROMPT="""You are the motion planner between an action/keyframe dictionary and a reference-video renderer.
Input: one image of a procedural mannequin (fixed camera, exact camera parameters unknown), a verbatim request (usually Korean), the clip duration and a seed dictionary that lists known action ids and semantics only (it contains no trajectories).
Rig: 15 joints pelvis, neck, head, L/R hip, knee, ankle, shoulder, elbow, wrist. L/R are the character's own left/right. Coordinates in metres: character's left +X, character's front -Y, up +Z, floor z=0. Approximate segment lengths: pelvis-neck 0.49, neck-head 0.21, upper arm 0.27, forearm 0.22, thigh 0.43, shin 0.43, shoulder half-width 0.23, hip half-width 0.12.
Rules:
1. Estimate the initial pose from the image only. Do not reset to T-pose or standing unless the image shows it. Put what you see in observations and anything ambiguous in uncertainties. Give all 15 joints and the visible contacts (feet on floor, pelvis on seat, ...).
2. Split the request into actions. request_quote must be copied verbatim from the request. Keep left/right exactly as requested, from the character's point of view. completion is an observable end condition.
3. keyframes: the first one is at time_s 0 with origin "observed" and the same joints as initial_pose. Every keyframe lists all 15 joints. Times increase and stay within [0, duration]. Hold the final state visibly before the clip ends. Preserve segment lengths and contacts the request does not ask to change.
4. origin is "retrieved" only when the keyframe follows a dictionary entry listed in retrieval, otherwise "inferred". Actions outside the dictionary are allowed: infer them and say so in assumptions.
5. List requirements you cannot satisfy in unsupported_requirements instead of silently dropping them. Do not claim certainty you do not have."""
def _guard_packet(packet,root=ROOT):
 extra=set(packet)-PACKET_KEYS
 if extra:raise ValueError('Generator packet carries non-generator fields: '+', '.join(sorted(extra)))
 image=Path(packet['image']).resolve()
 if not image.is_relative_to((Path(root)/'benchmark/images').resolve()):raise ValueError('Planner image must come from benchmark/images')
 if sha(image)!=packet['image_sha256']:raise ValueError('Image hash mismatch '+packet['case_id'])
 return image
def public_dictionary(root=ROOT):
 # Only the semantic inventory; disallowed_test_families would name held-out test actions.
 d=read(Path(root)/'benchmark/seed_dictionary.json');return {k:d[k] for k in ('version','actions','semantics','scope')}
def build_request(packet,root=ROOT):
 image=_guard_packet(packet,root);dictionary=public_dictionary(root)
 text=f"Request (verbatim): {packet['request']}\nDuration: {packet['duration_s']} s\nDictionary: {json.dumps(dictionary,ensure_ascii=False)}\nReturn the plan."
 return {'case_id':packet['case_id'],'paired_reference_group':packet['paired_reference_group'],'image':str(image),'image_sha256':packet['image_sha256'],'text':text,'system_prompt_sha256':hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest(),'schema_sha256':hashlib.sha256(json.dumps(PLAN_SCHEMA,sort_keys=True).encode()).hexdigest(),'dictionary':dictionary}
def _joints(points,where,errors):
 out={}
 for p in points or []:
  if p.get('joint') not in JOINTS or not all(isinstance(p.get(k),(int,float)) and math.isfinite(p[k]) for k in 'xyz'):errors.append(where+': invalid joint entry');continue
  if p['joint'] in out:errors.append(where+': duplicate joint '+p['joint'])
  out[p['joint']]=(p['x'],p['y'],p['z'])
 missing=[j for j in JOINTS if j not in out]
 if missing:errors.append(where+': missing joints '+', '.join(missing))
 return out
def _lengths(pose):return {(a,b):math.dist(pose[a],pose[b]) for a,b in BONES if a in pose and b in pose}
def check_plan(plan,packet,dictionary):
 """Structural/self-consistency check only; it does not show the motion is semantically right."""
 errors=[];warnings=[]
 for key in PLAN_SCHEMA['required']:
  if key not in plan:errors.append('missing '+key)
 if errors:return {'errors':errors,'warnings':warnings}
 initial=plan['initial_pose']
 if initial.get('pose_class') not in POSE_CLASSES:errors.append('initial_pose: invalid pose_class')
 base=_joints(initial.get('joints'),'initial_pose',errors);ref=_lengths(base)
 ids=set()
 for a in plan['actions']:
  ids.add(a.get('id'))
  if not a.get('request_quote') or a['request_quote'] not in packet['request']:errors.append(f"actions {a.get('id')}: request_quote not verbatim in request")
 if not plan['actions']:errors.append('actions: empty')
 for r in plan['retrieval']:
  if r.get('entry_id') not in dictionary['actions']:errors.append(f"retrieval: unknown dictionary entry {r.get('entry_id')}")
 frames=plan['keyframes'];times=[f.get('time_s') for f in frames]
 if len(frames)<2:errors.append('keyframes: need at least start and end')
 elif not all(isinstance(t,(int,float)) for t in times):errors.append('keyframes: non-numeric time')
 else:
  if times[0]!=0:errors.append('keyframes: first keyframe must be at 0 s')
  if any(b<=a for a,b in zip(times,times[1:])):errors.append('keyframes: times must increase')
  if times[-1]>packet['duration_s']:errors.append('keyframes: beyond clip duration')
 if frames and frames[0].get('origin')!='observed':errors.append('keyframes: first keyframe must be observed, not reset')
 if any(f.get('origin')=='retrieved' for f in frames) and not plan['retrieval']:errors.append('keyframes: retrieved origin without retrieval entry')
 for i,f in enumerate(frames):
  if f.get('origin') not in ORIGINS:errors.append(f'keyframe {i}: invalid origin')
  if f.get('action_id') is not None and f['action_id'] not in ids:errors.append(f'keyframe {i}: unknown action_id')
  pose=_joints(f.get('joints'),f'keyframe {i}',errors)
  if i==0 and base and pose and any(math.dist(base[j],pose[j])>1e-6 for j in JOINTS if j in base and j in pose):errors.append('keyframe 0: differs from initial_pose')
  for bone,length in _lengths(pose).items():
   if bone in ref and ref[bone]>0 and abs(length-ref[bone])/ref[bone]>BONE_TOLERANCE:warnings.append(f'keyframe {i}: {bone[0]}-{bone[1]} length {length:.3f} vs initial {ref[bone]:.3f}')
 return {'errors':errors,'warnings':warnings}
class DryRunBackend:
 """Writes the request that would be sent; calls no model."""
 name='dry-run';model=None
 def call(self,request):return None
class ClaudeCodeBackend:
 """Route A: headless Claude Code on the user's subscription. Customizations and tools are off, but Claude Code still wraps the request."""
 name='claude-code'
 def __init__(self,model='sonnet',exe=None,timeout=600):
  self.model=model;self.timeout=timeout
  self.exe=exe or os.environ.get('MOTIONBENCH_CLAUDE_EXE') or shutil.which('claude')
  if not self.exe:raise RuntimeError('claude CLI not found; install it or set MOTIONBENCH_CLAUDE_EXE')
 def command(self):
  return [self.exe,'-p','--input-format','stream-json','--output-format','stream-json','--verbose','--safe-mode','--tools','','--system-prompt',SYSTEM_PROMPT,'--json-schema',json.dumps(PLAN_SCHEMA),'--model',self.model,'--no-session-persistence']
 def env(self):
  # Drop host-session and API-key variables so the call bills the CLI's own subscription login, never an API key.
  return {k:v for k,v in os.environ.items() if not k.startswith('CLAUDE') and k not in ('ANTHROPIC_API_KEY','ANTHROPIC_AUTH_TOKEN','ANTHROPIC_BASE_URL')}
 def call(self,request):
  image=base64.b64encode(Path(request['image']).read_bytes()).decode()
  message={'type':'user','message':{'role':'user','content':[{'type':'image','source':{'type':'base64','media_type':'image/png','data':image}},{'type':'text','text':request['text']}]}}
  started=time.time()
  with tempfile.TemporaryDirectory() as cwd:
   try:p=subprocess.run(self.command(),input=json.dumps(message)+'\n',capture_output=True,text=True,encoding='utf-8',cwd=cwd,env=self.env(),timeout=self.timeout)
   except subprocess.TimeoutExpired:return {'transport_error':'timeout','latency_s':time.time()-started,'stdout':''}
  init=result=None
  for line in p.stdout.splitlines():
   try:o=json.loads(line)
   except ValueError:continue
   if o.get('type')=='system' and o.get('subtype')=='init':init=o
   if o.get('type')=='result':result=o
  out={'latency_s':time.time()-started,'returncode':p.returncode,'stdout':p.stdout,'stderr':p.stderr[-4000:],'cli_version':(init or {}).get('claude_code_version'),'model':(init or {}).get('model'),'tools':(init or {}).get('tools')}
  if result is None:out['transport_error']='no result message';return out
  out.update(usage=result.get('usage'),model_usage=result.get('modelUsage'),notional_cost_usd=result.get('total_cost_usd'),num_turns=result.get('num_turns'))
  if 'Not logged in' in str(result.get('result')):raise RuntimeError('claude CLI is not logged in; run it once and use /login with the subscription account')
  if result.get('is_error'):out['transport_error']=result.get('terminal_reason') or result.get('subtype') or 'error';out['message']=str(result.get('result'))[:2000];return out
  plan=result.get('structured_output')
  if plan is None:
   try:plan=json.loads(result.get('result') or '')
   except ValueError:plan=None
  out['plan']=plan;return out
def plan_run(run,backend,max_calls=8,group=None,allow_test=False,root=ROOT):
 ensure_binding(run,root);run=Path(run);meta=read(run/'run.json')
 if meta['split']=='test' and not allow_test:raise ValueError('Planner on test split requires a frozen pipeline; pass allow_test explicitly')
 dry=isinstance(backend,DryRunBackend)
 if not dry:
  config=meta['configuration'];wanted={'planner_backend':backend.name,'planner_model':backend.model}
  for k,v in wanted.items():
   if config.get(k) not in (None,v):raise ValueError(f'Run already uses {k}={config[k]}; plan a new run instead of mixing')
  config.update(wanted);save(run/'run.json',meta)
 packets=[p for p in read(run/'generator_inputs.json') if p['paired_reference_group']];rows={r['attempt_id']:r for r in read(run/'ledger.json')}
 groups={}
 for p in packets:groups.setdefault(p['paired_reference_group'],[]).append(p)
 done=[];calls=0
 for gid,members in groups.items():
  if group and gid!=group:continue
  attempts=[p['attempt_id'] for p in members]
  if any('plan' in rows[a]['outputs'] or rows[a]['status']!='pending' for a in attempts):continue
  if calls>=max_calls:break
  folder=run/'plans'/gid;folder.mkdir(parents=True,exist_ok=True)
  request=build_request(members[0],root);save(folder/'request.json',{k:v for k,v in request.items() if k!='dictionary'})
  if dry:done.append({'group':gid,'status':'request_only'});continue
  calls+=1;tries=[]
  for _ in range(2):
   response=backend.call(request);tries.append(response)
   if 'transport_error' not in response:break
  (folder/'response.jsonl').write_text('\n'.join(t.get('stdout','') for t in tries),encoding='utf-8')
  check=check_plan(response['plan'],members[0],request['dictionary']) if isinstance(response.get('plan'),dict) else {'errors':['no plan: '+str(response.get('transport_error') or 'unparseable output')],'warnings':[]}
  ok=not check['errors']
  log={'group':gid,'attempts':attempts,'backend':backend.name,'requested_model':backend.model,'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'tries':[{k:v for k,v in t.items() if k not in ('stdout','plan')} for t in tries],'check':check,'ok':ok,'request_sha256':sha(folder/'request.json'),'note':'check covers structure and self-consistency only; rendered motion still needs separate review'}
  save(folder/'log.json',log)
  if ok:save(folder/'plan.json',response['plan'])
  for a in attempts:
   artifact(run,a,'execution_log',folder/'log.json')
   if ok:artifact(run,a,'plan',folder/'plan.json')
   else:record(run,a,'failed','planning',root=root)
  done.append({'group':gid,'status':'planned' if ok else 'failed','errors':check['errors'],'warnings':len(check['warnings'])})
 return {'backend':backend.name,'model':backend.model,'calls':calls,'groups':done}
