"""Blender-only procedural assets, independent of KIT/LAFAN/MakeHuman assets."""
import bpy,json,math,hashlib
from pathlib import Path
from mathutils import Vector,Matrix
ROOT=Path(__file__).resolve().parents[1]
cases=json.loads((ROOT/'benchmark/cases.json').read_text(encoding='utf-8'))
def material(name,color):
 m=bpy.data.materials.new(name);m.diffuse_color=(*color,1);return m
def ellipsoid(name,p,scale,mat):
 bpy.ops.mesh.primitive_uv_sphere_add(segments=24,ring_count=16,location=p);o=bpy.context.object;o.name=name;o.scale=scale;o.data.materials.append(mat)
 for f in o.data.polygons:f.use_smooth=True
 return o
def limb(name,a,b,r,mat):
 a=Vector(a);b=Vector(b);o=ellipsoid(name,(a+b)/2,(r,r,(b-a).length/2+r*.35),mat);o.rotation_euler=(b-a).to_track_quat('Z','Y').to_euler()
def cube(name,p,scale,mat):
 bpy.ops.mesh.primitive_cube_add(size=1,location=p);o=bpy.context.object;o.name=name;o.scale=scale;o.data.materials.append(mat)
for case in cases:
 bpy.ops.wm.read_factory_settings(use_empty=True);scene=bpy.context.scene
 idx=case['render_variant'];pose=case['initial_pose'];body=material('body',(.15+.004*idx,.43+.009*(idx%4),.59));joint=material('joints',(.12,.25,.31));face=material('head',(.76,.69,.53));dark=material('eyes',(.035,.04,.045));floor=material('floor',(.37,.39,.42))
 pelvis=Vector((0,0,.99));neck=Vector((0,0,1.48));head=Vector((0,-.015,1.69))
 pts={'pelvis':pelvis,'neck':neck,'head':head}
 for side,sign in [('L',1),('R',-1)]:
  pts.update({side+'hip':Vector((sign*.12,0,.98)),side+'knee':Vector((sign*.13,-.015,.55)),side+'ankle':Vector((sign*.14,0,.12)),side+'shoulder':Vector((sign*.23,0,1.43)),side+'elbow':Vector((sign*.31,-.01,1.17)),side+'wrist':Vector((sign*.35,-.07,.96))})
 if pose=='seated':
  for name in ['pelvis','neck','head']+[s+p for s in ['L','R'] for p in ['shoulder','elbow','wrist']]:pts[name].z-=.36
  for s,sign in [('L',1),('R',-1)]:
   pts[s+'hip']=Vector((sign*.12,0,.62));pts[s+'knee']=Vector((sign*.16,-.40,.58));pts[s+'ankle']=Vector((sign*.16,-.44,.12));pts[s+'elbow']=Vector((sign*.30,-.04,.83));pts[s+'wrist']=Vector((sign*.22,-.29,.77))
  chair=material('chair',(.24,.25,.27));cube('seat',(0,.05,.55),(.54,.50,.08),chair);cube('back',(0,.28,.91),(.54,.06,.72),chair)
  for x in [-.22,.22]:
   for y in [-.14,.24]:cube('chair leg',(x,y,.26),(.045,.045,.52),chair)
 if pose=='crouched':
  pts['pelvis']=Vector((0,.10,.59));pts['neck']=Vector((0,-.16,1.05));pts['head']=Vector((0,-.24,1.25))
  for s,sign in [('L',1),('R',-1)]:
   pts[s+'hip']=Vector((sign*.12,.10,.59));pts[s+'knee']=Vector((sign*.18,-.32,.43));pts[s+'ankle']=Vector((sign*.18,0,.12));pts[s+'shoulder']=Vector((sign*.23,-.13,1.01));pts[s+'elbow']=Vector((sign*.28,-.37,.92));pts[s+'wrist']=Vector((sign*.25,-.60,.92))
 if pose=='leaning':
  pivot=pts['pelvis'].copy();rotation=Matrix.Rotation(math.radians(18),3,'Y')
  for name in ['neck','head']+[s+p for s in ['L','R'] for p in ['shoulder','elbow','wrist']]:pts[name]=pivot+rotation@(pts[name]-pivot)
 ellipsoid('pelvis',pts['pelvis'],(.19,.13,.15),body);limb('torso',pts['pelvis'],pts['neck'],.18,body);limb('neck',pts['neck'],pts['head'],.06,face);ellipsoid('head',pts['head'],(.115,.105,.145),face)
 for x in [-.042,.042]:ellipsoid('eye',pts['head']+Vector((x,-.099,.025)),(.014,.009,.017),dark)
 ellipsoid('nose',pts['head']+Vector((0,-.117,-.01)),(.021,.035,.024),face)
 for s in ['L','R']:
  for a,b,radius in [('hip','knee',.085),('knee','ankle',.064),('shoulder','elbow',.055),('elbow','wrist',.045)]:limb(s+a+b,pts[s+a],pts[s+b],radius,body)
  for p in ['shoulder','elbow','wrist','knee']:ellipsoid(s+p,pts[s+p],(.058,.058,.058),joint)
  ellipsoid(s+'hand',pts[s+'wrist']+Vector((0,-.015,-.045)),(.045,.028,.075),face)
  ellipsoid(s+'foot',pts[s+'ankle']+Vector((0,-.07,-.062)),(.075,.15,.054),joint)
 cube('floor',(0,0,-.035),(200,200,.05),floor)
 bpy.ops.object.camera_add(location=(-3.1,-5.5,2.6));camera=bpy.context.object;target=Vector((0,-.1,.92));camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.type='ORTHO';camera.data.ortho_scale=2.15;scene.camera=camera
 scene.render.engine='BLENDER_WORKBENCH';scene.display.shading.light='STUDIO';scene.display.shading.color_type='MATERIAL';scene.display.shading.show_shadows=True;scene.display.shading.show_cavity=True;scene.display.shading.background_type='WORLD';scene.world=bpy.data.worlds.new('World');scene.world.color=(.22,.24,.27)
 scene.render.resolution_x=576;scene.render.resolution_y=768;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG';path=ROOT/'benchmark'/case['image'];scene.render.filepath=str(path);bpy.ops.render.render(write_still=True)
 case['image_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
 truth={'case_id':case['id'],'coordinate_convention':'left +X, front -Y, up +Z; authored scene units','joints':{k:list(v) for k,v in pts.items()},'source':'procedurally authored, not measured motion capture','visibility':'evaluator only; not a generator input'}
 (ROOT/'benchmark/evaluator'/f"{case['id']}_initial_pose.json").write_text(json.dumps(truth,indent=2),encoding='utf-8')
(ROOT/'benchmark/cases.json').write_text(json.dumps(cases,indent=2,ensure_ascii=False),encoding='utf-8')
print('RENDERED',len(cases))
