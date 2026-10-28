"""Plan keyframes -> per-frame skeleton with fixed segment lengths. Stdlib only; drawing is tools/render_reference_blender.py.
Segment lengths come from the plan's own keyframe 0. Torso and arms interpolate segment directions (forward kinematics), so a raised arm
swings instead of cutting a straight chord through the shoulder. Legs use two-bone IK toward the interpolated ankle so planted feet stay put.
A planner that stretches a limb therefore gets a shorter reach and a logged keyframe error, never a longer bone."""
import math
from .planner import JOINTS
TORSO=[('pelvis','neck'),('neck','head')]+[('neck',s+'shoulder') for s in 'LR']+[('pelvis',s+'hip') for s in 'LR']
ARMS=[(s+'shoulder',s+'elbow',s+'wrist') for s in 'LR']
LEGS=[(s+'hip',s+'knee',s+'ankle') for s in 'LR']
SEGMENTS=TORSO+[(r,m) for r,m,_ in ARMS+LEGS]+[(m,e) for _,m,e in ARMS+LEGS]
def _sub(a,b):return tuple(x-y for x,y in zip(a,b))
def _add(a,b):return tuple(x+y for x,y in zip(a,b))
def _mul(a,k):return tuple(x*k for x in a)
def _dot(a,b):return sum(x*y for x,y in zip(a,b))
def _len(a):return math.sqrt(_dot(a,a))
def _unit(a,fallback):
 n=_len(a);return _mul(a,1/n) if n>1e-9 else fallback
def keyframe_poses(plan):return [(f['time_s'],{p['joint']:(p['x'],p['y'],p['z']) for p in f['joints']}) for f in plan['keyframes']]
def _slopes(times,values):
 # Fritsch-Butland tangents per axis: zero at local extrema, so no overshoot past any keyframe value (feet stay above planned floor contact).
 n=len(values);out=[0.0]*n
 for i in range(1,n-1):
  d0=(values[i]-values[i-1])/(times[i]-times[i-1]);d1=(values[i+1]-values[i])/(times[i+1]-times[i])
  out[i]=0.0 if d0*d1<=0 else 2/(1/d0+1/d1)
 return out
def interpolator(keys):
 """keys: [(time, {name: vector})]; returns t -> {name: vector} with monotone cubic Hermite per component."""
 times=[t for t,_ in keys];table={}
 for name,vec in keys[0][1].items():
  for axis in range(len(vec)):
   values=[track[name][axis] for _,track in keys];table[name,axis]=(values,_slopes(times,values))
 def at(t):
  if t<=times[0]:return dict(keys[0][1])
  if t>=times[-1]:return dict(keys[-1][1])
  i=max(k for k in range(len(times)-1) if times[k]<=t);h=times[i+1]-times[i];s=(t-times[i])/h
  h00,h10,h01,h11=2*s**3-3*s**2+1,s**3-2*s**2+s,-2*s**3+3*s**2,s**3-s**2
  return {name:tuple(h00*table[name,a][0][i]+h10*h*table[name,a][1][i]+h01*table[name,a][0][i+1]+h11*h*table[name,a][1][i+1] for a in range(len(vec))) for name,vec in keys[0][1].items()}
 return at
def segment_lengths(pose):return {(a,b):_len(_sub(pose[b],pose[a])) for a,b in SEGMENTS}
def tracks(pose,rest):
 """What gets interpolated: pelvis and ankle positions plus every segment direction."""
 out={'pelvis':pose['pelvis']}
 for _,_,ankle in LEGS:out[ankle]=pose[ankle]
 for a,b in SEGMENTS:out[a,b]=_unit(_sub(pose[b],pose[a]),_unit(_sub(rest[b],rest[a]),(0,0,1)))
 return out
def solve(sample,lengths):
 pose={'pelvis':sample['pelvis']};deficits={}
 fk=lambda a,b:_add(pose[a],_mul(_unit(sample[a,b],(0,0,1)),lengths[a,b]))
 for a,b in TORSO:pose[b]=fk(a,b)
 for root,mid,end in ARMS:pose[mid]=fk(root,mid);pose[end]=fk(mid,end)
 for root,mid,end in LEGS:
  l1,l2=lengths[root,mid],lengths[mid,end];knee=fk(root,mid);d=_sub(sample[end],pose[root]);dist=_len(d);u=_unit(d,(0,0,-1))
  reach=min(max(dist,abs(l1-l2)+1e-6),l1+l2-1e-6)
  if dist>l1+l2:deficits[end]=dist-(l1+l2)
  hint=_sub(knee,pose[root]);v=_unit(_sub(hint,_mul(u,_dot(hint,u))),(0,-1,0))
  a=(l1*l1-l2*l2+reach*reach)/(2*reach);h=math.sqrt(max(l1*l1-a*a,0))
  pose[mid]=_add(pose[root],_add(_mul(u,a),_mul(v,h)));pose[end]=_add(pose[root],_mul(u,reach))
 return pose,deficits
