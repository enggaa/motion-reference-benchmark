"""Development aid: re-run the current reference reviewer on already rendered references of a run without touching its ledger or gate files.
The motion summary is recomputed from frames.json with the current code. Output is a comparison file, not a gate decision.
Usage: python tools/rereview_offline.py runs/dev-004 out.json [model]"""
import json,sys,tempfile,shutil
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from motionbench.core import read,save
from motionbench.animate import motion_summary
from motionbench.planner import ClaudeCodeBackend
from motionbench.verify import review,VERIFIER_VERSION
def main(run,out,model='sonnet'):
 run=Path(run);backend=ClaudeCodeBackend(model);packets={p['paired_reference_group']:p for p in read(run/'generator_inputs.json') if p['paired_reference_group']};results={}
 for folder in sorted((run/'references').iterdir()):
  packet=packets[folder.name]
  for name,sub in (('initial',folder),('repaired',folder/'repaired')):
   if not (sub/'frames.json').is_file():continue
   with tempfile.TemporaryDirectory() as d:
    d=Path(d);t=read(sub/'telemetry.json');t['motion_summary']=motion_summary(read(sub/'frames.json')['frames'],t['fps']);save(d/'telemetry.json',t)
    for g in ('grid_input.png','grid_front.png'):shutil.copy(sub/g,d/g)
    verdict,tries=review(backend,packet['image'],packet['request'],packet['duration_s'],d)
   gate=read(folder/'gate_decision.json');old=next((s['verdict'] for s in gate['steps'] if s['step']==('review_initial' if name=='initial' else 'review_repaired')),None)
   results[f'{folder.name}/{name}']={'verifier':VERIFIER_VERSION,'verdict':verdict,'recorded_verdict':old,'recorded_version':gate.get('verifier_version'),'usage':[x.get('usage') for x in tries]}
   print(folder.name,name,'now',(verdict or {}).get('verdict'),'recorded',(old or {}).get('verdict'),flush=True)
 save(out,results)
if __name__=='__main__':main(*sys.argv[1:])
