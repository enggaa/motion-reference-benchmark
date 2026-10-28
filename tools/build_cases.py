"""Author benchmark v0.1 tasks. No model outputs or scores are generated."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
POSES=['standing','seated','leaning','crouched']
# Novelty is relative to the frozen seed dictionary, not a claim about LLM pretraining.
TASKS=[
 ('D01','development','known','standing','wave_right','오른손을 어깨 높이로 들어 몸 앞에서 두 번 왕복해 흔든 뒤 내려라.',6,['오른손','어깨 높이','몸 앞','두 번 왕복','내려라']),
 ('D02','development','known','seated','wave_left','앉은 자세를 유지하면서 왼손을 어깨 높이로 들어 한 번 왕복해 흔든 뒤 내려라.',6,['앉은 자세를 유지','왼손','어깨 높이','한 번 왕복','내려라']),
 ('D03','development','known','leaning','wave_right','기울어진 몸통 자세를 유지하면서 오른손을 몸 앞에서 한 번 왕복해 흔들어라.',6,['기울어진 몸통 자세를 유지','오른손','몸 앞','한 번 왕복']),
 ('D04','development','known','crouched','squat','현재 낮춘 자세에서 양 무릎을 펴며 일어나 똑바로 선 자세로 마쳐라.',6,['현재 낮춘 자세','양 무릎을 펴며','일어나','똑바로 선 자세']),
 ('D05','development','composed','standing','right_then_left','오른손을 한 번 왕복해 흔들고 내린 다음, 왼손을 한 번 왕복해 흔들고 내려라.',8,['오른손','한 번 왕복','내린 다음','왼손','내려라']),
 ('D06','development','composed','seated','left_then_right','앉은 자세를 유지하며 왼손을 한 번 왕복해 흔들고 내린 다음, 오른손을 한 번 왕복해 흔들고 내려라.',8,['앉은 자세를 유지','왼손','내린 다음','오른손','한 번 왕복']),
 ('D07','development','unseen','standing','overhead_stretch','양팔을 머리 위로 올려 1초간 유지한 뒤 양팔을 내려라.',6,['양팔','머리 위','1초간 유지','양팔을 내려라']),
 ('D08','development','unseen','leaning','hands_on_hips','기울어진 몸통을 똑바로 세운 뒤 양손을 각각 허리에 대고 멈춰라.',6,['몸통을 똑바로','세운 뒤','양손','각각 허리에','멈춰라']),
 ('C01','calibration','known','standing','wave_left','왼손을 몸 앞에서 한 번 왕복해 흔든 뒤 내려라.',6,['왼손','몸 앞','한 번 왕복','내려라']),
 ('C02','calibration','known','crouched','squat','낮춘 자세에서 일어나 양 무릎을 편 채 멈춰라.',6,['낮춘 자세','일어나','양 무릎을 편','멈춰라']),
 ('C03','calibration','unseen','seated','head_turn','앉은 자세를 유지하고 고개만 자신의 오른쪽으로 돌려 1초 유지한 뒤 정면으로 돌려라.',6,['앉은 자세를 유지','고개만','자신의 오른쪽','1초 유지','정면']),
 ('C04','calibration','unseen','leaning','palms_together','몸통의 기울기를 유지하며 두 손바닥을 가슴 앞에서 맞대고 멈춰라.',6,['몸통의 기울기를 유지','두 손바닥','가슴 앞','맞대고','멈춰라']),
]
for i,(novelty,pose) in enumerate((n,p) for n in ['known','composed','unseen'] for p in POSES):
 prefix={'standing':'선 자세에서','seated':'앉은 자세를 유지하며','leaning':'몸통의 기울기를 유지하며','crouched':'낮춘 자세를 유지하며'}[pose]
 if novelty=='known':
  family='wave_right' if i%2==0 else 'wave_left';hand='오른손' if family=='wave_right' else '왼손'
  prompt=f'{prefix} {hand}을 몸 앞에서 어깨 높이로 들어 세 번 왕복해 흔든 뒤 내려라.'
  clauses=[prefix,hand,'몸 앞','어깨 높이','세 번 왕복','내려라'];duration=8
 elif novelty=='composed':
  family='right_then_left_return';prompt=f'{prefix} 오른손을 한 번 왕복해 흔들고 완전히 내린 다음 왼손을 두 번 왕복해 흔들고 내려라.'
  clauses=[prefix,'오른손','한 번 왕복','완전히 내린 다음','왼손','두 번 왕복','내려라'];duration=10
 else:
  family='bow' if pose in ['standing','seated'] else 'cross_arms'
  if family=='bow':
   prompt=f'{prefix} 양팔을 몸 옆에 둔 채 상체를 앞으로 숙여 인사하고 1초 멈춘 뒤 처음의 몸통 자세로 돌아와라.'
   clauses=[prefix,'양팔을 몸 옆','상체를 앞으로 숙여','1초 멈춘','처음의 몸통 자세'];duration=8
  else:
   prompt=f'{prefix} 양팔을 가슴 앞에서 교차해 오른쪽 팔뚝이 위에 오게 하고 1초 유지한 뒤 양팔을 풀어라.'
   clauses=[prefix,'양팔을 가슴 앞','교차','오른쪽 팔뚝이 위','1초 유지','양팔을 풀어라'];duration=8
 TASKS.append((f'T{i+1:02d}','test',novelty,pose,family,prompt,duration,clauses))

def build():
 cases=[];contracts=[]
 for index,(cid,split,novelty,pose,family,prompt,duration,clauses) in enumerate(TASKS):
  cases.append({'id':cid,'split':split,'dictionary_relationship':novelty,'initial_pose':pose,'action_family':family,'variant_group':f'{split}-{family}-{pose}','actor_group':split+'-procedural-mannequin','request':prompt,'duration_s':duration,'image':f'images/{cid}.png','image_sha256':None,'render_variant':index,'initial_state_policy':'Infer initial pose from the supplied image; do not reset to T-pose or standing. Ground-truth pose files are evaluator-only.','novelty_definition':'relative to seed_dictionary.json, not unseen in model pretraining','input_type':'procedurally authored synthetic mannequin image'})
  requirements=[{'id':f'R{j+1}','quote':quote,'criterion':f'영상에서 다음 명시 요구를 충족: {quote}','mandatory':True} for j,quote in enumerate(clauses)]
  contracts.append({'case_id':cid,'requirements':requirements,'shared_requirements':[{'id':'S1','criterion':'첫 동작 이전에 입력 자세를 다른 자세로 순간 초기화하지 않는다.','mandatory':True},{'id':'S2','criterion':'지정하지 않은 신체 좌우로 행동을 바꾸지 않는다.','mandatory':True}],'ambiguity_policy':'If viewpoint or occlusion prevents a decision, mark uncertain; do not infer a pass.','completion_policy':'The required terminal state must be visible before the clip ends.'})
 (ROOT/'benchmark/cases.json').write_text(json.dumps(cases,indent=2,ensure_ascii=False),encoding='utf-8')
 (ROOT/'benchmark/evaluator/contracts.json').write_text(json.dumps(contracts,indent=2,ensure_ascii=False),encoding='utf-8')
 dictionary={'version':'seed-v0.1','actions':['wave_right','wave_left','squat'],'semantics':['raise-wave-lower','lower-pelvis-bend-knees-return'],'scope':'Semantic inventory only. Reference trajectory files must be supplied separately with their own license and provenance.','disallowed_test_families':['bow','cross_arms'],'training_policy':'Do not insert test action solutions, captions, poses, generated outputs or evaluator contracts into retrieval, finetuning or repair prompts.'}
 (ROOT/'benchmark/seed_dictionary.json').write_text(json.dumps(dictionary,indent=2),encoding='utf-8')
 print('Authored',len(cases),'cases. Image hashes populated by render_inputs.py.')
if __name__=='__main__':build()
