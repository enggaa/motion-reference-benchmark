"""Blender-only: draw solved frames with the same procedural mannequin, camera and lighting as tools/render_inputs.py.
Usage: blender -b --factory-startup --python tools/render_reference_blender.py -- frames.json out_dir [input|front]
The input view uses the camera the planner read off the input image (props.camera: yaw around the character and framing); plans without one
fall back to the v0.1 benchmark camera. The front view (orthographic, from -Y) is only a verification aid for motions the input view hides.
props.body sets the mannequin's girth (build) and head size (age group); its height comes from the plan's own segment lengths."""
import math
import bpy,json,sys
from pathlib import Path
from mathutils import Vector
args=sys.argv[sys.argv.index('--')+1:];frames_path,out=args[:2];view=args[2] if len(args)>2 else 'input';data=json.loads(Path(frames_path).read_text(encoding='utf-8'));out=Path(out);out.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True);scene=bpy.context.scene
def material(name,color):
 m=bpy.data.materials.new(name);m.diffuse_color=(*color,1);return m
# render_variant 0 colours: the generator does not know the per-case variant, so later variants differ slightly in body tint.
body=material('body',(.15,.43,.59));joint=material('joints',(.12,.25,.31));face=material('head',(.76,.69,.53));dark=material('eyes',(.035,.04,.045));floor=material('floor',(.37,.39,.42))
def ellipsoid(name,scale,mat):
 bpy.ops.mesh.primitive_uv_sphere_add(segments=24,ring_count=16);o=bpy.context.object;o.name=name;o.scale=scale;o.data.materials.append(mat)
 for f in o.data.polygons:f.use_smooth=True
 return o
def cube(name,p,scale,mat):
 bpy.ops.mesh.primitive_cube_add(size=1,location=p);o=bpy.context.object;o.name=name;o.scale=scale;o.data.materials.append(mat)
def between(o,a,b,r):
 # Same shape rule as render_inputs.limb: ellipsoid centred between two joints, long axis along the segment.
 o.location=(a+b)/2;o.scale=(r,r,(b-a).length/2+r*.35);o.rotation_euler=(b-a).to_track_quat('Z','Y').to_euler()
J=lambda f,k:Vector(f['joints'][k])
first=data['frames'][0]
if data['props'].get('chair'):
 # Chair under the planned starting pelvis, same proportions as the seated input scene; it stays put while the body moves.
 p=J(first,'pelvis');chair=material('chair',(.24,.25,.27));cube('seat',(p.x,p.y+.05,p.z-.08),(.54,.50,.08),chair);cube('back',(p.x,p.y+.28,p.z+.28),(.54,.06,.72),chair)
 for x in [-.22,.22]:
  for y in [-.14,.24]:cube('chair leg',(p.x+x,p.y+y,(p.z-.12)/2),(.045,.045,p.z-.12),chair)
BODY=data['props'].get('body') or {};CAM=data['props'].get('camera')
GIRTH={'slim':.85,'average':1.0,'muscular':1.15,'heavy':1.3}.get(BODY.get('build'),1.0)
HEIGHT=BODY.get('height_m') or 1.75;HEAD={'child':1.15,'teen':1.0}.get(BODY.get('age_group'),1.0)*(HEIGHT/1.75)**.3
G=lambda v:tuple(x*GIRTH for x in v)
parts={'pelvis':ellipsoid('pelvis',G((.19,.13,.15)),body),'torso':ellipsoid('torso',(1,1,1),body),'neck':ellipsoid('neck',(1,1,1),face),'head':ellipsoid('head',(.115*HEAD,.105*HEAD,.145*HEAD),face),
 'eyeL':ellipsoid('eye',(.014,.009,.017),dark),'eyeR':ellipsoid('eye',(.014,.009,.017),dark),'nose':ellipsoid('nose',(.021,.035,.024),face)}
SEGMENTS=[('hip','knee',.085),('knee','ankle',.064),('shoulder','elbow',.055),('elbow','wrist',.045)]
for s in 'LR':
 for a,b,_ in SEGMENTS:parts[s+a+b]=ellipsoid(s+a+b,(1,1,1),body)
 for p in ['shoulder','elbow','wrist','knee']:parts[s+p]=ellipsoid(s+p,(.058,.058,.058),joint)
 parts[s+'hand']=ellipsoid(s+'hand',(1,1,1),face);parts[s+'foot']=ellipsoid(s+'foot',(.075,.15,.054),joint)
