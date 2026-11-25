"""Final video generation for conditions A/B/C through fal.ai's hosted Seedance 2.0 (docs/PIPELINE.md).
A: image-to-video, the input image is the start frame. B/C: reference-to-video, the input image is @Image1 and the reference video @Video1;
in that mode the image is a reference, not a forced first frame, so start continuity is a separate secondary result (docs/PROTOCOL.md).
Endpoint names, parameters and prices come from fal's model pages checked on 2026-10-29. The network path is unverified until a FAL_KEY exists;
the dry run (payloads, cost estimate, budget cap) is what has been exercised."""
import base64,datetime,json,os,subprocess,time,urllib.error,urllib.request
from pathlib import Path
from .core import ROOT,read,save,sha,record,ensure_binding
MODELS={'direct_i2v':'bytedance/seedance-2.0/image-to-video','llm_reference_r2v':'bytedance/seedance-2.0/reference-to-video','verified_reference_r2v':'bytedance/seedance-2.0/reference-to-video'}
# 3:4 portrait, the benchmark images' aspect. Exact output sizes per tier are fal's; these drive the estimate only.
SIZES={'480p':(480,640),'720p':(720,960)}
USD_PER_1K_TOKENS={'plain':.014,'video_reference':.0086016}
# The researcher's video prompt template (motion-expression/prompts/video-prompt-template.md, 2026-09-05). The providers take no system
# role, so it goes in the prompt. Kept as written except "show the full body throughout", which v0.2's cropped framings would contradict:
# the shot keeps the input image's framing instead. A and B/C share every line except the reference-video sentence.
VIDEO_TEMPLATE=("Create one continuous {duration}-second shot. Use {image} for the character's appearance. {reference}Action: {action}. "
 "Keep a fixed camera and the framing of the input image. Preserve the character's appearance. Do not add cuts, facial acting, or audio.")
R2V_REFERENCE='Use @Video1 for body motion, action order, pauses, and timing. '
SUFFIX=VIDEO_TEMPLATE;R2V_PREFIX=R2V_REFERENCE
# The researcher's system prompt (prompts/system.md: motion-expression/prompts/planner-system.md verbatim plus an overall-flow paragraph) goes first in every
# video prompt, I2V and R2V alike, because the video APIs have no system role.
SYSTEM_TEXT=(ROOT/'prompts/system.md').read_text(encoding='utf-8').strip()
def prompt(arm,request,duration_s=6):
 if arm=='direct_i2v':body=VIDEO_TEMPLATE.format(duration=int(duration_s),image='the input image',reference='',action=request)
 else:body=VIDEO_TEMPLATE.format(duration=int(duration_s),image='@Image1',reference=R2V_REFERENCE,action=request)
 return SYSTEM_TEXT+chr(10)*2+body
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
# fal's R2V accepts reference videos between about 480p (640x640) and 720p (834x1112); our renders are 576x768, below the floor
# (dev-006 attempt 0002 was rejected with HTTP 422). The submitted copy is upscaled to 720x960; the registered reference is unchanged.
SUBMIT_SIZE=(720,960)
def submit_copy(path):
 """Upscaled H.264 copy of a reference for submission, cached next to it."""
 path=Path(path);out=path.with_name(path.stem+f'_submit{SUBMIT_SIZE[0]}x{SUBMIT_SIZE[1]}.mp4')
 if not out.is_file():
  subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(path),'-vf',f'scale={SUBMIT_SIZE[0]}:{SUBMIT_SIZE[1]}:flags=lanczos','-c:v','libx264','-pix_fmt','yuv420p','-an',str(out)],check=True)
 return out
def build_payload(row,packet,reference,resolution):
 base={'prompt':prompt(row['arm'],packet['request'],packet['duration_s']),'resolution':resolution,'duration':str(int(packet['duration_s'])),'aspect_ratio':'3:4','generate_audio':False}
 if row['arm']=='direct_i2v':return dict(base,image_url=_data_uri(packet['image'],'image/png'))
 return dict(base,image_urls=[_data_uri(packet['image'],'image/png')],video_urls=[_data_uri(submit_copy(reference['path']),'video/mp4')])
class SubmittedJobError(RuntimeError):
 """The job was accepted (and may be billed); retrying must fetch it again, never submit a new one."""
 def __init__(self,message,request_id):super().__init__(message);self.request_id=request_id
