# 외부 실행기 계약

벤치마크 CLI는 모델을 호출하지 않는다. 향후 어댑터는 `generator_inputs.json`만 생성 입력으로 읽고 evaluator 디렉터리는 접근하지 않는다.

## 공통 입력

`attempt_id`, 원문 `request`, 이미지 파일/해시, `duration_s`, `arm`, 고정 사전 버전. 모든 조건은 같은 사례의 같은 이미지 바이트/요청을 사용한다. 검증기는 그 입력을 보고 자체 판단해야 하며 evaluator 계약을 정답 프롬프트로 주지 않는다.

## LLM 계획 출력(권장)

```json
{
  "initial_pose": {"observations": [], "uncertainties": []},
  "actions": [{"id": "a1", "request_quote": "원문 일부", "side": "right", "completion": "관찰 가능한 종료 조건"}],
  "retrieval": [{"entry_id": "...", "sha256": "...", "used_for": "..."}],
  "keyframes": [{"time_s": 0.0, "constraints": [], "origin": "observed_or_retrieved_or_inferred"}],
  "assumptions": [],
  "unsupported_requirements": []
}
```

구현: `motionbench/planner.py`의 `PLAN_SCHEMA`가 이 형태를 구체화했다. `initial_pose`와 각 키프레임은 15개 관절 좌표(좌 +X, 앞 −Y, 위 +Z, 미터)를 모두 가지며, `retrieval`의 해시는 모델이 아니라 기록 측(`request.json`, 실행 로그)에서 남긴다. 현재 seed 사전에는 궤적이 없어 `retrieved`는 의미 수준 참조만 뜻한다. 위 형태는 계약 제안이며 현재 생성기 구현/학습 완료를 뜻하지 않는다. LLM은 행동 단계와 제약을 제안하고, IK/자세 계산기가 실제 초기 상태에서 관절을 계산한다. 키프레임이 사전에서 온 것인지 추론한 것인지 기록한다. 초기 자세를 T-pose로 강제 초기화하지 않는다. 추론 결과는 검증 전 사전/학습 데이터에 자동 편입하지 않는다.

## 산출물과 추적

계획 JSON, 최초 레퍼런스 MP4, 수정 레퍼런스 MP4, 검증 판단 JSON, 실제 리그 telemetry, 최종 MP4, 실행 로그를 보관한다. 모델/버전/요청/응답/토큰/시드/시간/비용/재시도/실패 위치를 기록한다. 토큰이나 인증키는 커밋하지 않는다.

```bash
python -m motionbench artifact --run runs/dev-001 --attempt 0002 --kind plan --file private/plan.json
python -m motionbench artifact --run runs/dev-001 --attempt 0002 --kind reference_initial --file private/reference.mp4
```

두 reference 조건의 동일 `paired_reference_group`에 최초 레퍼런스를 등록할 때 해시가 다르면 거부한다. 수정 레퍼런스는 verified 조건에만 등록할 수 있다. gate와 human evaluation은 별개다. gate가 pass라고 해도 최종 사람이 실패로 평가할 수 있다.

## 익명 검토

조건명·출처 경로·모델 메타데이터가 드러나지 않는 무작위 ID로 평가 복사본을 제공한다. 원본은 해시와 함께 보존한다. 자동 비식별 영상 패키징은 v0.1에서 아직 구현하지 않았다. 따라서 실행 담당자가 조건 매핑을 별도 보관하고 평가자에게 계획/gate/조건명 없이 제공해야 한다.

## 실제 실행 전 필수 확인

- 선택 모델/엔드포인트가 I2V 및 참조 영상 입력을 실제 지원하는지 확인.
- 모드별 이미지 역할/시작 프레임 강제 여부 차이 기록.
- 입력의 실제 미디어 디코딩·길이·크기·FPS·해시 검사.
- 숫자로 정한 비용 상한 및 호출 횟수 한도.
- 계약·사전·코드·모델 설정 동결, 사람 평가자 확보.

이 항목은 현재 완료된 온라인 실험 결과가 아니다. 실제 모델 연결 때 채워야 한다.
