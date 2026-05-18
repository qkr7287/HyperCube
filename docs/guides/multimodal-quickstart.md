# 멀티모달 모델 빠른 시작 (Qwen2-VL-2B)

이미지를 입력으로 받고 텍스트로 응답하는 멀티모달 모델을 HyperCube에 올려서
브라우저에서 직접 돌려보는 가이드입니다. 예제 모델은 가벼우면서도 한국어를
잘 다루는 **Qwen2-VL-2B-Instruct** (Apache 2.0, ~4 GB)입니다.

다른 모델(SmolVLM, LLaVA-OneVision 등)도 같은 절차로 올릴 수 있습니다.
모델 로드 코드 한 줄만 바꿔주면 됩니다.

## 1. 모델 파일 준비 (로컬에서)

Qwen2-VL-2B-Instruct는 HuggingFace에서 받습니다.

```bash
# huggingface_hub 설치 (한 번만)
pip install -U huggingface_hub

# 다운로드 (LFS 포함 약 4 GB)
huggingface-cli download Qwen/Qwen2-VL-2B-Instruct \
  --local-dir ./Qwen2-VL-2B-Instruct \
  --local-dir-use-symlinks False
```

HyperCube의 업로드 API는 파일 하나만 받기 때문에, 디렉터리째 tar로 묶습니다.

```bash
tar -czf Qwen2-VL-2B-Instruct.tar.gz Qwen2-VL-2B-Instruct/
ls -lh Qwen2-VL-2B-Instruct.tar.gz   # 약 4 GB
```

## 2. HyperCube에 모델 등록 요청

1. `/user` 접속 후 우상단 **모델 등록 요청** 클릭
2. **1단계 모델 정보**
   - 모델 이름: `Qwen2-VL-2B-Instruct`
   - 버전: `v1`
   - 설명: `이미지+텍스트 멀티모달, 한국어 지원, ~4GB`
   - 파일: `Qwen2-VL-2B-Instruct.tar.gz` 선택
3. **2단계 실행 환경**
   - `PyTorch + Jupyter Lab` 선택 (현재는 이 한 가지)
4. **3단계 확인**
   - 고급 설정에서 워크스페이스 디스크를 `30 GB` 이상으로 올려두는 것을 권장
     (모델 4 GB + 추출 후 추가 4 GB + 가중치 로드 시 여유)
   - 요청 제출

관리자가 직접 등록하는 경우엔 `/admin/model-requests` → **+ 템플릿 등록**으로
같은 wizard를 거치면 즉시 템플릿이 생성됩니다.

## 3. 관리자 승인 (또는 admin wizard로 즉시 등록)

`/admin/model-requests`에서 요청을 보고 **승인**을 누르면:

- `ModelAsset(qwen2-vl-2b-instruct)` 생성 (shared)
- `ModelVersion(v1)` 생성
- `ContainerTemplate(Qwen2-VL-2B-Instruct · PyTorch + Jupyter Lab)` 생성, 이 버전을
  `default_model_version_ids`로 묶음

## 4. 컨테이너 생성

`/user`에서 **+ 새 요청** 클릭 → 새로 생긴 템플릿 카드 (포함 모델: `Qwen2-VL-2B-Instruct v1`로
표시됨)를 선택. 자동으로 base_image, GPU, Jupyter 포트가 채워지고 모델 버전도
미리 선택됩니다. 컨테이너 이름과 서버를 고른 뒤 제출.

승인되어 deploy가 끝나면 컨테이너 카드에 **Jupyter** 액션이 활성화됩니다.

## 5. Jupyter에서 모델 실행

Jupyter 액션을 눌러 워크스페이스로 진입. 모델 파일은 자동으로 컨테이너 안의 다음
경로에 마운트됩니다:

```
/workspace/models/qwen2-vl-2b-instruct@v1/Qwen2-VL-2B-Instruct.tar.gz
```

`docs/samples/qwen2-vl-2b-gradio.ipynb` 파일을 Jupyter에 업로드(왼쪽 파일 패널 →
업로드) 한 뒤 **Run All Cells**. 다음 순서로 실행됩니다:

1. tar.gz 추출 → `/workspace/Qwen2-VL-2B-Instruct/`
2. transformers로 모델 로드 (`AutoProcessor` + `Qwen2VLForConditionalGeneration`)
3. gradio mini UI를 노트북 셀 안에 inline 렌더링
4. 이미지 드래그 + 프롬프트 입력 → 응답 출력

`inline=True`로 띄우기 때문에 외부 포트나 추가 권한 없이 노트북 출력 영역에서 바로
대화할 수 있습니다.

## 자원 가이드 (Qwen2-VL-2B 기준)

| 항목 | 권장값 |
|---|---|
| GPU VRAM | 6 GB 이상 (FP16 로드 기준 ~5 GB) |
| 시스템 RAM | 4 GB 이상 |
| 워크스페이스 디스크 | 30 GB (tar.gz 4G + 추출 4G + 추론 캐시 여유) |
| 첫 응답까지 | tar 추출 30~60초 + 모델 로드 20~40초 |

## 다른 모델로 바꾸기

`AutoProcessor.from_pretrained(...)`와 `Qwen2VLForConditionalGeneration.from_pretrained(...)`
두 줄만 해당 모델의 클래스로 교체하면 됩니다. 예:

- **SmolVLM-256M-Instruct** (~500 MB) — `AutoModelForVision2Seq`, 가장 가벼움
- **LLaVA-OneVision-Qwen2-0.5b-ov** (~1.5 GB) — `LlavaOnevisionForConditionalGeneration`
- **Phi-3-Vision-128k-Instruct** (~8 GB) — `AutoModelForCausalLM`, 긴 컨텍스트