def animate(plan,duration_s,fps=24):
 keys=keyframe_poses(plan);rest=keys[0][1];lengths=segment_lengths(rest);at=interpolator([(t,tracks(p,rest)) for t,p in keys])
 frames=[];unreachable={};worst=0.0
 for n in range(int(round(duration_s*fps))+1):
  t=n/fps;pose,deficits=solve(at(t),lengths);frames.append({'t':round(t,4),'joints':{j:[round(x,5) for x in pose[j]] for j in JOINTS}})
  for joint,deficit in deficits.items():
   u=unreachable.setdefault(joint,{'frames':0,'max_deficit_m':0.0,'first_t':round(t,4)});u['frames']+=1;u['max_deficit_m']=max(u['max_deficit_m'],deficit)
  worst=max([worst]+[abs(v-lengths[s]) for s,v in segment_lengths(pose).items()])
 # How far the drawn skeleton lands from each planned keyframe: nonzero when the plan changed a segment length.
 keyframe_error={}
 for t,planned in keys:
  pose,_=solve(at(t),lengths)
  for j in JOINTS:keyframe_error[j]=max(keyframe_error.get(j,0.0),math.dist(pose[j],planned[j]))
 contacts=' '.join(plan['initial_pose'].get('contacts',[])).lower()
 telemetry={'fps':fps,'frames':len(frames),'segment_lengths_m':{f'{a}-{b}':round(v,4) for (a,b),v in lengths.items()},'max_segment_length_error_m':worst,
  'unreachable_targets':{j:dict(v,max_deficit_m=round(v['max_deficit_m'],4)) for j,v in unreachable.items()},
  'max_keyframe_error_m':{j:round(v,4) for j,v in sorted(keyframe_error.items(),key=lambda x:-x[1]) if v>.005},
  'first_frame_shift_m':max(math.dist(frames[0]['joints'][j],rest[j]) for j in JOINTS),
  'props':{'chair':plan['initial_pose']['pose_class']=='seated' or 'chair' in contacts or 'seat' in contacts},
  'note':'Lengths fixed to keyframe 0 of the plan; arms/torso interpolate segment directions, legs reach interpolated ankles. Unreachable targets are clamped, not stretched.'}
 return frames,telemetry
def turning_points(times,values,threshold):
 """Zigzag extremes: a turn counts only after the value comes back by at least threshold, so hand jitter is not a repetition."""
 out=[];trend=0;cand=0
 for i,v in enumerate(values):
  if trend==0:
   if abs(v-values[0])>=threshold:trend=1 if v>values[0] else -1;cand=i
  elif trend*(v-values[cand])>0:cand=i
  elif trend*(values[cand]-v)>=threshold:out.append((times[cand],values[cand],'max' if trend>0 else 'min'));trend=-trend;cand=i
 return out
def _spans(times,flags,min_len):
 spans=[];start=None
 for t,f in zip(times+[None],flags+[False]):
  if f and start is None:start=t
  if not f and start is not None:
   end=prev
   if end-start>=min_len:spans.append([round(start,2),round(end,2)])
   start=None
  prev=t
 return spans
def motion_summary(frames,fps):
 """Measured on the rendered skeleton (not the plan) so a reviewer can count repetitions and timings that a few sampled frames cannot resolve."""
 times=[f['t'] for f in frames];J=lambda f,k:f['joints'][k];out={}
 for s,side in (('R','right'),('L','left')):
  lateral=[J(f,s+'wrist')[0]-J(f,s+'shoulder')[0] for f in frames];height=[J(f,s+'wrist')[2]-J(f,s+'shoulder')[2] for f in frames]
  outward=-1 if s=='R' else 1
  turns=[{'t':round(t,2),'toward':'outward' if (kind=='max')==(outward>0) else 'inward'} for t,v,kind in turning_points(times,lateral,.04)]
  out[side+'_wrist']={'lateral_turns':turns,'near_or_above_shoulder_s':_spans(times,[h>-.12 for h in height],.2),'above_head_s':_spans(times,[J(f,s+'wrist')[2]>J(f,'head')[2] for f in frames],.2)}
 speed=[0.0]+[max(math.dist(a['joints'][j],b['joints'][j]) for j in JOINTS)*fps for a,b in zip(frames,frames[1:])]
 out['whole_body_still_s']=_spans(times,[v<.05 for v in speed],.5)
 out['pelvis_height_m']={'start':round(J(frames[0],'pelvis')[2],3),'end':round(J(frames[-1],'pelvis')[2],3)}
 return out
