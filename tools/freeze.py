"""Hash the benchmark assets. Re-freezing requires an intentional version change."""
import json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
files=[ROOT/'benchmark/cases.json',ROOT/'benchmark/seed_dictionary.json',*sorted((ROOT/'benchmark/evaluator').glob('*.json')),*sorted((ROOT/'benchmark/images').glob('*.png'))]
for p in files:
 if p.suffix=='.json':p.write_bytes(p.read_bytes().replace(b'\r\n',b'\n'))
manifest={'version':'0.1.0','created_date_kst':'2026-10-29','state':'authored_not_model_evaluated','files':{p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
(ROOT/'benchmark/freeze.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print('Frozen',len(files),'files')
