"""Blender-only: draw solved frames with the same procedural mannequin, camera and lighting as tools/render_inputs.py.
Usage: blender -b --factory-startup --python tools/render_reference_blender.py -- frames.json out_dir [input|front]
The input view matches the benchmark images; the front view (orthographic, from -Y) is only a verification aid for motions the input view hides."""
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
parts={'pelvis':ellipsoid('pelvis',(.19,.13,.15),body),'torso':ellipsoid('torso',(1,1,1),body),'neck':ellipsoid('neck',(1,1,1),face),'head':ellipsoid('head',(.115,.105,.145),face),
 'eyeL':ellipsoid('eye',(.014,.009,.017),dark),'eyeR':ellipsoid('eye',(.014,.009,.017),dark),'nose':ellipsoid('nose',(.021,.035,.024),face)}
SEGMENTS=[('hip','knee',.085),('knee','ankle',.064),('shoulder','elbow',.055),('elbow','wrist',.045)]
for s in 'LR':
 for a,b,_ in SEGMENTS:parts[s+a+b]=ellipsoid(s+a+b,(1,1,1),body)
 for p in ['shoulder','elbow','wrist','knee']:parts[s+p]=ellipsoid(s+p,(.058,.058,.058),joint)
 parts[s+'hand']=ellipsoid(s+'hand',(1,1,1),face);parts[s+'foot']=ellipsoid(s+'foot',(.075,.15,.054),joint)
cube('floor',(0,0,-.035),(200,200,.05),floor)
bpy.ops.object.camera_add(location=(-3.1,-5.5,2.6) if view=='input' else (0,-6,1.0));camera=bpy.context.object;target=Vector((0,-.1,.92)) if view=='input' else Vector((0,0,1.0));camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.type='ORTHO';camera.data.ortho_scale=2.15;scene.camera=camera
scene.render.engine='BLENDER_WORKBENCH';scene.display.shading.light='STUDIO';scene.display.shading.color_type='MATERIAL';scene.display.shading.show_shadows=True;scene.display.shading.show_cavity=True;scene.display.shading.background_type='WORLD';scene.world=bpy.data.worlds.new('World');scene.world.color=(.22,.24,.27)
scene.render.resolution_x=576;scene.render.resolution_y=768;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGB'
for n,f in enumerate(data['frames']):
 head=J(f,'head')
 parts['pelvis'].location=J(f,'pelvis');between(parts['torso'],J(f,'pelvis'),J(f,'neck'),.18);between(parts['neck'],J(f,'neck'),head,.06);parts['head'].location=head
 parts['eyeL'].location=head+Vector((.042,-.099,.025));parts['eyeR'].location=head+Vector((-.042,-.099,.025));parts['nose'].location=head+Vector((0,-.117,-.01))
 for s in 'LR':
  for a,b,r in SEGMENTS:between(parts[s+a+b],J(f,s+a),J(f,s+b),r)
  for p in ['shoulder','elbow','wrist','knee']:parts[s+p].location=J(f,s+p)
  wrist=J(f,s+'wrist');forearm=(wrist-J(f,s+'elbow')).normalized()
  between(parts[s+'hand'],wrist,wrist+forearm*.09,.04);parts[s+'hand'].scale=(.045,.028,.075)
  parts[s+'foot'].location=J(f,s+'ankle')+Vector((0,-.07,-.062))
 scene.render.filepath=str(out/f'frame_{n:04d}.png');bpy.ops.render.render(write_still=True)
print('RENDERED',len(data['frames']))
