"""Final video generation for conditions A/B/C through fal.ai's hosted Seedance 2.0 (docs/ADAPTER_CONTRACT.md).
A: image-to-video, the input image is the start frame. B/C: reference-to-video, the input image is @Image1 and the reference video @Video1;
in that mode the image is a reference, not a forced first frame, so start continuity is a separate secondary result (docs/PROTOCOL.md).
Endpoint names, parameters and prices come from fal's model pages checked on 2026-10-29. The network path is unverified until a FAL_KEY exists;
the dry run (payloads, cost estimate, budget cap) is what has been exercised."""
import base64,datetime,json,os,time,urllib.request
from pathlib import Path
from .core import ROOT,read,save,sha,record,ensure_binding
MODELS={'direct_i2v':'bytedance/seedance-2.0/image-to-video','llm_reference_r2v':'bytedance/seedance-2.0/reference-to-video','verified_reference_r2v':'bytedance/seedance-2.0/reference-to-video'}
# 3:4 portrait, the benchmark images' aspect. Exact output sizes per tier are fal's; these drive the estimate only.
SIZES={'480p':(480,640),'720p':(720,960)}
USD_PER_1K_TOKENS={'plain':.014,'video_reference':.0086016}
SUFFIX='Keep the character, its appearance, the scene and the camera of the input image.'
R2V_PREFIX='@Image1 is the input image. Make its character perform the body motion shown in @Video1, starting from the pose in @Image1.'
def prompt(arm,request):return f'{request} {SUFFIX}' if arm=='direct_i2v' else f'{R2V_PREFIX} {request} {SUFFIX}'
def estimate_usd(resolution,duration_s,reference_s=0.0):
 """fal's token formula (height x width x seconds x 24 / 1024). Reference-video seconds are counted too, as an upper bound; video references lower the rate."""
 w,h=SIZES[resolution];tokens=w*h*(duration_s+reference_s)*24/1024
 return round(tokens/1000*USD_PER_1K_TOKENS['video_reference' if reference_s else 'plain'],4)
def _data_uri(path,mime):return f'data:{mime};base64,'+base64.b64encode(Path(path).read_bytes()).decode()
def _reference_for(row):
 """Which reference an attempt sends, or why it cannot be generated yet."""
 if row['arm']=='direct_i2v':return None,None
 if row['arm']=='llm_reference_r2v':
  ref=row['outputs'].get('reference_initial');return (ref,None) if ref else (None,'no initial reference registered')
 gate=row['outputs'].get('gate_decision')
 if not gate:return None,'no gate decision yet'
 decision=read(gate['path'])
 if decision['decision']!='pass':return None,'gate did not pass'
 ref=row['outputs'].get('reference_repaired' if decision['reference_for_final']=='repaired' else 'reference_initial')
 return (ref,None) if ref else (None,'gated reference missing')
def build_payload(row,packet,reference,resolution):
 base={'prompt':prompt(row['arm'],packet['request']),'resolution':resolution,'duration':str(int(packet['duration_s'])),'aspect_ratio':'3:4','generate_audio':False}
 if row['arm']=='direct_i2v':return dict(base,image_url=_data_uri(packet['image'],'image/png'))
 return dict(base,image_urls=[_data_uri(packet['image'],'image/png')],video_urls=[_data_uri(reference['path'],'video/mp4')])
class FalSeedance:
 name='fal-seedance-2.0'
 def __init__(self,key=None,poll_s=5,timeout_s=900):self.key=key or os.environ.get('FAL_KEY');self.poll_s=poll_s;self.timeout_s=timeout_s
 def _http(self,url,payload=None):
  req=urllib.request.Request(url,data=json.dumps(payload).encode() if payload is not None else None,headers={'Authorization':f'Key {self.key}','Content-Type':'application/json'},method='POST' if payload is not None else 'GET')
  with urllib.request.urlopen(req,timeout=120) as r:return json.loads(r.read())
 def _download(self,url,out):
  with urllib.request.urlopen(url,timeout=300) as r:Path(out).write_bytes(r.read())
 def generate(self,model,payload,out):
  """fal queue API: submit, poll status, fetch result, download the video. Returns metadata; raises on failure."""
  if not self.key:raise RuntimeError('FAL_KEY is not set')
  started=time.time();job=self._http(f'https://queue.fal.run/{model}',payload)
  while True:
   status=self._http(job['status_url'])
   if status.get('status')=='COMPLETED':break
   if status.get('status') not in ('IN_QUEUE','IN_PROGRESS'):raise RuntimeError('fal job failed: '+json.dumps(status)[:500])
   if time.time()-started>self.timeout_s:raise TimeoutError('fal job timed out')
   time.sleep(self.poll_s)
  result=self._http(job['response_url']);self._download(result['video']['url'],out)
  return {'request_id':job.get('request_id'),'seed':result.get('seed'),'latency_s':round(time.time()-started,1)}
