"""Diagnostic full-body KIT joint replay on the saved MakeHuman character.

This is source replay, not an LLM-generated motion. It bypasses the six-control
compiler and fixed-foot retargeter. Axial hand rotations and fingers are absent
from KIT21 and remain inherited from the character's rest rig.
"""
import argparse, hashlib, json, math, sys
from pathlib import Path
import bpy
import numpy as np
from mathutils import Vector, Matrix, Quaternion

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--clip', default='00651')
p.add_argument('--source-joints',type=Path,required=True)
p.add_argument('--plane-orientation',action='store_true')
p.add_argument('--continuous-limbs',action='store_true')
p.add_argument('--preserve-volume',action='store_true')
p.add_argument('--preserve-initial-torso',action='store_true')
p.add_argument('--chest-clavicle',action='store_true')
p.add_argument('--shoulder-distribution',action='store_true')
p.add_argument('--render-mode',choices=['preview','video','none'],default='preview')
p.add_argument('--out', required=True, type=Path)
p.add_argument('--scene', type=Path, required=True)
a = p.parse_args(sys.argv[sys.argv.index('--')+1:])
assert not (a.continuous_limbs and a.plane_orientation), 'Choose one orientation policy'
assert a.clip.isdigit() or (a.clip.startswith('M') and a.clip[1:].isdigit())
out = a.out.resolve(); out.mkdir(parents=True, exist_ok=False)
source = a.source_joints.resolve()
raw = np.load(source, allow_pickle=False).astype(float)
assert raw.ndim == 3 and raw.shape[1:] == (21, 3) and np.isfinite(raw).all()
original = np.stack([-raw[:,:,0], -raw[:,:,2], raw[:,:,1]], axis=2)
# Source samples are retained at every other 25 fps frame. No endpoint padding.
times = np.arange(2*len(raw)-1)/25
src_times = np.arange(len(raw))/12.5
motion = np.stack([np.interp(times, src_times, original[:,j,c]) for j in range(21) for c in range(3)], axis=1).reshape(-1,21,3)
np.testing.assert_allclose(motion[::2], original, atol=1e-9)
bpy.ops.wm.open_mainfile(filepath=str(a.scene.resolve()))
scene = bpy.context.scene; rig = bpy.data.objects['AdultMale_Rig']; face = bpy.data.objects['FACE_CONTROLS']
if a.preserve_volume:
    for obj in bpy.data.objects:
        for modifier in obj.modifiers:
            if modifier.type=='ARMATURE' and modifier.object==rig:
                modifier.use_deform_preserve_volume=True
if rig.animation_data: rig.animation_data.action = None
face.animation_data_clear()
for name in ['smile','frown','jaw_open','blink_left','blink_right','brow_raise','brow_frown','gaze_x','gaze_y']:
    face[name] = 0
rest = {b.name:b.matrix_local.copy() for b in rig.data.bones}
for pb in rig.pose.bones:
    if not pb.name.startswith('eye.'):
        pb.matrix_basis = Matrix.Identity(4); pb.rotation_mode = 'QUATERNION'

def head(name): return rig.data.bones[name].head_local.copy()
def delta(u,v):
    assert u.length > 1e-8 and v.length > 1e-8
    return u.normalized().rotation_difference(v.normalized())
transport_state={}
transport_events=[]
def continuous_delta(key,rest_direction,desired):
    unit=desired.normalized()
    if key not in transport_state:
        rotation=delta(rest_direction,desired)
    else:
        previous_direction,previous_rotation=transport_state[key]
        step=previous_direction.rotation_difference(unit)
        rotation=step@previous_rotation
        rotation.normalize()
        transport_events.append({'key':key,'direction_step_degrees':math.degrees(previous_direction.angle(unit)),
                                 'orientation_step_degrees':math.degrees(previous_rotation.rotation_difference(rotation).angle)})
    transport_state[key]=(unit.copy(),rotation.copy())
    return rotation

def body_frame(up, across):
    z = up.normalized(); x = (across-z*across.dot(z)).normalized(); y = z.cross(x).normalized()
    assert x.length > .9
    return Matrix((x,y,z)).transposed().to_quaternion()

