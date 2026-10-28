# 생성 파이프라인 (v0.2 개발판)

입력 이미지와 요청에서 최종 영상까지 가는 단계를 정리합니다. 각 단계의 출력과 실패를 따로 남겨서, 최종 영상만 보고 원인을 짐작하지 않게 합니다(PROTOCOL의 실패 위치).

```
이미지 + 요청 (generator_inputs.json)
  │
  ├─[A] ───────────────────────────────────────────────▶ Seedance I2V ─▶ final.mp4
  │
  ▼
① 초기 자세   LLM 자세 호출 → 실루엣 맞춤 (posefit, --pose-fit)       실패: initial_pose
② 계획        LLM 계획 호출 (행동 분해, 사전 참조, 키프레임)          실패: planning
③ 레퍼런스    뼈 길이 고정 FK/IK → Blender 마네킹 MP4                  실패: retargeting
  │            reference.mp4(입력 카메라) · reference_front.mp4 · grid_*.png · telemetry.json
  ├─[B] reference_initial ────────────────────────────▶ Seedance R2V ─▶ final.mp4
  ▼
④ 게이트(C)   렌더 프레임 검토 → 계획 1회 수정 → 재렌더 → 재검토      실패: reference_review (blocked)
  └─[C] 통과한 레퍼런스 (initial 또는 repaired) ─────▶ Seedance R2V ─▶ final.mp4
⑤ 평가        익명 패키지 → 평가자 2명(+조정자) → import → summarize
```

## 단계별 명령

| 단계 | 명령 | 모델 비용 |
|---|---|---|
| 슬롯 계획 | `plan --split development --repeats 1 --out runs/dev-002` | 없음 |
| ①② | `planner --run R --backend claude-code --model sonnet --pose-fit` | Claude 구독 (그룹당 2회 호출) |
| ③ | `render-reference --run R --group D01-01 --register` | 없음 (로컬 Blender) |
| ④ | `verify-reference --run R --group D01-01` | Claude 구독 (그룹당 1–3회 호출) |
| 최종 영상 | `generate --run R` (dry run) → `--execute --max-usd N` | fal.ai 결제 ([SEEDANCE_SETUP.md](SEEDANCE_SETUP.md)) |
| 평가 패키지 | `package-review --run R --out review/pkg --mapping private/map.json` | 없음 |
| 평가 반영 | `import-ratings --run R --mapping private/map.json --rater A.json --rater B.json` | 없음 |
| 집계 | `summarize --run R` | 없음 |

레퍼런스 자체를 사람이 평가할 때는 `package-review --kind reference`를 씁니다. B/C가 공유하는 최초 레퍼런스는 한 항목으로 묶입니다.

**검증기 보정:** 레퍼런스 사람 평가를 `import-ratings`로 들여온 뒤 `agreement --run R`을 실행합니다. 출력은 다음과 같습니다.
- 계약 요구별로 검증기 판정과 사람 판정의 원 일치율, Cohen's κ, 혼동표
- 사람은 fail인데 검증기가 pass한 **놓친 실패** 수

v3과 v4 재검토에서 판정이 흔들렸기 때문에(dev-004 기록), test 전에 이 대조를 calibration 문항에서 거쳐야 합니다.

## 정보 경계

| 단계 | 볼 수 있는 것 | 볼 수 없는 것 |
|---|---|---|
| ①② | 입력 이미지, 원문 요청, seed 사전의 의미 목록, 리그 규격 | `benchmark/evaluator/`, 평가용 행동 이름 |
| ③ | 계획, 리그 | 평가 정답 |
| ④ 검토자 | 입력 이미지, 원문 요청, **렌더된 프레임**, 렌더러의 자동 신호 | 계획 JSON, 평가 계약 |
| 평가자 | 입력 이미지, 원문 요청, 익명 영상, 채점 기준 | 조건명, 계획, 게이트 결과, 원본 경로 |

`tools/initial_pose_error.py`는 평가 정답을 읽는 개발 분석 도구입니다. development에서만 실행되고, 그 결과를 생성에 넣지 않습니다.

## 알려진 한계

- **카메라를 안다는 가정**: 실루엣 맞춤은 입력이 같은 마네킹·같은 카메라로 렌더링됐다고 가정합니다. 이 합성 벤치마크에서만 성립하고 실사 이미지에는 적용되지 않습니다.
- **깊이 모호성**: 한 시점 실루엣만으로는 앞뒤 깊이를 구분할 수 없습니다. 그래서 앞뒤 방향 변화에 큰 벌점을 주지만, 3D 관절 오차가 남을 수 있습니다.
- **정면 렌더의 용도**: 정면 영상은 검토 보조 자료일 뿐입니다. R2V에 넣는 레퍼런스는 입력 카메라 영상입니다.
- **미검증 경로**: Seedance 호출 경로는 키가 생기기 전까지 검증되지 않았습니다.
