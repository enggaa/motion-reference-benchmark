"""Plan -> reference MP4 for the shared B/C initial candidate. Uses only plan.json and the generator packet, never benchmark/evaluator."""
import glob,json,os,shutil,subprocess
from pathlib import Path
from .core import ROOT,read,save,sha,artifact,ensure_binding
from .animate import animate
def find_blender():
 found=os.environ.get('MOTIONBENCH_BLENDER') or shutil.which('blender') or next(iter(sorted(glob.glob('C:/Program Files/Blender Foundation/Blender */blender.exe'),reverse=True)),None)
 if not found:raise RuntimeError('Blender not found; set MOTIONBENCH_BLENDER')
 return found
def render_group(run,group,blender=None,fps=24,register=False,root=ROOT):
 ensure_binding(run,root);run=Path(run).resolve();plan_path=run/'plans'/group/'plan.json'
 if not plan_path.is_file():raise ValueError('No accepted plan for '+group)
 packets=[p for p in read(run/'generator_inputs.json') if p['paired_reference_group']==group];packet=packets[0]
 out=run/'references'/group;frames_dir=out/'frames'
 if frames_dir.exists():shutil.rmtree(frames_dir)
 out.mkdir(parents=True,exist_ok=True)
 frames,telemetry=animate(read(plan_path),packet['duration_s'],fps);telemetry.update(group=group,plan_sha256=sha(plan_path))
 save(out/'frames.json',{'props':telemetry['props'],'frames':frames})
 script=Path(root)/'tools/render_reference_blender.py'
 p=subprocess.run([blender or find_blender(),'-b','--factory-startup','--disable-autoexec','--python-exit-code','1','--python',str(script),'--',str(out/'frames.json'),str(frames_dir)],capture_output=True,text=True,encoding='utf-8',errors='replace')
 if p.returncode!=0 or len(list(frames_dir.glob('frame_*.png')))!=len(frames):raise RuntimeError('Blender render failed: '+p.stdout[-1500:]+p.stderr[-1500:])
 video=out/'reference.mp4'
 subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-framerate',str(fps),'-i',str(frames_dir/'frame_%04d.png'),'-c:v','libx264','-pix_fmt','yuv420p','-crf','18','-movflags','+faststart',str(video)],check=True)
 # Side-by-side of the supplied input image and frame 0: the first-frame continuity check is done by eye, not by this file.
 subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',packet['image'],'-i',str(frames_dir/'frame_0000.png'),'-filter_complex','[0:v]format=rgb24[a];[1:v]format=rgb24[b];[a][b]hstack','-frames:v','1',str(out/'first_frame_vs_input.png')],check=True)
 telemetry.update(video_sha256=sha(video),blender=Path(blender or find_blender()).parent.name);save(out/'telemetry.json',telemetry)
 registered=[]
 if register:
  for q in packets:
   artifact(run,q['attempt_id'],'reference_initial',video);registered.append(q['attempt_id'])
 return {'group':group,'video':str(video),'frames':len(frames),'unreachable_targets':telemetry['unreachable_targets'],'registered':registered}
