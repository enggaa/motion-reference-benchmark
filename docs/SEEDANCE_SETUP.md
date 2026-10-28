# 시댄스(Seedance) 연결 안내

작성일: 2026-10-29. 아래 가격과 파라미터는 fal.ai 모델 페이지를 그날 확인한 값입니다. 결제 전에 다시 확인하세요. 계정 생성, 결제, API 키 입력은 사용자가 직접 해야 합니다.

## 왜 fal.ai인가

- **문서화된 엔드포인트**: ByteDance Seedance 2.0의 image-to-video(조건 A)와 reference-to-video(조건 B/C)를 같은 계정, 같은 키 하나로 호출할 수 있습니다.
  - [I2V 페이지](https://fal.ai/models/bytedance/seedance-2.0/image-to-video/llms.txt)
  - [R2V 페이지](https://fal.ai/models/bytedance/seedance-2.0/reference-to-video/llms.txt)
- **참조 영상 입력 지원**: R2V는 이미지 최대 9장과 영상 최대 3개(합계 2–15초, 480p–720p)를 받고, 프롬프트에서 `@Image1`, `@Video1`로 가리킵니다. 우리 레퍼런스(576×768, 6–8초)는 이 범위 안에 있습니다.
- **BytePlus ModelArk(공식)도 참조 영상을 받는다**고 알려져 있습니다. 다만 공식 API 문서는 직접 확인하지 못했습니다. 3자 정리 글 기준으로는 최대 3개, 각 2–15초이고, 첫 프레임 모드와 참조 모드는 함께 쓸 수 없다고 합니다([가이드](https://aiapiplaybook.com/blog/seedance-2-0-reference-to-video-api-complete-developer-guide/), [가격 정리](https://framesurfer.com/blogs/seedance-2-0-pricing)).
- **다른 재판매처**: Atlas Cloud 같은 곳이 더 싸다고 홍보하지만([예](https://www.atlascloud.ai/blog/guides/seedance-2-cost-per-second)), 연구용 재현성을 생각하면 한 제공자로 끝까지 가는 것이 우선입니다.

## 예상 비용 (상한 추정, `motionbench.video.estimate_usd`)

**계산식**: fal 토큰식은 `높이 × 너비 × 초 × 24 / 1024`입니다. 1k 토큰당 $0.014이고, 참조 영상이 있으면 $0.0086입니다. 참조 영상의 길이도 토큰에 더해진다고 보고 상한으로 잡았습니다.

| 해상도 | development 24슬롯 (A / B / C) | test 108슬롯 |
|---|---|---|
| 480p | 약 $18 ($5.2 / $6.4 / $6.4) | 약 $82 |
| 720p | 약 $41 | 약 $184 |

비용을 최소화하려면 480p로 development 24슬롯부터 돌리는 것을 권합니다. 오디오를 꺼도 가격은 같지만 평가에 필요 없어서 끕니다.

## 해야 할 일 (사용자)

1. [fal.ai](https://fal.ai)에 가입하고 결제 수단을 등록한 뒤 크레딧을 충전합니다. development만 돌릴 거라면 $20–25 정도면 됩니다.
2. 대시보드에서 API 키를 만듭니다.
3. 키는 **저장소에 넣지 말고** 환경변수로만 둡니다. PowerShell에서 현재 창에만 적용하려면:
   ```powershell
   $env:FAL_KEY = '여기에 키'
   ```

## 실행 (모델 호출은 3단계에서만)

```bash
# 1) B/C 레퍼런스 등록, 그리고 C 게이트 (Claude 구독 사용량만 씀)
python -m motionbench render-reference --run runs/dev-002 --group D01-01 --register
python -m motionbench verify-reference --run runs/dev-002 --group D01-01
# 2) 결제 없이 요청 내용과 예상 비용 확인
python -m motionbench generate --run runs/dev-002 --resolution 480p
# 3) 상한을 걸고 실제 호출
python -m motionbench generate --run runs/dev-002 --resolution 480p --execute --max-usd 20
```

- **모든 슬롯은 처음 한 번만 실행됩니다.** 실패해도 같은 run에서 다시 돌리지 않습니다. 실패는 `failed/final_generation` 또는 `failed/transport`로 남습니다.
- **결과가 마음에 들지 않아도 재생성하지 않습니다**(PROTOCOL).

## 실제 연결 때 확인할 것 (아직 미확인)

- **이미지 전달 방식**: data URI(base64)를 그대로 받는지, 아니면 fal 저장소 업로드 URL이 필요한지. 지금 코드는 data URI를 보냅니다.
- **실제 출력**: 3:4 비율과 480p 출력의 실제 크기와 FPS, 그리고 첫 호출의 실제 비용(로그의 추정치와 비교).
- **R2V의 시작 프레임**: R2V에서는 입력 이미지가 시작 프레임으로 강제되지 않습니다. 이 차이는 조건 간 차이로 기록하고, 시작 연속성은 부 결과로 평가합니다.
- **seed**: 입력 파라미터로 받지 않고 출력으로만 돌려줍니다. 같은 seed로 재현할 수는 없으니 로그에 남기기만 합니다.