cube('floor',(0,0,-.035),(200,200,.05),floor)
def framed(cam):
 # Fixed camera like the input shot: centred on the first frame's pelvis, cropped to the framing, high enough to keep the tallest head.
 f0=data['frames'][0];p=J(f0,'pelvis');framing=cam.get('framing')
 # Keep raised hands in shot too (dev-007 smoke test: a chest-up frame cut off both hands of "만세").
 top=max(max(J(f,'head').z+.25*HEAD,J(f,'Lwrist').z+.15,J(f,'Rwrist').z+.15) for f in data['frames'])
 bottom={'full_body':-.05,'knees_up':(J(f0,'Lknee').z+J(f0,'Rknee').z)/2-.05,'waist_up':p.z-.02,'chest_up':(p.z+J(f0,'neck').z)/2}.get(framing,-.05)
 # A crop never narrower than a person's shoulders plus room: minimum shot heights per framing (3:4 portrait, width = 0.75 x height).
 top=max(top,bottom+{'chest_up':1.1,'waist_up':1.4,'knees_up':1.8}.get(framing,.6));a=math.radians(cam.get('yaw_deg') or 0);d=6.0
 # yaw 0 faces the character (which looks along -Y); positive yaw walks toward the character's own left (+X).
 loc=Vector((p.x+d*math.sin(a),p.y-d*math.cos(a),(top+bottom)/2));return loc,Vector((p.x,p.y,(top+bottom)/2)),(top-bottom)*1.05
if view=='input' and CAM:loc,target,scale=framed(CAM)
elif view=='input':loc,target,scale=Vector((-3.1,-5.5,2.6)),Vector((0,-.1,.92)),2.15
else:loc,target,scale=Vector((0,-6,1.0)),Vector((0,0,1.0)),2.15
bpy.ops.object.camera_add(location=loc);camera=bpy.context.object;camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.type='ORTHO';camera.data.ortho_scale=scale;scene.camera=camera
scene.render.engine='BLENDER_WORKBENCH';scene.display.shading.light='STUDIO';scene.display.shading.color_type='MATERIAL';scene.display.shading.show_shadows=True;scene.display.shading.show_cavity=True;scene.display.shading.background_type='WORLD';scene.world=bpy.data.worlds.new('World');scene.world.color=(.22,.24,.27)
scene.render.resolution_x=576;scene.render.resolution_y=768;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGB'
for n,f in enumerate(data['frames']):
 head=J(f,'head')
 parts['pelvis'].location=J(f,'pelvis');between(parts['torso'],J(f,'pelvis'),J(f,'neck'),.18*GIRTH);between(parts['neck'],J(f,'neck'),head,.06);parts['head'].location=head
 side=(J(f,'Lshoulder')-J(f,'Rshoulder'));side.z=0
 side=side.normalized() if side.length>1e-6 else Vector((1,0,0));fwd=side.cross(Vector((0,0,1)));yaw=math.atan2(fwd.x,-fwd.y)
 rot=lambda v:Vector((v.x*math.cos(yaw)-v.y*math.sin(yaw),v.x*math.sin(yaw)+v.y*math.cos(yaw),v.z))*HEAD
 parts['head'].rotation_euler=(0,0,yaw);parts['eyeL'].location=head+rot(Vector((.042,-.099,.025)));parts['eyeR'].location=head+rot(Vector((-.042,-.099,.025)));parts['nose'].location=head+rot(Vector((0,-.117,-.01)))
 for s in 'LR':
  for a,b,r in SEGMENTS:between(parts[s+a+b],J(f,s+a),J(f,s+b),r*GIRTH)
  for p in ['shoulder','elbow','wrist','knee']:parts[s+p].location=J(f,s+p)
  wrist=J(f,s+'wrist');forearm=(wrist-J(f,s+'elbow')).normalized()
  between(parts[s+'hand'],wrist,wrist+forearm*.09,.04);parts[s+'hand'].scale=(.045,.028,.075)
  parts[s+'foot'].location=J(f,s+'ankle')+Vector((0,-.07,-.062))
 scene.render.filepath=str(out/f'frame_{n:04d}.png');bpy.ops.render.render(write_still=True)
print('RENDERED',len(data['frames']))
