"""Pipeline freeze for the test split (docs/PROTOCOL.md): code, prompts, schemas and model settings are fingerprinted into run.json before any
test call, and every later test stage refuses to run when the fingerprint no longer matches. Development runs are never blocked."""
import datetime,hashlib,json,subprocess
from pathlib import Path
from .core import ROOT,read,save,ensure_binding
def fingerprint(root=ROOT):
 from . import planner,posefit,verify,video
 root=Path(root);files=sorted(list((root/'motionbench').glob('*.py'))+list((root/'tools').glob('render_reference_blender.py')))
 code=hashlib.sha256();prompts={}
 for f in files:code.update(f.relative_to(root).as_posix().encode()+b'\0'+f.read_bytes())
 for name,text in {'planner_system':planner.SYSTEM_PROMPT,'plan_schema':json.dumps(planner.PLAN_SCHEMA,sort_keys=True),'pose_system':posefit.POSE_PROMPT,'pose_penalty':json.dumps(posefit.PENALTY,sort_keys=True),
  'verify_system':verify.VERIFY_PROMPT,'verdict_schema':json.dumps(verify.VERDICT_SCHEMA,sort_keys=True),'video_prompts':video.R2V_PREFIX+'|'+video.SUFFIX,'video_models':json.dumps(video.MODELS,sort_keys=True)}.items():
  prompts[name]=hashlib.sha256(text.encode()).hexdigest()
 return {'code_sha256':code.hexdigest(),'prompt_sha256':prompts}
def _git(root,*args):
 try:return subprocess.run(['git',*args],cwd=root,capture_output=True,text=True,check=True).stdout.strip()
 except (OSError,subprocess.CalledProcessError):return None
def freeze_run(run,planner_model,planner_variant,video_resolution,max_usd,root=ROOT):
 ensure_binding(run,root);run=Path(run);meta=read(run/'run.json')
 if meta.get('frozen'):raise ValueError('Run is already frozen; plan a new run for a new pipeline version')
 if max_usd is None:raise ValueError('A numeric cost cap is required before freezing')
 dirty=_git(root,'status','--porcelain','--','motionbench','tools')
 if dirty:raise ValueError('Commit pipeline changes before freezing:\n'+dirty)
 meta['frozen']=dict(fingerprint(root),git_head=_git(root,'rev-parse','HEAD'),planner_model=planner_model,planner_variant=planner_variant,video_resolution=video_resolution,max_usd=max_usd,utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
 meta['configuration'].update(planner_model=planner_model,planner_variant=planner_variant,numeric_cost_cap=max_usd);save(run/'run.json',meta);return meta['frozen']
def check_frozen(run,root=ROOT,**settings):
 """Raises unless run.json is frozen with the current code, prompts and the given settings (e.g. planner_model='sonnet')."""
 frozen=read(Path(run)/'run.json').get('frozen')
 if not frozen:raise ValueError('Test split requires freeze-pipeline first')
 now=fingerprint(root)
 if now['code_sha256']!=frozen['code_sha256'] or now['prompt_sha256']!=frozen['prompt_sha256']:raise ValueError('Pipeline changed after freezing; version a new run instead of tuning on test')
 for k,v in settings.items():
  if v is not None and frozen.get(k)!=v:raise ValueError(f'Frozen {k}={frozen.get(k)}, requested {v}')
 return frozen
