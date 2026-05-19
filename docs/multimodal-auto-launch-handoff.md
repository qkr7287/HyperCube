# Multimodal Auto-Launch — Phase 2 (in-progress) Handoff

마지막 갱신: 2026-05-19

## 큰 그림 (목표)

"ML Workspace = 사용자가 새 컨테이너 신청 → admin 승인 → 워크스페이스 클릭 → **이미 모델이 메모리에 떠있고 멀티모달 gradio UI가 동작 중**" 까지가 자동.

## Phase 1 (commit `b57dd07`)

Qwen2-VL-2B-Instruct **하나만** 동작하는 하드코딩 PoC. 베이스 이미지가 컨테이너 시작 시 `qwen2-vl-2b-instruct` 디렉터리 감지하면 `launch_qwen2vl.py` 백그라운드 실행 → `127.0.0.1:7860` gradio → `jupyter-server-proxy` 경유 `/proxy/7860/` 노출.

## Phase 2 (현재 세션)

핵심: **inference recipe = `(model_class, processor_class, app_template)` 튜플** 을 wizard에서 선택 → backend가 ContainerTemplate 에 박아둠 → agent 가 컨테이너 시작 시 `HC_LAUNCHER_RECIPE` 환경변수로 받음 → 베이스 이미지의 generic `launch.py` 가 recipe 카탈로그에서 클래스 lookup 후 gradio UI 띄움.

### 들어간 변경 (모두 dev 브랜치, push 대기)

| 영역 | 파일 | 무엇 |
|---|---|---|
| recipe 카탈로그 (backend) | `backend/apps/containers/launcher_recipes.py` | `LauncherRecipe` dataclass + `RECIPES` 4종 (`qwen2-vl`, `llava-onevision`, `auto-causal-lm`, `none`). `export_catalogue_json()` 로 JSON 직렬화 |
| data model | `backend/apps/containers/models.py`, `backend/apps/models_catalog/models.py` | `ContainerTemplate.launcher_recipe_id` + `ModelUploadRequest.launcher_recipe_id` (CharField max=64, default `"none"`) |
| migration | `containers/0015_template_launcher_recipe.py`, `models_catalog/0004_request_launcher_recipe.py` | AddField, dev에 적용 완료 |
| service | `backend/apps/models_catalog/services.py` | `approve_model_upload_request` 가 recipe id 를 새 ContainerTemplate 으로 복사 |
| service | `backend/apps/containers/services/deployment.py` | `_launcher_env_for_request()` — recipe != "none" + 모델 1개 이상 attached 면 `HC_LAUNCHER_RECIPE`, `HC_MODEL_DIR=/workspace/<asset-slug>`, `HC_GRADIO_PORT`, `HC_GRADIO_ROOT_PATH` env 주입 |
| serializer | `backend/apps/containers/serializers.py` | `ContainerTemplateSerializer.fields += launcher_recipe_id`. `MyContainerSerializer` 가 `created_via_request.template.launcher_recipe_id` 를 노출 (`/user` 페이지가 이걸로 버튼 분기) |
| serializer | `backend/apps/models_catalog/serializers.py` | `ModelUploadRequestSerializer.fields += launcher_recipe_id` |
| viewset | `backend/apps/containers/viewsets.py` | `LauncherRecipeListView` (GET `/api/launcher-recipes/`). 또 `WorkspaceViewSet.open` 이 `path` body param 받도록 — `"proxy/7860/"` 등 subpath 지정 가능 |
| urls | `backend/apps/containers/urls.py` | `launcher-recipes/` path 등록 |
| base image | `packaging/ml-images/pytorch-jupyter/launch.py` | **generic launcher** — `/opt/hc/launcher_recipes.json` 에서 recipe lookup, `importlib` 로 transformers 클래스 resolve, `gradio_vlm_chat` / `gradio_text_chat` 템플릿 디스패치 |
| base image | `packaging/ml-images/pytorch-jupyter/launcher_recipes.json` | recipe 카탈로그의 frozen mirror (drift guard는 backend 테스트가 책임) |
| base image | `packaging/ml-images/pytorch-jupyter/start-jupyter.sh` | qwen2-vl 디렉터리 감지 분기 **삭제**. 대신 `[[ "${HC_LAUNCHER_RECIPE:-none}" != "none" ]]` 면 `/opt/hc/launch.py` 백그라운드 실행 |
| base image | `packaging/ml-images/pytorch-jupyter/Dockerfile` | COPY `launch.py` + `launcher_recipes.json` 추가, 기존 `launch_qwen2vl.py` COPY 제거 |
| base image | `packaging/ml-images/pytorch-jupyter/launch_qwen2vl.py` | **삭제** (`launch.py` 가 일반화 대체) |
| base image | `packaging/ml-images/pytorch-jupyter/00-quickstart.ipynb` | recipe id 가 'none' 일 때 안내, 그 외에는 `HC_LAUNCHER_RECIPE` 변수명으로 동적 표기 |
| build script | `packaging/ml-images/build-pytorch-jupyter.sh` | (a) 빌드 전 `sed -i 's/\r$//'` 로 *.sh/Dockerfile/py/json/ipynb CRLF strip (b) `launcher_recipes.json` 을 backend `launcher_recipes.py` 에서 regenerate 후 build |
| wizard UI | `frontend/src/lib/components/UploadModelWizard.svelte` | step 2 에 "추론 레시피" 카드 그리드 추가. `/api/launcher-recipes/` 로 fetch, default `none`, summary 에 선택값 표시. submit 시 `launcher_recipe_id` form field 전송 |
| user 카드 | `frontend/src/routes/user/+page.svelte` | `MyContainer.launcher_recipe_id` 타입 추가. `hasAutoRecipe(c)` 도우미. recipe != `none` 컨테이너에 `[AI UI]` accent 버튼 추가 (Jupyter 버튼 좌측). `openWorkspace(c, e, 'proxy/7860/')` 가 backend 의 `path` body 와 합쳐 gradio URL 발급 |
| backend test | `backend/apps/containers/tests/test_launcher_recipes.py` | catalogue 형상 + env 주입 7 tests (1 skip = image JSON drift, 컨테이너에서는 packaging 폴더 안 보임) |
| docs | `docs/api.md` | `/api/launcher-recipes/`, `open` 의 `path` body param 명시 |

