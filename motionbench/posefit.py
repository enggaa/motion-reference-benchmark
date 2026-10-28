"""Silhouette fitting of the initial pose: start from the LLM's estimate, render candidate poses with the renderer's mannequin and camera,
and keep the one whose silhouette best overlaps the supplied input image. Uses the input image and our own renderer only, never benchmark/evaluator.
Assumes the input was drawn with the same mannequin and camera, which holds for this synthetic benchmark but not for real photos.
An earlier variant asked the LLM to correct its own pose from a side-by-side picture; on D08 it pushed the lean further the wrong way, so the
correction is numeric and the LLM only supplies the starting estimate, pose class and contacts."""
import json,math,subprocess,tempfile
from pathlib import Path
from .core import ROOT,save
from .planner import JOINTS,PLAN_SCHEMA,RIG,_joints
W,H=144,192
POSE_SCHEMA=PLAN_SCHEMA['properties']['initial_pose']
POSE_PROMPT=f"""You estimate the starting 3D pose of a procedural mannequin from one image.
{RIG}
Give all 15 joints, the pose class, observations, uncertainties and visible contacts. Do not assume a standing or T-pose. Read the posture, the torso lean direction from the character's own point of view, arm bends and leg bends from the image."""
UPPER=('neck','head','Lshoulder','Rshoulder')
# Parameter -> initial step. Angles in degrees, scale as a ratio, shifts in metres.
STEPS={'lean_side':8,'lean_front':8,'scale':.04,'shift_x':.03,'shift_y':.03,'Larm_side':12,'Rarm_side':12,'Larm_front':12,'Rarm_front':12,'Lelbow':15,'Relbow':15}
# Score cost per unit of change, so a move must buy visible overlap. Front-back moves (lean_front, arm_front, shift_y) cost double: the input
# view barely sees depth, and unpenalised fits swung arms 63-75 degrees fore-aft for small overlap gains while 3D error grew (dev-001 D03, D04).
PENALTY={'lean_side':.0004,'lean_front':.0008,'scale':.1,'shift_x':.1,'shift_y':.2,'Larm_side':.0004,'Rarm_side':.0004,'Larm_front':.0008,'Rarm_front':.0008,'Lelbow':.0004,'Relbow':.0004}
# Fits that end below this overlap do not describe the pictured body (dev-001 fits ended at 0.75-0.89; dev-002's axis-swapped poses at 0.03-0.06).
FIT_MIN=.5
def penalty(params):return sum(PENALTY[k]*abs(v) for k,v in params.items())
def _rot(p,c,axis,deg):
 """Rodrigues rotation of point p about the axis through c."""
 a=math.radians(deg);k=[x/math.sqrt(sum(y*y for y in axis)) for x in axis];v=[p[i]-c[i] for i in range(3)]
 cross=(k[1]*v[2]-k[2]*v[1],k[2]*v[0]-k[0]*v[2],k[0]*v[1]-k[1]*v[0]);dot=sum(k[i]*v[i] for i in range(3))
 return tuple(c[i]+v[i]*math.cos(a)+cross[i]*math.sin(a)+k[i]*dot*(1-math.cos(a)) for i in range(3))
def transform(joints,params):
 """Arms rotate about their shoulders, then the torso leans about the pelvis while the arms keep their direction and follow the shoulders
 (a leaning person's arms still hang), then the whole body scales about the floor point under the feet and shifts. Segment lengths change only through the uniform scale."""
 j=dict(joints)
 for s in 'LR':
  sh=j[s+'shoulder']
  for name,axis in ((s+'arm_side',(0,1,0)),(s+'arm_front',(1,0,0))):
   if params.get(name):j[s+'elbow'],j[s+'wrist']=_rot(j[s+'elbow'],sh,axis,params[name]),_rot(j[s+'wrist'],sh,axis,params[name])
  if params.get(s+'elbow'):
   upper=[j[s+'elbow'][i]-sh[i] for i in range(3)];fore=[j[s+'wrist'][i]-j[s+'elbow'][i] for i in range(3)]
   normal=(upper[1]*fore[2]-upper[2]*fore[1],upper[2]*fore[0]-upper[0]*fore[2],upper[0]*fore[1]-upper[1]*fore[0])
   if sum(x*x for x in normal)<1e-8:normal=(1,0,0)
   j[s+'wrist']=_rot(j[s+'wrist'],j[s+'elbow'],normal,params[s+'elbow'])
 for name,axis in (('lean_side',(0,1,0)),('lean_front',(-1,0,0))):
  if params.get(name):
   before={s:j[s+'shoulder'] for s in 'LR'}
   for k in UPPER:j[k]=_rot(j[k],j['pelvis'],axis,params[name])
   for s in 'LR':
    shift=[j[s+'shoulder'][i]-before[s][i] for i in range(3)]
    for k in (s+'elbow',s+'wrist'):j[k]=tuple(j[k][i]+shift[i] for i in range(3))
 scale=1+params.get('scale',0);fx=(j['Lankle'][0]+j['Rankle'][0])/2;fy=(j['Lankle'][1]+j['Rankle'][1])/2
 return {k:(fx+(x-fx)*scale+params.get('shift_x',0),fy+(y-fy)*scale+params.get('shift_y',0),z*scale) for k,(x,y,z) in j.items()}
