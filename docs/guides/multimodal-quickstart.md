# 멀티모달 모델 빠른 시작 (Phase 2: 추론 레시피 일반화)

이미지/텍스트 모델을 HyperCube 에 올려서 브라우저에서 바로 돌려보는 가이드입니다.
2026-05-19 부터는 wizard 에서 **추론 레시피** 를 골라 임의 멀티모달/LLM 모델에
대해 자동 launcher 가 만들어집니다. 예시 모델은 한국어를 잘 다루는
**Qwen2-VL-2B-Instruct** (Apache 2.0, ~4 GB).

## 자동 실행 흐름 (Phase 2)

`hypercube/ml-pytorch-jupyter:cuda12.4-airgap` 이미지는 컨테이너 시작 시 다음을
자동으로 합니다:

1. `/workspace/models/*/*.tar.gz` 발견 시 `/workspace/<asset-slug>/` 로 자동 추출.
2. `HC_LAUNCHER_RECIPE` 환경변수 (backend 가 wizard 선택에 따라 주입) 가 `none` 이
   아니면 `/opt/hc/launch.py` 백그라운드 실행 — `launcher_recipes.json` 의 매칭
   레시피에 따라 transformers 클래스 (`Qwen2VLForConditionalGeneration`,
   `LlavaOnevisionForConditionalGeneration`, `AutoModelForCausalLM`, …) 로 로드하고
   gradio mini UI 를 `127.0.0.1:7860` 에 띄움 (`jupyter-server-proxy` 를 통해
   `<workspace>/proxy/7860/` 로 노출).
3. `/workspace/00-quickstart.ipynb` 시드 — Jupyter 에서 한 셀 Run 하면 gradio 가
   IFrame 으로 임베드되어 노트북 안에서 바로 동작.

→ 사용자 신청 → admin 승인 → `/user` 카드의 **AI UI** 버튼 클릭만으로 멀티모달 UI
바로 사용 가능. 직접 노트북에서 `from_pretrained` 코드를 작성할 필요 없습니다.

## 1. 모델 파일 준비 (로컬에서)

```bash
pip install -U huggingface_hub

huggingface-cli download Qwen/Qwen2-VL-2B-Instruct \
  --local-dir ./Qwen2-VL-2B-Instruct \
  --local-dir-use-symlinks False

tar -czf Qwen2-VL-2B-Instruct.tar.gz Qwen2-VL-2B-Instruct/
ls -lh Qwen2-VL-2B-Instruct.tar.gz   # 약 4 GB
```

다른 모델 예시:
- **SmolVLM-256M-Instruct** (~500 MB) — VLM 가장 가벼움. recipe: 별도 카탈로그 추가 필요 (`Idefics3ForConditionalGeneration`).
- **LLaVA-OneVision-Qwen2-0.5b-ov** (~1.5 GB) — recipe `llava-onevision`.
- **Phi-3-mini-4k-instruct** (~7 GB) — 텍스트 LLM. recipe `auto-causal-lm`.

## 2. HyperCube 에 모델 등록 요청

1. `/user` 접속 후 우상단 **모델 등록 요청** 클릭.
2. **1단계 모델 정보**
   - 모델 이름: `Qwen2-VL-2B-Instruct`
   - 버전: `v1`
   - 설명: `이미지+텍스트 멀티모달, 한국어 지원, ~4GB`
   - 파일: `Qwen2-VL-2B-Instruct.tar.gz` 선택.
3. **2단계 실행 환경**
   - 실행 환경: `PyTorch + Jupyter Lab`.
   - **추론 레시피**: `Qwen2-VL (이미지+텍스트)`. (텍스트만이면 `일반 텍스트 LLM`,
     LLaVA 모델이면 `LLaVA-OneVision`, 자동 실행을 원치 않으면 `자동 실행 안 함`.)
4. **3단계 확인**
   - 워크스페이스 디스크 30 GB 이상 권장 (모델 4 GB + 추출 4 GB + 추론 캐시).
   - 요청 제출.

관리자는 `/admin/approvals` → **+ 템플릿 등록** 으로 같은 wizard 를 거치면 즉시 템플릿이
생성됩니다.

## 3. 관리자 승인

`/admin/approvals` 에서 요청을 보고 **승인** 누르면:

- `ModelAsset(qwen2-vl-2b-instruct)` 생성 (shared).
- `ModelVersion(v1)` 생성.
- `ContainerTemplate(... · PyTorch + Jupyter Lab)` 생성, `default_model_version_ids`
  + `launcher_recipe_id="qwen2-vl"` 가 박혀 있음.

## 4. 컨테이너 생성

`/user` → **+ 새 요청** → 새 템플릿 카드 선택. 자동으로 base_image / GPU /
Jupyter 포트 / 모델 버전이 채워집니다. 컨테이너 이름 + 서버 지정 후 제출.

승인되어 deploy 가 끝나면 컨테이너 카드에 **AI UI** + **Jupyter** 두 액션이
활성화됩니다 (recipe 가 `none` 이면 Jupyter 만).

## 5. AI UI 클릭 → 바로 사용

**AI UI** 를 누르면 backend 가 one-time ticket 발급, gradio 페이지로 직행
(`/workspace/<wk>/proxy/7860/?ticket=...`). 모델이 아직 로딩 중이면 5~60초 동안 503
이 잠깐 뜰 수 있고 새로고침하면 정상 응답. 이미지를 드래그 + 프롬프트 입력 → 한국어
응답을 받습니다.

Jupyter 가 더 익숙하면 **Jupyter** 액션 → `00-quickstart.ipynb` 의 셀 한 번 Run
→ 같은 gradio UI 가 노트북 안에서 IFrame 으로 떠 동작합니다.

## 자원 가이드 (Qwen2-VL-2B 기준)

| 항목 | 권장값 |
|---|---|
| GPU VRAM | 6 GB 이상 (FP16 ~5 GB) |
| 시스템 RAM | 4 GB 이상 |
| 워크스페이스 디스크 | 30 GB |
| 첫 응답까지 | tar 추출 30~60초 + 모델 로드 20~40초 |

## 새 모델/레시피 추가

베이스 이미지 카탈로그가 알고 있는 transformers 클래스 4개 + `none` 외 다른 모델이
필요하면:

1. `backend/apps/containers/launcher_recipes.py` 의 `_RECIPES` 에 새 entry 추가
   (id, label, description, model_class, processor_class, input_kinds, app_template).
2. 베이스 이미지 재빌드 — `bash packaging/ml-images/build-pytorch-jupyter.sh` 가
   `launcher_recipes.json` 을 자동 regenerate 후 docker build + save.
3. 새 이미지를 호스트에 `docker load` (또는 dev 는 그대로 사용).
4. 새 wizard 가 자동으로 새 카드를 노출 — 다른 코드 변경 불필요.

drift guard: `apps/containers/tests/test_launcher_recipes.py` 가 host 에서 실행 시
`launcher_recipes.py` 와 `launcher_recipes.json` 동기화 여부 검증.

## 함정

- **agent #18 (model-cache mount)** 미해결 — 신규 모델 등록 후 첫 deploy 는 agent
  가 cache path 를 못 봐 `docker cp` 우회 필요. PR 머지될 때까지 dev 흐름은 이
  단계가 손작업.
- **GPU 자원 부족** — recipe 가 모델을 메모리에 올리니 GPU slice / VRAM 미확보 시
  컨테이너 OOM. wizard 의 자원 요구사항을 충실히 채울 것.
- **`trust_remote_code`** — 일부 모델 (InternVL 변형 등) 은 `True` 필요. recipe
  메타에 toggle.
