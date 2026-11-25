"""Author benchmark v0.2 tasks: eight AI-generated images of fictional people, each given several everyday action requests.
No model outputs or scores are generated. Image files are copied into benchmark/images/ before running this script."""
import hashlib, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

# One image per person; every image shows a different fictional person (sex, height, age, build differ),
# and the four images of a split cover the four initial poses, four viewpoints and four framings.
IMAGES = {
 'D1': ('development', 'standing', 'front', 'chest_up', 'tall man, 30s, muscular'),
 'D2': ('development', 'seated', 'right_three_quarter', 'knees_up', 'short girl, child'),
 'D3': ('development', 'leaning', 'left_three_quarter', 'waist_up_one_arm_cropped', 'tall woman, 30s, slim'),
 'D4': ('development', 'crouched', 'side', 'full_body', 'short boy, child'),
 'T1': ('test', 'standing', 'left_three_quarter', 'chest_up', 'short girl, child'),
 'T2': ('test', 'seated', 'side', 'knees_up', 'tall man, 50s-60s, heavy build'),
 'T3': ('test', 'leaning', 'front', 'waist_up_one_arm_cropped', 'short boy, teenager'),
 'T4': ('test', 'crouched', 'right_three_quarter', 'full_body', 'tall woman, 30s-40s, muscular'),
}

# Everyday requests as a person would type them. Families are relative to seed_dictionary.json
# (wave, squat); "인사해" may be met by a wave or a bow, "일어나" is the squat's rise.
TASKS = [
 ('D01', 'D1', '만세 해', 'hands_up'), ('D02', 'D1', '기지개 켜', 'stretch'),
 ('D03', 'D2', '브이 해', 'v_sign'), ('D04', 'D2', '하품해', 'yawn'),
 ('D05', 'D3', '춤 춰', 'dance'), ('D06', 'D3', '돌아봐', 'look_back'),
 ('D07', 'D4', '만세 해', 'hands_up'), ('D08', 'D4', '브이 해', 'v_sign'),
 ('T01', 'T1', '인사해', 'greet'), ('T02', 'T1', '박수 쳐', 'clap'), ('T03', 'T1', '팔짱 껴', 'cross_arms'),
 ('T04', 'T2', '일어나', 'stand_up'), ('T05', 'T2', '인사해', 'greet'), ('T06', 'T2', '박수 쳐', 'clap'),
 ('T07', 'T3', '인사해', 'greet'), ('T08', 'T3', '경례해', 'salute'), ('T09', 'T3', '뒤돌아', 'turn_around'),
 ('T10', 'T4', '일어나', 'stand_up'), ('T11', 'T4', '점프해', 'jump'), ('T12', 'T4', '팔짱 껴', 'cross_arms'),
]
KNOWN = {'greet', 'stand_up'}