def _classes(b,offset=0):
 # Red minus blue separates the scene: beige head/hands >= +5, blue body and joints <= -14, gray background, floor, shadows and chair in between.
 rb=[b[i]-b[i+2] for i in range(offset,offset+W*H*3,3)];return [x>=5 or x<=-14 for x in rb],[x>=5 for x in rb]
def _decode(path):return subprocess.run(['ffmpeg','-v','error','-i',str(path),'-vf',f'scale={W}:{H}','-f','rawvideo','-pix_fmt','rgb24','-'],capture_output=True,check=True).stdout
def masks(path):return _classes(_decode(path))
def iou(a,b):
 union=sum(x or y for x,y in zip(a,b));return sum(x and y for x,y in zip(a,b))/union if union else 0.0
def score(target,candidate):
 """Mean of whole-silhouette IoU and skin IoU. The skin term pins hands and head, which a silhouette alone lets fold into the torso."""
 return (iou(target[0],candidate[0])+iou(target[1],candidate[1]))/2
def render_batch(poses,chair,blender,keep=None):
 with tempfile.TemporaryDirectory() as d:
  d=Path(d);save(d/'frames.json',{'props':{'chair':chair},'frames':[{'t':0,'joints':{j:list(p[j]) for j in JOINTS}} for p in poses]})
  out=Path(keep).resolve() if keep else d/'f'
  p=subprocess.run([blender,'-b','--factory-startup','--disable-autoexec','--python-exit-code','1','--python',str(ROOT/'tools/render_reference_blender.py'),'--',str(d/'frames.json'),str(out)],capture_output=True,text=True,encoding='utf-8',errors='replace')
  if p.returncode or len(list(out.glob('frame_*.png')))<len(poses):raise RuntimeError('Blender render failed: '+p.stdout[-800:])
  b=_decode(out/'frame_%04d.png');return [_classes(b,o) for o in range(0,W*H*3*len(poses),W*H*3)]
def is_seated(pose):
 contacts=' '.join(pose.get('contacts',[])).lower();return pose.get('pose_class')=='seated' or 'chair' in contacts or 'seat' in contacts
STAGES=[('lean_side','lean_front','scale','shift_x','shift_y'),('Larm_side','Rarm_side','Larm_front','Rarm_front'),tuple(STEPS)]
def fit(image,pose,blender,iterations=6,workdir=None):
 """Staged coordinate search: whole-body lean/scale/shift, then arm directions, then every parameter. Each round renders every +/- step of the
 stage (one and two steps) in one Blender call, takes the better of the best single move and the sum of all improving moves, and halves the steps when nothing improves.
 Fitting everything at once let a forearm fold behind the torso instead of swinging the arm out to the visible hand (D08)."""
 errors=[];base=_joints(pose.get('joints'),'pose',errors)
 if errors:raise ValueError('; '.join(errors))
 target=masks(image);chair=is_seated(pose);params=dict.fromkeys(STEPS,0.0)
 start=score(target,render_batch([base],chair,blender)[0]);best=start;raw=start;history=[round(best,4)]
 for stage in STAGES:
  steps={k:STEPS[k] for k in stage}
  for _ in range(iterations):
   # Single and double steps: the score is not monotone along a limb swing (D08's right arm dips at 12 degrees and peaks at 24).
   moves=[(name,sign*k*steps[name]) for name in stage for sign in (-1,1) for k in (1,2)]
   candidates=[dict(params,**{name:params[name]+delta}) for name,delta in moves]
   raws=[score(target,m) for m in render_batch([transform(base,c) for c in candidates],chair,blender)];scores=[r-penalty(c) for r,c in zip(raws,candidates)]
   better={}
   for (name,delta),s in zip(moves,scores):
    if s>best and s>better.get(name,(0,0))[1]:better[name]=(delta,s)
   if not better:
    steps={k:v/2 for k,v in steps.items()};history.append(round(best,4));continue
   single=max(range(len(scores)),key=scores.__getitem__);combo=dict(params,**{n:params[n]+d for n,(d,_) in better.items()})
   combo_raw=score(target,render_batch([transform(base,combo)],chair,blender)[0]) if len(better)>1 else -1;combo_score=combo_raw-penalty(combo)
   params,best,raw=(combo,combo_score,combo_raw) if combo_score>scores[single] else (candidates[single],scores[single],raws[single]);history.append(round(best,4))
 fitted=transform(base,params)
 if workdir:render_batch([base,fitted],chair,blender,keep=workdir)
 out=dict(pose,joints=[{'joint':j,'x':round(fitted[j][0],4),'y':round(fitted[j][1],4),'z':round(fitted[j][2],4)} for j in JOINTS])
 out['observations']=list(pose.get('observations',[]))+['Joint positions adjusted by silhouette fitting against the input image (render-and-compare).']
 return out,{'score_start':round(start,4),'score_end':round(raw,4),'objective_history':history,'penalty':round(penalty(params),4),'params':{k:round(v,4) for k,v in params.items() if v},'note':'Score is the mean of silhouette IoU and skin (head/hands) IoU between the input and our render of the pose; it is not a joint error. The search maximises score minus penalty.'}
