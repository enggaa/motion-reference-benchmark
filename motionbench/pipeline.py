"""Run every reference stage for a run in order: plan (with pose fit), render and register the shared reference, gate condition C.
Each stage keeps its own records and failure stage; a group that fails a stage simply stops there."""
from pathlib import Path
from .core import read
from .planner import plan_run
from .reference import render_group,find_blender
from .verify import verify_group
def run_pipeline(run,backend,pose_fit=True,max_groups=8,blender=None):
 blender=blender or find_blender();result={'plan':plan_run(run,backend,max_groups,pose_fit=blender if pose_fit else None),'groups':{}}
 rows={r['attempt_id']:r for r in read(Path(run)/'ledger.json')}
 for p in read(Path(run)/'generator_inputs.json'):
  gid=p['paired_reference_group']
  if not gid or gid in result['groups'] or not (Path(run)/'plans'/gid/'plan.json').is_file():continue
  entry=result['groups'][gid]={}
  if 'reference_initial' not in rows[p['attempt_id']]['outputs']:
   r=render_group(run,gid,blender,register=True);entry['first_frame_match']=r['first_frame_match']
  g=verify_group(run,gid,backend,blender);entry['gate']=g.get('decision',g.get('skipped'));entry['reference_for_final']=g.get('reference_for_final')
 return result