class FalSeedance:
 name='fal-seedance-2.0'
 def __init__(self,key=None,poll_s=5,timeout_s=900):
  self.key=key or os.environ.get('FAL_KEY');self.poll_s=poll_s;self.timeout_s=timeout_s
  # Windows Python can lack the issuer of fal's media CDN (dev-007: CERTIFICATE_VERIFY_FAILED on download); use certifi when present.
  try:
   import certifi,ssl;self.ctx=ssl.create_default_context(cafile=certifi.where())
  except ImportError:self.ctx=None
 def _http(self,url,payload=None):
  req=urllib.request.Request(url,data=json.dumps(payload).encode() if payload is not None else None,headers={'Authorization':f'Key {self.key}','Content-Type':'application/json'},method='POST' if payload is not None else 'GET')
  try:
   with urllib.request.urlopen(req,timeout=120,context=self.ctx) as r:return json.loads(r.read())
  except urllib.error.HTTPError as e:
   # Keep the provider's reason (dev-006: the 422 body said the image looked like a real person).
   raise RuntimeError(f'HTTP {e.code}: '+e.read().decode('utf-8','replace')[:1500]) from None
 def _download(self,url,out):
  with urllib.request.urlopen(url,timeout=300,context=self.ctx) as r:Path(out).write_bytes(r.read())
 def submit(self,model,payload):
  if not self.key:raise RuntimeError('FAL_KEY is not set')
  return self._http(f'https://queue.fal.run/{model}',payload)
 def collect(self,model,request_id,out,started=None):
  """Poll an accepted job, fetch its result and download the video. Safe to repeat: it never submits."""
  started=started or time.time();app='/'.join(model.split('/')[:2]);base=f'https://queue.fal.run/{app}/requests/{request_id}'
  while True:
   status=self._http(base+'/status')
   if status.get('status')=='COMPLETED':break
   if status.get('status') not in ('IN_QUEUE','IN_PROGRESS'):raise RuntimeError('fal job failed: '+json.dumps(status)[:500])
   if time.time()-started>self.timeout_s:raise TimeoutError('fal job timed out')
   time.sleep(self.poll_s)
  result=self._http(base);self._download(result['video']['url'],out)
  return {'request_id':request_id,'seed':result.get('seed'),'latency_s':round(time.time()-started,1)}
 def generate(self,model,payload,out):
  """Submit once, then collect. After acceptance every failure is a SubmittedJobError so the caller retries collect(), not the job."""
  started=time.time();job=self.submit(model,payload);rid=job.get('request_id')
  try:return self.collect(model,rid,out,started)
  except Exception as e:raise SubmittedJobError(f'{type(e).__name__}: {e}',rid) from e
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
  logged=dict(payload,**({'image_url':{'path':packet['image'],'sha256':packet['image_sha256']}} if 'image_url' in payload else {'image_urls':[{'path':packet['image'],'sha256':packet['image_sha256']}],'video_urls':[{'path':str(submit_copy(ref['path'])),'sha256':sha(submit_copy(ref['path'])),'upscaled_from':{'path':ref['path'],'sha256':ref['sha256']}}]}))
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
  info=None;request_id=None
  for _ in range(2):
   try:
    # dev-007 0001 was billed twice: a download error re-ran generate() and submitted a second job. Once a job is accepted, retry collect() only.
    info=backend.collect(model,request_id,out) if request_id else backend.generate(model,payload,out);errors=[];break
   except Exception as e:
    request_id=getattr(e,'request_id',None) or request_id;errors.append(f'{type(e).__name__}: {e}'[:2000])
  stamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
  if errors:
   record(run,row['attempt_id'],'failed','transport' if any(x.startswith(('URLError','TimeoutError','HTTPError')) for x in errors) else 'final_generation',root=root)
   _note(run,row['attempt_id'],model_ids={'video':model},cost=None,generation_log={'errors':errors,'request_id':request_id,'utc':stamp});summary['executed'].append({'attempt':row['attempt_id'],'status':'failed'})
  else:
   record(run,row['attempt_id'],'succeeded',output=out,root=root)
   _note(run,row['attempt_id'],model_ids={'video':model},cost={'estimated_usd':usd},latency_s=info['latency_s'],generation_log=dict(info,utc=stamp));summary['executed'].append({'attempt':row['attempt_id'],'status':'succeeded'})
 return summary