# What counts as doing the action (pass) and typical failures. Written before any model output exists.
CRITERIA = {
 'greet': ('손을 흔들거나, 고개나 상체를 숙이는 것 중 하나', '손을 들기만 하고 멈춤, 고개만 살짝 까딱임'),
 'clap': ('두 손바닥을 마주치는 동작이 2번 이상', '손을 모으기만 함, 한 번만 닿음'),
 'cross_arms': ('두 팔을 가슴 앞에서 엇갈려 끼고 멈춤', '팔을 겹치다 맒, 한 팔만 올림'),
 'stand_up': ('앉거나 쪼그린 상태에서 서 있는 자세까지 완료', '엉덩이만 들썩임, 중간에 멈춤'),
 'salute': ('한 손을 이마나 눈썹 옆에 대는 동작', '손을 머리 근처로 들다 맒'),
 'turn_around': ('몸 전체가 카메라 반대쪽을 향할 때까지 회전', '고개만 돌림, 반쯤만 돎'),
 'jump': ('두 발이 바닥에서 떨어지는 장면이 보임', '무릎만 굽혔다 폄'),
 'hands_up': ('두 팔을 머리 위로 올림', '한 팔만 올림, 어깨 높이에서 멈춤'),
 'stretch': ('팔을 위나 옆으로 뻗으며 몸을 늘임', '팔을 조금만 움직임'),
 'v_sign': ('손가락 두 개를 펴서 브이 모양을 보임', '손만 들고 모양이 안 보임'),
 'yawn': ('입을 크게 벌리는 하품 동작', '입만 살짝 벌림'),
 'dance': ('몸을 리듬 있게 반복해서 움직임', '한두 번 흔들고 멈춤'),
 'look_back': ('상체를 옆이나 뒤로 돌려 바라봄 (상체 회전이 반드시 있어야 함)', '고개만 돌림, 눈만 움직임'),
}
COMMON = [
 '요청한 행동이 영상 안에서 눈에 보이게 시작해서 끝나야 성공이다.',
 '거의 움직이지 않거나 숨 쉬는 정도의 움직임만 있으면 실패다.',
 '행동하는 부위가 화면 밖에 있다가 끝까지 들어오지 않으면 실패다.',
 '다른 행동을 하면 실패다.',
 '가려지거나 각도 때문에 판단할 수 없을 때만 판단 불가(uncertain)다.',
]
TEST_ONLY = sorted({f for _, img, _, f in TASKS if IMAGES[img][0] == 'test' and f not in KNOWN})

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def build():
 cases, contracts = [], []
 for cid, img, request, family in TASKS:
  split, pose, view, framing, subject = IMAGES[img]
  path = ROOT / 'benchmark/images' / f'{img}.png'
  cases.append({'id': cid, 'split': split, 'dictionary_relationship': 'known' if family in KNOWN else 'unseen',
   'initial_pose': pose, 'view': view, 'framing': framing, 'subject': subject, 'action_family': family,
   'variant_group': f'image-{img}', 'actor_group': f'{split}-{img}', 'request': request, 'duration_s': 6,
   'image': f'images/{img}.png', 'image_sha256': sha(path),
   'initial_state_policy': 'Infer the starting pose from the supplied image; do not reset to T-pose or standing.',
   'novelty_definition': 'relative to seed_dictionary.json, not unseen in model pretraining',
   'input_type': 'AI-generated photorealistic image of a fictional person (OpenAI image generation, 2026-11)'})
  ok, fail = CRITERIA[family]
  contracts.append({'case_id': cid,
   'requirements': [{'id': 'R1', 'quote': request, 'criterion': f'성공: {ok}. 실패 예: {fail}.', 'mandatory': True}],
   'shared_requirements': [{'id': 'S1', 'criterion': '첫 동작 이전에 입력 자세를 다른 자세로 순간 초기화하지 않는다.', 'mandatory': True}],
   'common_policy': COMMON,
   'ambiguity_policy': 'If viewpoint or occlusion prevents a decision, mark uncertain; do not infer a pass.',
   'completion_policy': 'The required action must be visibly completed before the clip ends.'})
 (ROOT / 'benchmark/cases.json').write_text(json.dumps(cases, indent=2, ensure_ascii=False), encoding='utf-8')
 (ROOT / 'benchmark/evaluator/contracts.json').write_text(json.dumps(contracts, indent=2, ensure_ascii=False), encoding='utf-8')
 dictionary = {'version': 'seed-v0.2', 'actions': ['wave_right', 'wave_left', 'squat'],
  'semantics': ['raise-wave-lower', 'lower-pelvis-bend-knees-return'],
  'scope': 'Semantic inventory only. Reference trajectory files must be supplied separately with their own license and provenance.',
  'disallowed_test_families': TEST_ONLY,
  'training_policy': 'Do not insert test action solutions, captions, poses, generated outputs or evaluator contracts into retrieval, finetuning or repair prompts.'}
 (ROOT / 'benchmark/seed_dictionary.json').write_text(json.dumps(dictionary, indent=2, ensure_ascii=False), encoding='utf-8')
 print('Authored', len(cases), 'cases on', len(IMAGES), 'images.')

if __name__ == '__main__': build()