### 검증 결과 (이번 세션)

- `python manage.py migrate` — 0015, 0004 적용 완료 (dev `hc-backend`)
- `python manage.py test apps.containers.tests.test_launcher_recipes` — 7 tests OK (1 skipped)
- `python manage.py test apps.containers.tests.test_deployment apps.containers.tests.test_serializers` — 5 tests OK (regression 없음)
- `npm run check` (svelte-check) — 0 errors, 202 pre-existing warnings
- ops-flow-1 (560f94bf39ff) 컨테이너 안에서 gradio 7860 liveness 직접 확인은 SSH docker exec 가 sandbox 차단으로 미수행 — 이미지를 새로 빌드 + 컨테이너 재생성 시 검증

### 남은 작업 (다음 세션)

1. **베이스 이미지 빌드** — dev 63 에서 `bash packaging/ml-images/build-pytorch-jupyter.sh` 실행. 결과물 `hypercube/ml-pytorch-jupyter:cuda12.4-airgap` 태그 교체.
2. **기존 컨테이너 재배포** — ops-flow-1 (560f94bf39ff) 삭제 → 같은 템플릿으로 재신청. backend 가 새 env (`HC_LAUNCHER_RECIPE=qwen2-vl`, `HC_MODEL_DIR=/workspace/qwen2-vl-2b-instruct`) 주입, 새 베이스 이미지의 `launch.py` 가 받아 gradio 부팅.
3. **SmolVLM (또는 다른 VLM) E2E**:
   1. user1 wizard → 새 모델 등록 + recipe `auto-causal-lm` (또는 SmolVLM 전용 recipe 추가 — 아래 참고)
   2. admin approve → ContainerTemplate 자동 생성 (recipe 박혀 있음)
   3. user1 그 템플릿으로 컨테이너 신청 → admin approve → 배포
   4. user 카드에 `[AI UI]` 버튼 보이는지 → 클릭 → SmolVLM gradio 페이지 동작 확인 (이미지+한국어 응답)
