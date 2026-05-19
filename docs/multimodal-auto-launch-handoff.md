# Multimodal Auto-Launch — Phase 2 (완료)

마지막 갱신: 2026-05-19

## 큰 그림

"ML Workspace = 사용자가 새 컨테이너 신청 → admin 승인 → 워크스페이스 클릭 →
**이미 모델이 메모리에 떠있고 멀티모달 gradio UI 가 동작 중**" 까지 자동.

## Phase 1 (이전, commit `b57dd07`)

Qwen2-VL-2B-Instruct **하나만** 동작하는 하드코딩 PoC. `start-jupyter.sh` 가
디렉터리명 `qwen2-vl-2b-instruct` 감지하면 `launch_qwen2vl.py` 백그라운드 실행.

## Phase 2 (완료, commits 6bad602 → 8cd2d8b)

**핵심 디자인 한 줄**: `inference recipe = (model_class, processor_class, app_template)`
튜플을 wizard 에서 선택. 카탈로그에 없는 architecture 도 `직접 입력` 으로 inline
등록 가능 — 베이스 이미지 재빌드 불필요.

### 데이터 모델

| 모델 | 신규 필드 | migration |
|---|---|---|
| `ContainerTemplate` | `launcher_recipe_id: CharField(default="none")` | `containers/0015_template_launcher_recipe` |
| `ContainerTemplate` | `launcher_overrides: JSONField(default=dict)` | `containers/0016_template_launcher_overrides` |
| `ModelUploadRequest` | `launcher_recipe_id` | `models_catalog/0004_request_launcher_recipe` |
| `ModelUploadRequest` | `launcher_overrides` | `models_catalog/0005_request_launcher_overrides` |

### Recipe 카탈로그

`backend/apps/containers/launcher_recipes.py`. `LauncherRecipe` dataclass 의
필드: `id / label / description / model_class / processor_class / input_kinds
/ app_template / architectures / trust_remote_code / extra_env / available
/ category`.

현재 4개 active recipe:

| id | model_class | app_template | 커버 |
|---|---|---|---|
| `auto-causal-lm` | `AutoModelForCausalLM` + `AutoTokenizer` | `gradio_text_chat` | 텍스트 LLM (Llama / Mistral / Qwen2 / Phi3 / Gemma 등 9 arch) |
| `qwen2-vl` | `Qwen2VLForConditionalGeneration` | `gradio_vlm_chat` | Qwen2-VL 2B/7B |
| `llava-onevision` | `LlavaOnevisionForConditionalGeneration` | `gradio_vlm_chat` | LLaVA-OneVision 계열 |
| `none` | — | `none` | 자동 실행 안 함 (Jupyter 만) |

### Env 주입 (`backend/apps/containers/services/deployment.py`)

`_launcher_env_for_request` 가 recipe != "none" 이고 모델 1개 이상 attached 면:

```
HC_LAUNCHER_RECIPE      = qwen2-vl | auto-causal-lm | __custom__ | ...
HC_MODEL_DIR            = /workspace/<asset-slug>
HC_GRADIO_PORT          = 7860
HC_GRADIO_ROOT_PATH     = /proxy/7860
```

`__custom__` 인 경우 추가로:

```
HC_LAUNCHER_MODEL_CLASS         = <override>
HC_LAUNCHER_PROCESSOR_CLASS     = <override>
HC_LAUNCHER_APP_TEMPLATE        = gradio_text_chat | gradio_vlm_chat
HC_LAUNCHER_TRUST_REMOTE_CODE   = true | false
```

### Base image (`packaging/ml-images/pytorch-jupyter/`)

- `launch.py` — generic. `/opt/hc/launcher_recipes.json` 에서 recipe lookup,
  `importlib` 로 transformers 클래스 resolve, `gradio_vlm_chat` /
  `gradio_text_chat` 빌더 디스패치. `HC_LAUNCHER_RECIPE == "__custom__"` 면
  catalogue 안 보고 env 4종 으로 inline recipe dict 구성.
- `launcher_recipes.json` — 카탈로그 frozen mirror. 빌드 시 backend
  `launcher_recipes.py` 에서 regenerate.