def _note(run,attempt,**fields):
 ledger=Path(run)/'ledger.json';rows=read(ledger);row=next(r for r in rows if r['attempt_id']==attempt)
 for k,v in fields.items():
  if isinstance(row.get(k),dict) and isinstance(v,dict):row[k].update(v)
  else:row[k]=v
 save(ledger,rows)
def generate_run(run,backend=None,resolution='480p',execute=False,max_usd=None,attempts=None,root=ROOT):
 """Dry run by default: writes video_requests/<attempt>.json and the cost estimate. execute=True calls the backend; max_usd caps the estimated total before any call."""
 ensure_binding(run,root);run=Path(run).resolve();meta=read(run/'run.json')
 if meta['split']=='test':
  from .freeze import check_frozen
  frozen=check_frozen(run,root,video_resolution=resolution)
  if max_usd is None or max_usd>frozen['max_usd']:raise ValueError(f"Test generation needs --max-usd at or below the frozen cap {frozen['max_usd']}")
 packets={p['attempt_id']:p for p in read(run/'generator_inputs.json')};plans=[];skipped={}
 for row in read(run/'ledger.json'):
  if row['status']!='pending' or (attempts and row['attempt_id'] not in attempts):continue
  ref,why=_reference_for(row)
  if why:skipped[row['attempt_id']]=why;continue
  packet=packets[row['attempt_id']];reference_s=packet['duration_s'] if ref else 0
  payload=build_payload(row,packet,ref,resolution);usd=estimate_usd(resolution,packet['duration_s'],reference_s)
  logged=dict(payload,**({'image_url':{'path':packet['image'],'sha256':packet['image_sha256']}} if 'image_url' in payload else {'image_urls':[{'path':packet['image'],'sha256':packet['image_sha256']}],'video_urls':[{'path':ref['path'],'sha256':ref['sha256']}]}))
  (run/'video_requests').mkdir(exist_ok=True);save(run/'video_requests'/f"{row['attempt_id']}.json",{'model':MODELS[row['arm']],'arm':row['arm'],'case_id':row['case_id'],'payload':logged,'estimated_usd':usd})
  plans.append((row,MODELS[row['arm']],payload,usd))
 total=round(sum(p[3] for p in plans),2)
 summary={'resolution':resolution,'planned':len(plans),'estimated_usd':total,'by_arm':{a:sum(1 for p in plans if p[0]['arm']==a) for a in MODELS},'skipped':skipped,'executed':[]}
 if max_usd is not None and total>max_usd:raise ValueError(f'Estimated ${total} exceeds the cap ${max_usd}; nothing was sent')
 if not execute:return summary
 backend=backend or FalSeedance();(run/'finals').mkdir(exist_ok=True)
 config=meta['configuration'];config.update(video_model=f'{backend.name}:{resolution}',numeric_cost_cap=max_usd,conditioning_modes_confirmed=False);meta['execution_enabled']=True;save(run/'run.json',meta)
 for row,model,payload,usd in plans:
  out=run/'finals'/f"{row['attempt_id']}.mp4";errors=[]
  for _ in range(2):
   try:info=backend.generate(model,payload,out);errors=[];break
   except Exception as e:errors.append(f'{type(e).__name__}: {e}'[:500])
  stamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
  if errors:
   record(run,row['attempt_id'],'failed','transport' if any(x.startswith(('URLError','TimeoutError','HTTPError')) for x in errors) else 'final_generation',root=root)
   _note(run,row['attempt_id'],model_ids={'video':model},cost=None,generation_log={'errors':errors,'utc':stamp});summary['executed'].append({'attempt':row['attempt_id'],'status':'failed'})
  else:
   record(run,row['attempt_id'],'succeeded',output=out,root=root)
   _note(run,row['attempt_id'],model_ids={'video':model},cost={'estimated_usd':usd},latency_s=info['latency_s'],generation_log=dict(info,utc=stamp));summary['executed'].append({'attempt':row['attempt_id'],'status':'succeeded'})
 return summary
