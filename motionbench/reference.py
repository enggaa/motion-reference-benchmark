"""Plan -> reference MP4 for the shared B/C initial candidate (and C's repaired candidate). Uses only the plan and the generator packet, never benchmark/evaluator."""
import glob,json,os,shutil,subprocess
from pathlib import Path
from .core import ROOT,read,save,sha,artifact,ensure_binding
from .animate import animate
GRID=8
def find_blender():
 found=os.environ.get('MOTIONBENCH_BLENDER') or shutil.which('blender') or next(iter(sorted(glob.glob('C:/Program Files/Blender Foundation/Blender */blender.exe'),reverse=True)),None)
 if not found:raise RuntimeError('Blender not found; set MOTIONBENCH_BLENDER')
 return found
def _ffmpeg(*args):subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y',*map(str,args)],check=True)
def render_plan(plan,duration_s,image,out,blender=None,fps=24,root=ROOT):
 """Writes reference.mp4 (input camera, the R2V reference), reference_front.mp4 and grid_*.png (verification aids), first_frame_vs_input.png and telemetry.json into out."""
 from .posefit import masks,score
 out=Path(out).resolve();out.mkdir(parents=True,exist_ok=True);blender=blender or find_blender()
 frames,telemetry=animate(plan,duration_s,fps);save(out/'frames.json',{'props':telemetry['props'],'frames':frames})
 picks=[round(k*(len(frames)-1)/(GRID-1)) for k in range(GRID)];telemetry['grid_times_s']=[frames[i]['t'] for i in picks]
 for view,name in (('input','reference.mp4'),('front','reference_front.mp4')):
  frames_dir=out/f'frames_{view}'
  if frames_dir.exists():shutil.rmtree(frames_dir)
  p=subprocess.run([blender,'-b','--factory-startup','--disable-autoexec','--python-exit-code','1','--python',str(Path(root)/'tools/render_reference_blender.py'),'--',str(out/'frames.json'),str(frames_dir),view],capture_output=True,text=True,encoding='utf-8',errors='replace')
  if p.returncode!=0 or len(list(frames_dir.glob('frame_*.png')))!=len(frames):raise RuntimeError('Blender render failed: '+p.stdout[-1500:]+p.stderr[-1500:])
  _ffmpeg('-framerate',fps,'-i',frames_dir/'frame_%04d.png','-c:v','libx264','-pix_fmt','yuv420p','-crf',18,'-movflags','+faststart',out/name)
  _ffmpeg('-i',frames_dir/'frame_%04d.png','-vf',"select='"+'+'.join(f'eq(n\\,{i})' for i in picks)+"',scale=288:384,tile=4x2",'-fps_mode','vfr','-frames:v',1,out/f'grid_{view}.png')
 _ffmpeg('-i',image,'-i',out/'frames_input/frame_0000.png','-filter_complex','[0:v]format=rgb24[a];[1:v]format=rgb24[b];[a][b]hstack','-frames:v',1,out/'first_frame_vs_input.png')
 # Same silhouette + skin overlap as the pose fit: an automatic first-frame continuity signal, not a substitute for looking.
 telemetry['first_frame_match']=round(score(masks(image),masks(out/'frames_input/frame_0000.png')),4)
 telemetry.update(plan_sha256=None,video_sha256=sha(out/'reference.mp4'),front_video_sha256=sha(out/'reference_front.mp4'),blender=Path(blender).parent.name);save(out/'telemetry.json',telemetry)
 return telemetry
def render_group(run,group,blender=None,fps=24,register=False,root=ROOT):
 ensure_binding(run,root);run=Path(run).resolve();plan_path=run/'plans'/group/'plan.json'
 if not plan_path.is_file():raise ValueError('No accepted plan for '+group)
 packets=[p for p in read(run/'generator_inputs.json') if p['paired_reference_group']==group];packet=packets[0];out=run/'references'/group
 telemetry=render_plan(read(plan_path),packet['duration_s'],packet['image'],out,blender,fps,root);telemetry.update(group=group,plan_sha256=sha(plan_path));save(out/'telemetry.json',telemetry)
 registered=[]
 if register:
  for q in packets:
   artifact(run,q['attempt_id'],'reference_initial',out/'reference.mp4');registered.append(q['attempt_id'])
 return {'group':group,'video':str(out/'reference.mp4'),'frames':telemetry['frames'],'first_frame_match':telemetry['first_frame_match'],'unreachable_targets':telemetry['unreachable_targets'],'registered':registered}