- `start-jupyter.sh` — 디렉터리명 분기 제거.
  `[[ "${HC_LAUNCHER_RECIPE:-none}" != "none" ]]` 면 `/opt/hc/launch.py` 백그라운드.
- `Dockerfile` — `launch.py + launcher_recipes.json` COPY.
- `build-pytorch-jupyter.sh` — 빌드 전 CRLF strip + JSON regenerate.

### Wizard UI (`UploadModelWizard.svelte`)

- Step 2 = 실행 환경 테이블 (preset) + 추론 레시피 테이블 (recipe) 동시 표시.
  preset 1개라 자동 선택. recipe 는 5종 (4 active + 1 직접 입력) 카테고리 그룹.
- 직접 입력 행 클릭 시 inline 폼 expand: model_class / processor_class /
  app_template (3 옵션) / trust_remote_code. submit 시 `launcher_overrides`
  JSON 으로 전송.
- 업로드 progress overlay: XHR 기반 percent + MB 카운터 + 취소 버튼.

### NewRequestModal (`/user` 새 컨테이너 요청)

테이블 + 검색 + 필터 chip (전체 / 모델). 템플릿 선택 후 cfg-table (key | value)
한 장으로 컨테이너 이름 / 배치 서버 / GPU / 자원 limits / 모델 자산.

### /user 대시보드

- Layout header 에 hero merge (title + KPI 4종 + 새로고침 icon + 모델 등록 /
  새 요청 액션 + username/logout).
- 사이드 패널: 단일 "요청 리스트" 테이블 (모델 + 컨테이너 통합, 종류 chip 필터).
- 컨테이너 행 액션 컬럼: `[모니터링] [AI UI] [Jupyter]` + 설정 컬럼 [⋯].
- 정렬: CPU / MEM / GPU / GPU VRAM / 최근 모두 가능.

### /admin/approvals

- 두 탭 (컨테이너 요청 / 모델 등록 요청) — 동일 패턴 테이블.
- 검색 input + 정렬 (sortable th, ↑/↓ 화살표) + pending/all 필터 chip.
- 액션 컬럼 분리: `상세` (모달) + `검토` (pending → [승인][반려], 그 외 → reviewer).
- Status pill: tone 색 텍스트 + 12% bg + 38% border (color-mix). 흰 글씨 +
  saturated bg 패턴 제거.
- 신규 `ModelRequestDetailModal` — 기본정보 / 파일 / 실행환경+자원 / 생성 템플릿
  / 검토 결과 섹션.

### 백엔드 테스트

`backend/apps/containers/tests/test_launcher_recipes.py`:

| 테스트 | 검증 |
|---|---|
| `test_required_recipes_present` | qwen2-vl / auto-causal-lm / none 항상 있어야 |
| `test_none_is_not_auto` | `is_auto("none") == False` |
| `test_get_recipe_rejects_unknown` | 잘못된 id 는 KeyError |
| `test_image_json_matches_catalogue` | py 와 image JSON drift 가드 (image json 없으면 skip) |
| `test_none_recipe_injects_no_launcher_env` | recipe=none 일 때 env {} |
| `test_qwen2vl_recipe_injects_recipe_env_with_model_dir` | recipe 환경 변수 4종 |
| `test_recipe_skipped_when_no_model_attached` | 모델 없으면 env {} |
| `test_custom_recipe_injects_override_env` | __custom__ 일 때 model_class 등 env 추가 |
| `test_custom_recipe_without_model_class_yields_no_env` | model_class 비어있으면 env {} |

### 검증된 E2E

1. **Qwen2-VL (Phase 1 회귀)** — 기존 ops-flow-1 컨테이너 삭제 후 새 base image
   로 재배포. 같은 모델, recipe=qwen2-vl, `launch.py` 가 catalogue 에서 클래스
   lookup 후 gradio 부팅. 한국어 응답 받음.
2. **Qwen2.5-0.5B-Instruct (auto-causal-lm)** — wizard 에서 업로드 + recipe 선택
   → admin approve → 컨테이너 deploy → `gradio.ChatInterface` 7860 →
   `gradio_api/call/chat` HTTP 200, "안녕하세요! 어떻게 도와드릴까요?".
