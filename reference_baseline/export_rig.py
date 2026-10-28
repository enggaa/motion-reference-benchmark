"""Export evaluated Blender geometry, not intended keys, for independent action checks."""
import bpy,sys,json,math
from pathlib import Path
from mathutils import Vector
scene_path=Path(sys.argv[sys.argv.index('--')+1]).resolve();out=Path(sys.argv[-1]).resolve()
bpy.ops.wm.open_mainfile(filepath=str(scene_path),load_ui=False,use_scripts=False)
scene=bpy.context.scene;rig=bpy.data.objects['AdultMale_Rig'];q=[];previous={};max_step=0.;events=[];penetrations=[]
names=['root','spine04','spine01','neck01','head','upperarm01.L','lowerarm01.L','wrist.L','upperarm01.R','lowerarm01.R','wrist.R','upperleg01.L','lowerleg01.L','foot.L','toe1-1.L','toe1-1.L','upperleg01.R','lowerleg01.R','foot.R','toe1-1.R','toe1-1.R']
for f in range(1,scene.frame_end+1):
 scene.frame_set(f);bpy.context.view_layer.update();deps=bpy.context.evaluated_depsgraph_get();evaluated=rig.evaluated_get(deps);pb=evaluated.pose.bones
 points=[list(pb[n].head) for n in names];points[15]=list(pb['toe1-1.L'].tail);points[20]=list(pb['toe1-1.R'].tail);q.append(points)
 for b in pb:
  if b.name.startswith('eye.'):continue
  quat=b.matrix.to_quaternion().normalized()
  if b.name in previous:
   angle=math.degrees(2*math.acos(min(1.,abs(previous[b.name].dot(quat)))))
   max_step=max(max_step,angle)
   if angle>35:events.append({'frame':f,'bone':b.name,'step_deg':angle})
  previous[b.name]=quat
 # Conservative torso capsule screen; not a mesh collision solver.
 base=pb['root'].head;top=pb['neck01'].head;axis=top-base;radius=(pb['upperarm01.L'].head-pb['upperarm01.R'].head).length*.25
 for side in ['L','R']:
  hand=pb['wrist.'+side].head;t=max(0,min(1,(hand-base).dot(axis)/axis.length_squared));distance=(hand-(base+axis*t)).length
  if distance<radius:penetrations.append({'frame':f,'side':side,'depth':radius-distance})
out.write_text(json.dumps({'source_scene':str(scene_path),'fps':scene.render.fps,'joint_positions':q,'max_bone_step_degrees':max_step,'rotation_events_over_35deg':events,'torso_proxy_penetrations':penetrations,'collision_scope':'wrist-to-torso capsule only; not full mesh collision validation'},indent=2))
print(out)
