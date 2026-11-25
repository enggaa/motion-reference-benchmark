# 출처와 재현 범위

## 이 저장소에 포함된 것

- 연구용 문항, 프로토콜, Python 기록/채점 코드: 이번 프로젝트에서 작성.
- 입력 이미지 8장(`benchmark/images/D1–D4.png`, `T1–T4.png`, v0.2): OpenAI 이미지 생성(2026-11)으로 만든 **실존하지 않는 가상 인물**의 캐릭터 그림체(비실사) 이미지다. 8장 모두 다른 인물이며 성별·키·나이·체형을 달리했고, 자세(서기·앉기·기울기·웅크리기), 시점, 화면 범위를 이미지마다 다르게 지정했다. 실존 인물이나 기존 캐릭터를 모사하지 않았다. 해상도는 1086×1448(세로 3:4)이다. 처음에는 같은 구성의 실사풍 이미지를 만들었으나, Seedance(fal.ai)가 "실존 인물의 모습일 수 있다"는 콘텐츠 정책으로 거부하여(HTTP 422, content_policy_violation) 같은 자세·구도의 캐릭터 그림체로 다시 만들었다.
- 문항 생성: `python tools/build_cases.py` (이미지를 `benchmark/images/`에 둔 뒤 실행하면 해시를 채운다).
- v0.1의 절차적 마네킹 이미지 24장과 초기 자세 정답 JSON은 v0.2에서 제거했다. 해당 파일과 그로 만든 1~4차 실행(예비 실험)은 git 이력에 남아 있다.

## 포함하지 않은 것

KIT-ML/LAFAN1 원본, 재구성된 모션 배열, MakeHuman 원본/FBX/BLEND, 외부 학습 모델, 실제 영상 API 출력은 포함하지 않는다. 연구 준비 과정에서 이 자료들을 로컬로 사용했지만, 본 벤치마크 패키지의 배포 자산과는 별개다. 원본 라이선스가 다른 데이터들을 하나의 코드 라이선스로 덮지 않는다. 저장소의 배포 라이선스는 아직 별도로 선택하지 않았다.

## 관련 원천 자료

- [KIT Motion-Language Dataset](https://motion-annotation.humanoids.kit.edu/dataset/): 원본 MMM/C3D 및 주석 형식.
- [MMM Reference Model](https://sw.pages.h2t.iar.kit.edu/mmm/core/referencemodel.html): 원본 골격 정의.
- [MMM Tools](https://git.h2t.iar.kit.edu/sw/mmm/tools): 로컬 오류 추적에 사용한 모델 커밋 `e8e304addf1ecf4f88e7380555f4293e20134d01`.
- [HumanML3D](https://github.com/EricGuo5513/HumanML3D): KIT-ML 배포 및 21관절 표현 관련 문서.
- [BytePlus video task API](https://docs.byteplus.com/en/docs/modelark/create-video-generation-task-api): 후속 I2V/R2V 어댑터의 기능 확인 참고. 벤치마크는 이 제공자에 종속되지 않으며 실제 사용 시 문서를 다시 확인해야 한다.

이 링크들은 기존 자료의 출처이며, 해당 저자들이 본 벤치마크나 현재 결과를 승인했다는 뜻이 아니다.