# MMM named joint order: 5=LS, 8=RS, 11=LH, 16=RH.
# The cached KIT coordinates require a reflected X conversion to agree with
# MakeHuman anatomical sides AND toe-forward direction. Record this explicitly.
arm_map={'L':(5,6,7),'R':(8,9,10)}
leg_map={'L':(11,12,13,14,15),'R':(16,17,18,19,20)}
across=Vector(original[0,11]-original[0,16]);across.z=0
if across.length<1e-6: raise ValueError('Initial hip heading is ambiguous')
across.normalize();z=Vector((0,0,1))
heading=Matrix((across,z.cross(across),z)).transposed()
motion=np.array([[heading.inverted()@Vector(v) for v in ps] for ps in motion])

def segment_frame(direction,normal):
    y=direction.normalized()
    z=normal-y*normal.dot(y)
    if z.length<1e-6: raise ValueError('Degenerate limb plane')
    z.normalize();x=y.cross(z).normalized()
    return Matrix((x,y,z)).transposed()

previous_normals={}
plane_fallbacks=0
def limb_rotations(side,upper,lower):
    global plane_fallbacks
    ru=head('lowerarm01.'+side)-head('upperarm01.'+side)
    rl=head('wrist.'+side)-head('lowerarm01.'+side)
    rest_normal=ru.cross(rl).normalized()
    normal=upper.normalized().cross(lower.normalized())
    if normal.length<.05:
        plane_fallbacks+=1
        normal=previous_normals.get(side,delta(ru,upper)@rest_normal)
    else:
        normal.normalize()
    previous_normals[side]=normal.copy()
    return ((segment_frame(upper,normal)@segment_frame(ru,rest_normal).transposed()).to_quaternion(),
            (segment_frame(lower,normal)@segment_frame(rl,rest_normal).transposed()).to_quaternion())
ratios=[]
for side,(hip,knee,ankle,_,__) in leg_map.items():
    ratios += [(head('lowerleg01.'+side)-head('upperleg01.'+side)).length/np.median(np.linalg.norm(motion[:,knee]-motion[:,hip],axis=1)),
               (head('foot.'+side)-head('lowerleg01.'+side)).length/np.median(np.linalg.norm(motion[:,ankle]-motion[:,knee],axis=1))]
scale=float(np.median(ratios)); origin=motion[0,0].copy()
motion = (motion-origin)*scale
pose_frames=[]; min_foot=1e9; direction_errors=[]; target_points=[]; axis_reference=None
for ps in motion:
    points=[Vector(v) for v in ps]; rotations={}
    hip_across=points[leg_map['L'][0]]-points[leg_map['R'][0]]
    chest_across=points[arm_map['L'][0]]-points[arm_map['R'][0]]
    rotations['root']=body_frame(points[1]-points[0], hip_across)
    for names,vector,lateral in [(['spine05','spine04'],points[1]-points[0],hip_across),
                                 (['spine03','spine02','spine01'],points[2]-points[1],chest_across),
                                 (['neck01','neck02','neck03'],points[3]-points[2],chest_across),
                                 (['head'],points[4]-points[3],chest_across)]:
        for name in names: rotations[name]=body_frame(vector,lateral)
    for side,(shoulder,elbow,wrist) in arm_map.items():
        # Source shoulder displacement relative to upper torso controls clavicle.
        ref=head('upperarm01.'+side)-head('neck01')
        clavicle=delta(ref,points[shoulder]-points[3])
        for name in ['clavicle','shoulder01']: rotations[name+'.'+side]=clavicle
        upper=delta(head('lowerarm01.'+side)-head('upperarm01.'+side),points[elbow]-points[shoulder])
        lower=delta(head('wrist.'+side)-head('lowerarm01.'+side),points[wrist]-points[elbow])
        if a.continuous_limbs:
            upper=continuous_delta('upperarm.'+side,head('lowerarm01.'+side)-head('upperarm01.'+side),points[elbow]-points[shoulder])
            lower=continuous_delta('lowerarm.'+side,head('wrist.'+side)-head('lowerarm01.'+side),points[wrist]-points[elbow])
        if a.plane_orientation:
            upper,lower=limb_rotations(side,points[elbow]-points[shoulder],points[wrist]-points[elbow])
        for name in ['upperarm01','upperarm02']: rotations[name+'.'+side]=upper
        for name in ['lowerarm01','lowerarm02','wrist']: rotations[name+'.'+side]=lower
    for side,(hip,knee,ankle,mid,toe) in leg_map.items():
        upper=delta(head('lowerleg01.'+side)-head('upperleg01.'+side),points[knee]-points[hip])
        lower=delta(head('foot.'+side)-head('lowerleg01.'+side),points[ankle]-points[knee])
        if a.continuous_limbs:
            upper=continuous_delta('upperleg.'+side,head('lowerleg01.'+side)-head('upperleg01.'+side),points[knee]-points[hip])
            lower=continuous_delta('lowerleg.'+side,head('foot.'+side)-head('lowerleg01.'+side),points[ankle]-points[knee])
        for name in ['upperleg01','upperleg02']: rotations[name+'.'+side]=upper
        for name in ['lowerleg01','lowerleg02']: rotations[name+'.'+side]=lower
        rotations['foot.'+side]=delta(head('toe1-1.'+side)-head('foot.'+side),points[toe]-points[ankle])
    # Source neck/head joint offsets are not MakeHuman bone axes. Align the
    # initial torso/head/clavicle frames to target rest, then preserve changes.
    # Limb segment directions remain absolute; this is a stated calibration
    # assumption, not evidence that the initial source frame is truly neutral.
    calibrated=[n for n in rotations if n=='root' or n.startswith(('spine','neck','head','clavicle','shoulder'))]
    if axis_reference is None: axis_reference={n:rotations[n].copy() for n in calibrated}
    for n in calibrated:
        if a.preserve_initial_torso and (n=='root' or n.startswith(('spine','neck','head'))):
            # Source body-frame orientation is already relative to canonical world axes.
            # Preserve initial tilt rather than removing it with the first source frame.
            continue
        rotations[n]=rotations[n]@axis_reference[n].inverted()
    if a.chest_clavicle:
        for side in ['L','R']:
            for prefix in ['clavicle','shoulder01']:
                rotations[prefix+'.'+side]=rotations['spine01'].copy()
    if a.shoulder_distribution:
        for side in ['L','R']:
            chest=rotations['spine01'];upper=rotations['upperarm01.'+side]
            rotations['clavicle.'+side]=chest.slerp(upper,.20)
            rotations['shoulder01.'+side]=chest.slerp(upper,.40)
    poses={}
    for bone in rig.data.bones:
        name=bone.name; local=rest[bone.parent.name].inverted()@rest[name] if bone.parent else rest[name]
        parent=poses[bone.parent.name] if bone.parent else Matrix.Identity(4)
        current=parent@local
        if name=='root': current.translation += points[0]
        if name in rotations:
            mat=(rotations[name]@rest[name].to_quaternion()).to_matrix().to_4x4()
            mat.translation=current.translation; current=mat
        poses[name]=current
    for side in ['L','R']:
        min_foot=min(min_foot,poses['foot.'+side].translation.z,poses['toe1-1.'+side].translation.z)
    pose_frames.append(poses)

