# 출처와 재현 범위

## 이 저장소에 포함된 것

- 연구용 문항, 프로토콜, Python 기록/채점 코드: 이번 프로젝트에서 작성.
- 24개 PNG 이미지: `tools/render_inputs.py`로 Blender 기본 구/타원체/육면체에서 생성. 외부 메시·텍스처·사진·캐릭터를 사용하지 않음.
- 초기 자세 JSON: 작성한 절차적 좌표이며 모션캡처 실측값이 아님. 평가용으로만 제공.
- 문항 생성: `python tools/build_cases.py`.
- 이미지 생성: `blender -b --factory-startup --disable-autoexec --python-exit-code 1 --python tools/render_inputs.py`.

현재 이미지 생성 환경은 Blender 4.2.21 LTS, Workbench, 576×768 PNG다. Blender 버전/플랫폼에 따라 픽셀이 달라질 수 있다. 저장된 이미지를 벤치마크 정본으로 사용하고, 재생성하면 해시와 버전을 갱신한다. 문항 생성 스크립트는 이미지 해시를 초기화하므로 `build_cases.py` 후에는 이미지 생성기를 실행해야 한다.

## 포함하지 않은 것

KIT-ML/LAFAN1 원본, 재구성된 모션 배열, MakeHuman 원본/FBX/BLEND, 외부 학습 모델, 실제 영상 API 출력은 포함하지 않는다. 연구 준비 과정에서 이 자료들을 로컬로 사용했지만, 본 벤치마크 패키지의 배포 자산과는 별개다. 원본 라이선스가 다른 데이터들을 하나의 코드 라이선스로 덮지 않는다. 저장소의 배포 라이선스는 아직 별도로 선택하지 않았다.

## 관련 원천 자료

- [KIT Motion-Language Dataset](https://motion-annotation.humanoids.kit.edu/dataset/): 원본 MMM/C3D 및 주석 형식.
- [MMM Reference Model](https://sw.pages.h2t.iar.kit.edu/mmm/core/referencemodel.html): 원본 골격 정의.
- [MMM Tools](https://git.h2t.iar.kit.edu/sw/mmm/tools): 로컬 오류 추적에 사용한 모델 커밋 `e8e304addf1ecf4f88e7380555f4293e20134d01`.
- [HumanML3D](https://github.com/EricGuo5513/HumanML3D): KIT-ML 배포 및 21관절 표현 관련 문서.
- [BytePlus video task API](https://docs.byteplus.com/en/docs/modelark/create-video-generation-task-api): 후속 I2V/R2V 어댑터의 기능 확인 참고. 벤치마크는 이 제공자에 종속되지 않으며 실제 사용 시 문서를 다시 확인해야 한다.

이 링크들은 기존 자료의 출처이며, 해당 저자들이 본 벤치마크나 현재 결과를 승인했다는 뜻이 아니다.
