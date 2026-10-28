# Motion Reference Benchmark — v0.1 prototype

**졸업논문 중간보고용 벤치마크 초판. 모델 성능 결과는 아직 없습니다.**

이미지와 요청만 사용하는 I2V에 비해, **LLM이 행동 사전을 활용해 추론한 레퍼런스**를 추가하는 R2V가 행동 정확도를 높이는지 평가하기 위한 로컬 도구입니다. 레퍼런스가 틀려 오히려 결과를 악화시키는 경우도 실패로 포함합니다.

| 조건 | 입력과 처리 |
|---|---|
| A · `direct_i2v` | 같은 이미지 + 같은 요청 |
| B · `llm_reference_r2v` | 같은 입력 + LLM이 만든 최초 레퍼런스 |
| C · `verified_reference_r2v` | B와 **동일한 최초 레퍼런스**를 검사하고 필요하면 1회 수정 |

현재 저장소는 **벤치마크 문항·입력 이미지·평가 계약·실행 기록·채점 도구**와 **LLM planner 어댑터(초판)**를 제공합니다. 별도 자세 추정기, 벤치마크용 리타기팅 연결, 유료 영상 API 어댑터는 구현되어 있지 않습니다. `reference_baseline/`에 과거 로컬 리타기팅 코드를 별도로 보존했지만 호환 장면/동작 파일은 외부에서 준비해야 합니다. 과거의 세 동작 재생기가 미관측 행동 생성에 성공한 것으로 해석하면 안 됩니다.

## 구성

- 개발 8문항 / 채점 연습 4문항 / 평가 12문항, **총 24문항과 24개 실제 PNG 입력**.
- 평가 12문항은 **사전 내·조합·사전 밖 × 서기·앉기·기울기·웅크리기**를 각각 1개씩 포함합니다. 통계적 검정력을 갖춘 대규모 벤치마크는 아닙니다.
- 사전 밖은 **고정된 seed 사전에 없는 행동**입니다. 기반 모델의 사전학습에서 본 적 없다는 뜻은 아닙니다.
- 평가용 사전 밖 행동 `bow`, `cross_arms`는 개발·채점 연습 행동군에서 제외했습니다. 알려진 동작과 초기 자세 유형은 분할 사이에서 공유합니다. 모든 행동군/자세가 완전히 홀드아웃된 설계는 아닙니다.
- 입력 이미지는 Blender 기본 도형으로 직접 제작했습니다. KIT/LAFAN 모션, MakeHuman 캐릭터, 체크포인트, 비밀키를 포함하지 않습니다. 단순 캐릭터를 사용하므로 실제 사진·다양한 2D 스타일로의 일반화는 후속 과제입니다.

![네 초기 자세](docs/initial_pose_grid.png)

## 빠른 시작

Python 3.10 이상, 표준 라이브러리만으로 검증·기록·채점할 수 있습니다.

```bash
python -m motionbench validate
python -m unittest discover -s tests -v
python -m motionbench plan --split development --repeats 1 --out runs/dev-001
python -m motionbench summarize --run runs/dev-001
```

마지막 명령은 모델을 실행하지 않았으므로 **점수 `null`**을 출력합니다. 이를 0점이나 성공률로 꾸미지 않습니다. 기본 3회 반복이면 개발 72개, 평가 108개 슬롯입니다. 처음에는 개발 1회 반복 24슬롯으로 기능을 확인하는 것을 권합니다. API 호출·비용 발생 기능은 없습니다.

실패 예시:

```bash
python -m motionbench record --run runs/dev-001 --attempt 0001 --status blocked --stage planning
```

실제 생성 후에는 MP4 파일을 등록하고, 모든 요구사항에 대한 두 독립 평가자의 판정을 입력합니다. 컨테이너 확인은 디코딩/내용 검증을 대신하지 않습니다.

```bash
python -m motionbench artifact --run runs/dev-001 --attempt 0002 --kind reference_initial --file /path/to/reference.mp4
python -m motionbench record --run runs/dev-001 --attempt 0002 --status succeeded --output /path/to/final.mp4
python -m motionbench review-template --case D01 --out runs/dev-001/review.json
# 실제 평가자가 양식을 채운 뒤:
python -m motionbench review --run runs/dev-001 --attempt 0002 --file runs/dev-001/review.json
```