# One constant floor offset; no per-frame foot locking or invented body motion.
floor_offset=.035-min_foot
scene.render.fps=25; scene.render.fps_base=1; scene.frame_start=1; scene.frame_end=len(motion)
previous={}; max_bone_error=0
for i,poses in enumerate(pose_frames,1):
    scene.frame_set(i)
    for bone in rig.data.bones:
        name=bone.name
        if name.startswith('eye.'): continue
        pb=rig.pose.bones[name]
        local=rest[bone.parent.name].inverted()@rest[name] if bone.parent else rest[name]
        parent=poses[bone.parent.name] if bone.parent else Matrix.Identity(4)
        current=poses[name].copy()
        if name=='root': current.translation.z+=floor_offset
        pb.matrix_basis=local.inverted()@parent.inverted()@current
        # Hemisphere continuity avoids quaternion sign flips between samples.
        if name in previous and pb.rotation_quaternion.dot(previous[name])<0:
            pb.rotation_quaternion.negate()
        previous[name]=pb.rotation_quaternion.copy()
        pb.keyframe_insert(data_path='location',frame=i);pb.keyframe_insert(data_path='rotation_quaternion',frame=i)
    bpy.context.view_layer.update()
    mapped=[]
    for side,(s,e,w) in arm_map.items():
        for first,last,u,v in [('upperarm01','lowerarm01',s,e),('lowerarm01','wrist',e,w)]:
            actual=rig.pose.bones[last+'.'+side].head-rig.pose.bones[first+'.'+side].head
            desired=Vector(motion[i-1,v]-motion[i-1,u])
            direction_errors.append(math.degrees(actual.angle(desired)))
    for bone in rig.data.bones:
        max_bone_error=max(max_bone_error,abs(rig.pose.bones[bone.name].length-bone.length))
    target_points.append({n:list(rig.pose.bones[n].head) for n in ['root','head','foot.L','foot.R','wrist.L','wrist.R']})