4. **Chrome E2E 자동화** — `frontend/e2e/` 에 SmolVLM 시나리오 추가 (선택)
5. **재현 가이드 갱신** — `docs/guides/multimodal-quickstart.md` 가 아직 Phase 1 기준 → Phase 2 (recipe 카드 → 자동 실행) 으로 다시 쓰기
6. **SmolVLM 전용 recipe 추가** — SmolVLM 은 `Idefics3ForConditionalGeneration` 사용. 등록은 `launcher_recipes.py` + `launcher_recipes.json` 양쪽에 동일 entry 추가하면 됨 (drift guard 테스트가 어긋남 잡음)

### 함정 / 주의

- **`launcher_recipes.json` 은 source-of-truth 가 아님** — backend `launcher_recipes.py` 가 source. JSON 은 빌드 시 build script 가 regenerate. 수동 편집하면 drift guard 테스트가 image JSON 없는 환경에서는 skip 되어 잡지 못함. 로컬에서 검증하려면 host 에서 `python -c "from apps.containers.launcher_recipes import export_catalogue_json; print(export_catalogue_json())"` 결과를 JSON 과 비교.
- **agent #18 (model-cache mount)** 미해결 — 새 모델 (SmolVLM 등) 등록 후 컨테이너 생성 시 agent prepare 가 호스트 mount path 를 못 봐서 `docker cp` 우회를 손으로 해야 함. agent PR 머지될 때까지 dev 흐름은 이 우회 필요.
- **gradio root_path** — `/proxy/7860` 으로 두지 않으면 static asset 깨짐. backend 가 `HC_GRADIO_ROOT_PATH` 주입.
- **`HC_MODEL_DIR` 정확성** — `start-jupyter.sh` 가 tar 를 `/workspace/<asset-slug>/` 로 펼침. backend 는 `ModelVersion.asset.slug` 그대로 사용. 두 곳이 합의 안 되면 launcher 가 "model dir missing" 으로 죽음. 첫 번째 attached model 만 사용 (다중 모델 워크스페이스는 추후).
- **CRLF**: build script 가 sed strip 자동 수행. 수동 빌드시 잊지 말 것.
- **trust_remote_code** — recipe 메타에 toggle 있음. 일부 모델 (InternVL 변형 등) 은 True 필요.

### 파일 인덱스 (다음 세션 자주 만질)

- 카탈로그: `backend/apps/containers/launcher_recipes.py` ←→ `packaging/ml-images/pytorch-jupyter/launcher_recipes.json`
- 모델/migration: `backend/apps/containers/models.py:0015`, `backend/apps/models_catalog/models.py:0004`
- 서비스: `backend/apps/containers/services/deployment.py:_launcher_env_for_request`, `backend/apps/models_catalog/services.py:approve_model_upload_request`
- 에이전트 payload: `backend/apps/containers/services/deployment.py:_build_create_payload`
- 베이스 이미지: `packaging/ml-images/pytorch-jupyter/{launch.py,start-jupyter.sh,Dockerfile,00-quickstart.ipynb}`
- 빌드: `packaging/ml-images/build-pytorch-jupyter.sh`
- 사용자 wizard: `frontend/src/lib/components/UploadModelWizard.svelte`
- 사용자 카드: `frontend/src/routes/user/+page.svelte`
- 테스트: `backend/apps/containers/tests/test_launcher_recipes.py`
- API 문서: `docs/api.md` (Workspaces / 새 `launcher-recipes` 섹션)
