"""Draw a planned keyframe strip (front + side stick figures) next to the input image. Inspection aid only: not a renderer, not a solver."""
import base64,json,sys,html
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from motionbench.planner import BONES
LIMBS=BONES+[('neck',s+'shoulder') for s in 'LR']+[('pelvis',s+'hip') for s in 'LR']
def figure(joints,ox,oy,scale,view):
 # Front view looks from -Y (character's left +X on the right); side view looks from the character's right (front -Y on the right).
 px=lambda p:ox+scale*(p[0] if view=='front' else -p[1]);py=lambda p:oy-scale*p[2]
 out=[f'<line x1="{ox-scale*.6:.1f}" y1="{oy:.1f}" x2="{ox+scale*.6:.1f}" y2="{oy:.1f}" stroke="#888"/>']
 for a,b in LIMBS:
  colour='#c0392b' if a[0]=='R' or b[0]=='R' else '#2471a3' if a[0]=='L' or b[0]=='L' else '#333'
  out.append(f'<line x1="{px(joints[a]):.1f}" y1="{py(joints[a]):.1f}" x2="{px(joints[b]):.1f}" y2="{py(joints[b]):.1f}" stroke="{colour}" stroke-width="3" stroke-linecap="round"/>')
 out.append(f'<circle cx="{px(joints["head"]):.1f}" cy="{py(joints["head"]):.1f}" r="{scale*.09:.1f}" fill="none" stroke="#333" stroke-width="2"/>')
 return out
def preview(plan_dir,out=None):
 plan_dir=Path(plan_dir);plan=json.loads((plan_dir/'plan.json').read_text(encoding='utf-8'));request=json.loads((plan_dir/'request.json').read_text(encoding='utf-8'))
 frames=plan['keyframes'];cell=150;scale=110;image_w=225;width=image_w+20+cell*len(frames);height=480
 svg=[f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" font-family="sans-serif" font-size="11"><rect width="100%" height="100%" fill="white"/>']
 data=base64.b64encode(Path(request['image']).read_bytes()).decode()
 svg.append(f'<image x="0" y="40" width="{image_w}" height="300" href="data:image/png;base64,{data}"/><text x="4" y="30">input {html.escape(request["case_id"])}</text>')
 svg.append(f'<text x="{image_w+20}" y="14">red = character right, blue = left · top: front view, bottom: side view (front to the right)</text>')
 for i,f in enumerate(frames):
  joints={p['joint']:(p['x'],p['y'],p['z']) for p in f['joints']};ox=image_w+20+cell*i+cell/2
  svg+=figure(joints,ox,265,scale,'front')+figure(joints,ox,455,scale*.85,'side')
  svg.append(f'<text x="{ox:.1f}" y="40" text-anchor="middle">{f["time_s"]:g}s · {html.escape(f["origin"])}</text>')
 svg.append('</svg>');out=Path(out or plan_dir/'preview.svg');out.write_text('\n'.join(svg),encoding='utf-8');return out
if __name__=='__main__':print(preview(*sys.argv[1:]))