for fc in rig.animation_data.action.fcurves:
    for key in fc.keyframe_points: key.interpolation='LINEAR'
assert max_bone_error<1e-5 and max(direction_errors)<.15, (max_bone_error,max(direction_errors))
validation={'source_clip':a.clip,'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
            'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'source_frames':len(raw),'source_fps':12.5,'frames':len(motion),'fps':25,
            'source_representation':'C3D proxy trajectories or explicitly logged sequential composition; see plan.json', 'source_samples_preserved_before_rig_projection':True,'scale':scale,'constant_floor_offset':floor_offset,
            'arm_map':arm_map,'leg_map':leg_map,'max_arm_direction_error_deg':max(direction_errors),
            'max_bone_length_error':max_bone_error,'new_llm_generation':False,
            'continuous_limb_orientation':a.continuous_limbs,'retarget_v2':{'explicit_anatomical_map':True,'elbow_plane_orientation':a.plane_orientation,
                           'preserve_volume':a.preserve_volume,'preserve_initial_torso':a.preserve_initial_torso,
                           'chest_clavicle':a.chest_clavicle,'axis_conversion':'C3D xyz stored as xzy, then mapped to -x,-y,z; marker labels define sides',
                           'shoulder_distribution':a.shoulder_distribution,'shoulder_distribution_policy':'authored slerp 0.20 clavicle / 0.40 shoulder, not observed scapula motion',
                           'plane_fallback_count':plane_fallbacks},
            'axis_calibration':('Initial torso tilt retained; clavicle still first-frame calibrated.' if a.preserve_initial_torso else 'Initial torso/head/clavicle mapped to target rest.'),
            'limitations':['Joint positions do not determine axial wrist rotation or fingers.','Retargeted lengths follow the target character; positions differ from source.','No contact solver or dynamic balance validation.','Neutral face: the source has no facial observations.','The short source clip need not start/end neutral.']}
(out/'transport_events.json').write_text(json.dumps(transport_events,indent=2),encoding='utf-8')
(out/'validation.json').write_text(json.dumps(validation,indent=2),encoding='utf-8')
(out/'source_trajectory.json').write_text(json.dumps({'times_seconds':times.tolist(),'positions':motion.tolist()},indent=2),encoding='utf-8')
(out/'target_points.json').write_text(json.dumps(target_points),encoding='utf-8')
scene.frame_set(1);bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(out/'source_motion.blend'))

if a.render_mode=='none':
    print('BUILD_ONLY_DONE');sys.exit(0)
# Fast source-motion diagnostic; material-color Workbench, not final-quality render.
import subprocess, shutil
scene.render.engine='BLENDER_WORKBENCH'
scene.display.shading.light='STUDIO'
scene.display.shading.color_type='MATERIAL'
scene.display.shading.show_shadows=True
scene.display.shading.show_cavity=True
scene.render.resolution_x=480; scene.render.resolution_y=600; scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG'
# Follow horizontal root translation; preserve vertical body drop in the view.
camera_origin=scene.camera.location.copy()
root_origin=Vector(target_points[0]['root'])
frames_dir=out/'frames';frames_dir.mkdir()
render_frames=range(1,len(motion)+1) if a.render_mode=='video' else [1,2*(len(raw)//2)+1,len(motion)]
for index, frame in enumerate(render_frames,1):
    scene.frame_set(frame)
    shift=Vector(target_points[frame-1]['root'])-root_origin
    scene.camera.location=camera_origin+Vector((shift.x,shift.y,0))
    scene.render.filepath=str(frames_dir/f'{index:04d}.png')
    bpy.ops.render.render(write_still=True)
if a.render_mode=='preview':
    print('PREVIEW_READY '+str(out));sys.exit(0)
ffmpeg=shutil.which('ffmpeg')
if not ffmpeg: raise RuntimeError('ffmpeg unavailable')
subprocess.run([ffmpeg,'-hide_banner','-loglevel','error','-n','-framerate','25','-i',str(frames_dir/'%04d.png'),
                '-c:v','libx264','-crf','20','-pix_fmt','yuv420p','-movflags','+faststart',str(out/'source_replay.mp4')],check=True)
validation['preview']={'engine':'WORKBENCH','fps':25,'rendered_frames':len(motion),'horizontal_camera_follow':True,
                       'meaning':'Source replay, not trained-model output or independent visual approval.'}
(out/'validation.json').write_text(json.dumps(validation,indent=2),encoding='utf-8')
print('VIDEO_READY '+str(out/'source_replay.mp4'))