## LLM planner (경로 A: Claude 구독)

```bash
python -m motionbench planner --run runs/dev-001                       # dry-run: 요청만 저장, 모델 호출 없음
python -m motionbench planner --run runs/dev-001 --backend claude-code --model sonnet --max-calls 1
```

`claude-code` backend는 로그인된 Claude Code CLI(`claude -p`)를 호출하므로 **Claude 구독 사용량에서 차감**되고 API 키 과금은 하지 않습니다(`ANTHROPIC_API_KEY`는 하위 프로세스에서 제거). CLI가 PATH에 없으면 Windows 데스크톱 앱에 번들된 최신 CLI를 찾고, 그래도 없으면 `MOTIONBENCH_CLAUDE_EXE`로 경로를 지정합니다. 처음 한 번 `claude auth login`으로 구독 계정에 로그인해야 합니다. 사용자 설정·CLAUDE.md·도구는 끄지만(`--safe-mode`, `--tools ""`, 자체 system prompt) Claude Code 래퍼가 끼어 있으므로, 입력을 완전히 통제하는 API 경로(B)는 후속 개선입니다. 동결 전에 backend를 하나로 확정합니다.

B/C의 같은 `paired_reference_group`에 계획 1개를 만들어 두 시도에 같은 `plan` 아티팩트로 등록합니다. 입력은 `generator_inputs.json`과 seed 사전의 의미 목록뿐이며 evaluator 파일은 읽지 않습니다. 전송 오류는 1회 재시도, 구조 검사 실패는 재생성하지 않고 `failed/planning`으로 기록합니다. 구조 검사(관절 15개, 0초 관측 키프레임, 원문 인용, 시간 순서)를 통과해도 **동작이 맞다는 뜻은 아닙니다.** 뼈 길이 변화는 경고로만 남깁니다. test 분할은 `--allow-test` 없이는 거부합니다.

계획 확인용 그림: `python tools/plan_preview.py runs/dev-001/plans/D01-01` → 입력 이미지 옆에 키프레임별 정면/측면 막대 인형 SVG. 렌더러나 IK가 아니라 눈으로 보는 점검 도구입니다. 개발 분할에서 초기 자세를 평가 정답과 비교: `python tools/initial_pose_error.py runs/dev-001` (evaluator를 읽으므로 생성에 사용 금지). 첫 실제 결과: [results/dev-001-planner](results/dev-001-planner/README.md).

`attempt`와 `case`는 계획된 ledger에서 확인해야 합니다. 예시의 0002가 반드시 R2V 조건이라는 뜻은 아닙니다. 조건 순서는 무작위입니다.

## 평가 규칙

모든 명시 요구를 만족한 최종 영상만 성공입니다. 실패·중단·판정 불확실은 성공으로 세지 않으며 배정된 분모에서 제거하지 않습니다. 미실행/미평가/평가자 불일치가 남으면 주 점수는 아직 계산하지 않습니다. 전체 완료 시 사례별 반복 성공률의 평균과 직접 I2V 대비 대응 차이를 계산합니다. v0.1에는 신뢰구간·유의성 검정이 없습니다.

`benchmark/evaluator/`의 기준과 초기 관절 정답은 **평가 전용**입니다. `generator_inputs.json`에는 넣지 않습니다. 공개/공유된 테스트를 개발에 사용하면 그 버전의 홀드아웃 지위는 소멸합니다. 변경 후 새 버전을 만들어야 합니다.

## 문서

- [Claude 인계 문서](HANDOFF.md) · [Claude 작업 지침](CLAUDE.md)
- [중간보고서](docs/MIDTERM_REPORT.ko.md)
- [실험 프로토콜](docs/PROTOCOL.md)
- [채점 기준](docs/RUBRIC.md)
- [어댑터 계약과 누출 방지](docs/ADAPTER_CONTRACT.md)
- [출처와 재현 범위](docs/PROVENANCE.md)

현재 상태: 입력/문항 검증 가능, 실행 슬롯/기록/채점 가능, LLM planner 어댑터 구현(dry-run과 고정 응답 시험만 검증), **실제 planner 출력·레퍼런스 렌더러·영상 모델 연결 및 비교실험 미실행**. 이 저장소의 벤치마크 단위시험 결과와 외부 모델 성능을 구분합니다.