3. **Custom recipe** — 같은 Qwen2.5 모델 + recipe=`__custom__` +
   overrides `{model_class: "Qwen2ForCausalLM", processor_class: "AutoTokenizer",
   app_template: "gradio_text_chat"}` → `launch.py` 가 inline recipe 빌드 →
   "동작이 정상적으로 작동합니다." 응답.

## 함정 / 주의

- **agent #18 (model-cache mount)** 미해결 — 신규 모델 등록 후 첫 deploy 는
  agent prepare 가 host mount path 를 못 봐서 `docker cp` 우회 한 번 필요.
  PR 머지될 때까지 dev 흐름은 이 단계가 손작업.
- **카탈로그 source-of-truth = `launcher_recipes.py`**. JSON 은 빌드 스크립트가
  regenerate. 수동 편집하면 drift guard 테스트가 host 에서 실행될 때 잡힘.
- **HC_MODEL_DIR 정확성** — `start-jupyter.sh` 가 `/workspace/<asset-slug>/`
  로 tar 해제. backend 는 `ModelVersion.asset.slug` 그대로 사용. 두 곳이
  합의돼야.
- **CRLF**: build script 가 자동 strip. Windows clone 에서 수동 빌드 시 주의.
- **gradio `root_path`** — `/proxy/7860` 없으면 static asset 깨짐. backend 가
  `HC_GRADIO_ROOT_PATH` 주입.
- **DATA_UPLOAD_MAX_MEMORY_SIZE = 200MB** — workspace proxy 가 multipart body
  를 통째로 읽어 forward 하므로 Django 기본 2.5MB 면 gradio image upload 가
  RequestDataTooBig 으로 fail. settings 에서 bump. tus/Range 기반 resumable
  upload 는 미구현 (취소만 가능).

## 다음 단계 후보

| 작업 | 비용 | 가치 |
|---|---|---|
| SmolVLM / Phi-3-Vision / InternVL recipe 추가 | 10줄 + 이미지 빌드 15분/개 | VLM 변형 즉시 자동 |
| `gradio_image_gen` / `gradio_asr` / `gradio_tts` app_template 구현 | 각 ~80줄 + 이미지 재빌드 | Diffusion / Whisper / TTS 자동화 가능 |
| Resumable upload (tus) | 백엔드 chunked endpoint + 프론트 chunk loop | 대용량 모델 (수십 GB) 안정성 |
| agent #18 fix | agent repo PR | dev 흐름 docker cp 우회 제거 |

## 관련 파일 인덱스

- 카탈로그: `backend/apps/containers/launcher_recipes.py` ↔ `packaging/ml-images/pytorch-jupyter/launcher_recipes.json`
- 모델/migration: `backend/apps/containers/migrations/0015..0016`, `backend/apps/models_catalog/migrations/0004..0005`
- 서비스: `backend/apps/containers/services/deployment.py:_launcher_env_for_request`, `backend/apps/models_catalog/services.py:approve_model_upload_request`
- 베이스 이미지: `packaging/ml-images/pytorch-jupyter/{launch.py,start-jupyter.sh,Dockerfile,00-quickstart.ipynb}`
- 빌드: `packaging/ml-images/build-pytorch-jupyter.sh`
- wizard: `frontend/src/lib/components/UploadModelWizard.svelte`
- 새 컨테이너 모달: `frontend/src/lib/components/NewRequestModal.svelte`
- 사이드 패널 (요청 리스트): `frontend/src/routes/user/+page.svelte` `aside.side-panel`
- 사용자 카드: `frontend/src/routes/user/+page.svelte`
- admin 패널: `frontend/src/lib/components/admin/{Container,Model}RequestsPanel.svelte`
- 신규 모달: `frontend/src/lib/components/ModelRequestDetailModal.svelte`
- store: `frontend/src/lib/stores/user-header.ts`
- 테스트: `backend/apps/containers/tests/test_launcher_recipes.py`
- API 문서: `docs/api.md` (`/api/launcher-recipes/`, `open` `path` body param)
- 사용자 가이드: `docs/guides/multimodal-quickstart.md`
