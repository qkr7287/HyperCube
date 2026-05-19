# Multimodal Auto-Launch — Phase 2 Handoff

작성일: 2026-05-19
이전 세션 종료 커밋: (이 문서가 들어가는 커밋 직전까지)

## 큰 그림 (목표)

"ML Workspace = 사용자가 새 컨테이너 신청 → admin 승인 → 워크스페이스 클릭 → **이미 모델이 메모리에 떠있고 멀티모달 gradio UI가 동작 중**" 까지가 자동.

지금까지 ML Workspace는 컨테이너 + 모델 파일 마운트까지만 자동이고, 사용자가 직접 노트북 열어서 `tar -xzf`, `transformers.from_pretrained`, `gradio.launch` 3단계를 cell 실행해야 했음. 이 격차를 메우는 게 이 작업의 목적.

## Phase 1 (현재 commit으로 끝난 것)

Qwen2-VL-2B-Instruct **하나만** 동작하는 하드코딩 PoC. 일반화는 Phase 2.

### 1차에 들어간 것

| 영역 | 파일 | 무엇 |
|---|---|---|
| base image | `packaging/ml-images/pytorch-jupyter/requirements.txt` | `jupyter-server-proxy`, `transformers`, `accelerate`, `gradio`, `safetensors`, `sentencepiece`, `protobuf`, `pillow`, `qwen-vl-utils` 추가 |
| base image | `packaging/ml-images/pytorch-jupyter/start-jupyter.sh` | 시작 시 (a) `/workspace/models/*/*.tar.gz` 자동 추출 → `/workspace/<asset-slug>/`, (b) `00-quickstart.ipynb` 시드, (c) Qwen2-VL 디렉터리 감지 시 `launch_qwen2vl.py` 백그라운드 실행 |
| base image | `packaging/ml-images/pytorch-jupyter/launch_qwen2vl.py` | transformers로 Qwen2VLForConditionalGeneration 로드 + gradio.Interface를 127.0.0.1:7860 / `root_path=/proxy/7860` 으로 launch |
| base image | `packaging/ml-images/pytorch-jupyter/00-quickstart.ipynb` | 1 cell 노트북: 7860 ready 폴링 + `IFrame('proxy/7860/')` 임베드 |
| base image | `packaging/ml-images/pytorch-jupyter/Dockerfile` | launcher + notebook을 `/opt/hc/`에 복사, EXPOSE 7860 추가 |

### 1차의 한계 (Phase 2가 풀어야 할 것)

1. **모델 식별이 디렉터리명 하드코딩**: `start-jupyter.sh`가 `qwen2-vl-2b-instruct` 문자열로 분기. SmolVLM, LLaVA, Phi-3-Vision 등 추가 시 if-elif 늘어남.
2. **launcher가 모델 클래스 하드코딩**: `Qwen2VLForConditionalGeneration` 박혀 있음. 다른 VLM이면 별도 launcher 필요.
3. **wizard에서 inference recipe를 못 받음**: 사용자가 모델 등록할 때 "이 모델은 어떤 클래스로 로드하나" 정보를 안 받기 때문에, 새 모델 추가하려면 base image 빌드해야 함.
4. **UI가 자동 동작 사실을 모름**: 사용자 컨테이너 카드에는 여전히 "Jupyter 열기" 버튼만. gradio UI가 뜬다는 신호 없음.

## Phase 2 목표

> **임의의 멀티모달 / LLM 모델**을 wizard에서 등록하면 launcher가 자동으로 만들어져서, 같은 자동-기동 흐름이 작동.

핵심 디자인 한 줄: **inference recipe = `(model_class, processor_class, app_template)` 튜플을 wizard에서 선택**.

### 데이터 모델 변경 (backend)

| 모델 | 필드 | 변경 |
|---|---|---|
| `ContainerTemplate` | (신규) `launcher_recipe_id: str` | 어떤 recipe로 자동 기동하는지 (`qwen2-vl`, `llava-onevision`, `smolvlm`, `none` 등) |
| `ModelUploadRequest` | (신규) `launcher_recipe_id: str` | wizard 입력값. approve 시 ContainerTemplate으로 복사 |
| `ModelVersion.metadata` | recipe 메타 키 추가 (선택) | "model_class": "Qwen2VLForConditionalGeneration" 등을 참조용으로 |

migration: `containers/migrations/0015_template_launcher_recipe.py`, `models_catalog/migrations/0004_request_launcher_recipe.py`

### Recipe 카탈로그

새 위치 권장: `backend/apps/containers/launcher_recipes.py` (또는 별도 패키지).

```python
RECIPES = {
    "qwen2-vl": LauncherRecipe(
        id="qwen2-vl",
        label="Qwen2-VL (이미지+텍스트 chat)",
        model_class="Qwen2VLForConditionalGeneration",
        processor_class="AutoProcessor",
        input_kinds=["image", "text"],
        app_template="gradio_vlm_chat",  # template 1
        env={"TRUST_REMOTE_CODE": "false"},
    ),
    "llava-onevision": LauncherRecipe(
        id="llava-onevision",
        label="LLaVA-OneVision",
        model_class="LlavaOnevisionForConditionalGeneration",
        ...
    ),
    "auto-causal-lm": LauncherRecipe(
        id="auto-causal-lm",
        label="일반 텍스트 LLM (AutoModelForCausalLM)",
        ...
        app_template="gradio_text_chat",
    ),
    "none": LauncherRecipe(
        id="none",
        label="자동 실행 안 함 (사용자가 노트북에서 직접)",
        ...
    ),
}
```

처음엔 3~4개로 충분. wizard에서 카드로 보여줌.

### Launcher 일반화 (base image)

`launch_qwen2vl.py` → `launch.py` (generic):

```python
recipe_id = os.environ["HC_LAUNCHER_RECIPE"]
model_dir = os.environ["HC_MODEL_DIR"]
recipe = load_recipe(recipe_id)  # 위 카탈로그를 JSON으로 image 안에 박음
processor_cls = importlib.import_module("transformers").__dict__[recipe["processor_class"]]
model_cls = importlib.import_module("transformers").__dict__[recipe["model_class"]]
# ... app_template에 따라 gradio.Interface 만들기
```

`start-jupyter.sh`의 if-qwen2vl 분기 제거. 대신:

```bash
if [[ -n "${HC_LAUNCHER_RECIPE:-}" ]] && [[ "${HC_LAUNCHER_RECIPE}" != "none" ]]; then
    nohup python /opt/hc/launch.py ...
fi
```

`HC_LAUNCHER_RECIPE`, `HC_MODEL_DIR`는 컨테이너 생성 시 backend가 환경변수로 주입 (agent payload `env` 통해서).

### Agent payload 변경

`workspace_payload_for_request` 가 `env`에 recipe 정보 포함하도록 (이미 custom_env 흘러가니까 거의 작업 없음 — backend service에서 셋업만).

만약 agent 측에 새 명령이 필요하면 별도 GitHub Issue (`docs/agent-channel.md` 참고).

### Wizard UI 변경 (`frontend/src/lib/components/UploadModelWizard.svelte`)

현재 3-step wizard: 모델 정보 → 실행 환경(preset 1개) → 확인.

추가 step (또는 step 2 안에 sub-section):

**Step 2 안에 "추론 레시피" 선택**:

```
실행 환경: [● PyTorch + Jupyter Lab]    ← 기존
추론 레시피:                              ← 신규
  ○ Qwen2-VL (이미지+텍스트)
  ○ LLaVA-OneVision
  ○ 일반 텍스트 LLM
  ○ 자동 실행 안 함
```

선택값을 `launcher_recipe_id`로 POST. ModelUploadRequestSerializer / ContainerTemplateSerializer에 필드 추가 동반.

### NewRequestModal 변경 (frontend)

- 템플릿 카드에 recipe 배지 추가: 현재 `포함 모델: Qwen2-VL-2B` 옆에 `자동 실행: Qwen2-VL gradio` 한 줄.
- 작은 정보만 추가, 큰 구조 변경 없음.

### 사용자 컨테이너 카드 변경 (frontend `/user/+page.svelte`)

현재 "Jupyter 열기" 버튼만 있음. 자동 실행 모델 있으면 두 가지 옵션:

- (A) 버튼 라벨만 바꿈: `Jupyter` → `워크스페이스 (Qwen2-VL UI)` 같이
- (B) 두 버튼: `[gradio UI 열기]` + `[Jupyter 열기]`. 클릭 시 `/workspace/<wk>/proxy/7860/` 로 직접 이동
- 추천 (B). 사용자가 "AI 모델 빨리 써보고 싶음" 의도면 gradio가 일관성 있음, Jupyter는 개발자 의도용.

container 응답 직렬화에 `launcher_recipe_id` 노출 필요.

### Workspace proxy 변경 (선택)

현재 `/workspace/<wk>/lab` 만 우리 proxy가 처리하고, jupyter-server-proxy가 그 안에서 `/proxy/7860` 을 다시 처리하는 2-hop 구조. 잘 동작하면 그대로 둠.

만약 gradio 같은 multimodal UI를 *메인*으로 노출하고 싶으면 새 `workspace_kind="app"` 도입하고 우리 proxy가 7860으로 바로 라우팅. 이건 Phase 2 후반 또는 Phase 3로.

## 검증 시나리오 (Phase 2 끝났을 때)

1. user1이 wizard 열어서 **새 모델 (SmolVLM-256M)** 업로드 + 추론 레시피 "auto-causal-lm" 선택
2. admin 승인 → ContainerTemplate 자동 생성됨 (recipe 박혀 있음)
3. user1이 그 템플릿으로 컨테이너 신청
4. admin 승인 → 컨테이너 배포
5. 사용자 컨테이너 카드에 `[gradio UI 열기]` 버튼 노출
6. 클릭 → SmolVLM의 gradio UI 가 바로 뜸 (사용자가 셀 실행한 적 없음)
7. 이미지 업로드 + 한국어 응답 받음

같은 흐름이 Qwen2-VL / LLaVA-OneVision 어떤 모델에도 통해야 함.

## 작업 분량 추정

| 영역 | 작업 |
|---|---|
| backend (모델 + serializer + migration) | 2~3시간 |
| recipe 카탈로그 (3개 정도) | 2시간 |
| base image launcher 일반화 + 빌드 | 2시간 |
| wizard UI에 recipe 선택 | 1~2시간 |
| user 컨테이너 카드에 gradio 버튼 | 1시간 |
| Chrome E2E 검증 (모델 1개) | 1시간 |
| **총** | **한 세션 안에 가능** (집중하면) |

## 다음 세션 첫 5분 체크리스트

1. `git log --oneline -10` 해서 이 commit 위치 확인
2. `cat docs/multimodal-auto-launch-handoff.md` 다시 한 번 (이 문서)
3. ssh로 ops-flow-1 컨테이너 상태 확인 + gradio가 7860에 떠있는지 (`docker exec <id> ss -tlnp | grep 7860`)
4. 1차 PoC가 깨졌다면 먼저 그것부터 복구하고 시작 (한 번에 너무 많이 갈아엎지 말 것)

## 주의할 점 / 함정

- **Windows CRLF**: `packaging/ml-images/pytorch-jupyter/*.sh`가 mutagen sync로 63에 가면 CRLF로 변환되어 `set -o pipefail` 등이 깨짐. 빌드 전 `sed -i 's/\r$//' *.sh Dockerfile *.py *.ipynb` 한 번 돌리는 게 안전. (build 스크립트에 박는 게 더 깔끔)
- **agent model-cache mount**: `qkr7287/HyperCube-agent#18` 미해결. 모델 등록 후 컨테이너 생성 시 agent prepare가 호스트 mount path를 못 봐서 `docker cp` 우회를 손으로 해야 함. agent PR 머지될 때까지 dev 흐름은 이 우회 필요.
- **base image 빌드 시 외부 인터넷 필요**: dev 63은 PyPI 닿음. airgap 호스트에서는 미리 만들어둔 tar를 `docker load` 해야 함 (`docker save` 결과물이 `hypercube-ml-pytorch-jupyter-cuda12.4-airgap.tar`).
- **모델별 `trust_remote_code`**: Qwen2-VL은 transformers 4.45+ 에 정식 포함되어 trust_remote_code 불필요. 일부 모델 (예: 일부 InternVL 변형) 은 trust_remote_code=True 필요. recipe 메타에 toggle 두는 게 안전.
- **gradio root_path**: jupyter-server-proxy 뒤에서 동작하려면 `root_path='/proxy/7860'` 필수. 빠지면 static asset 경로가 깨짐.
- **HC_QWEN2VL_MODEL 환경변수**: 1차 PoC는 이 변수가 entrypoint에서 자동 세팅됨. Phase 2에서는 `HC_LAUNCHER_RECIPE` + `HC_MODEL_DIR` 로 일반화.

## 관련 파일 인덱스 (Phase 2 작업 시 자주 만질)

- 데이터 모델: `backend/apps/containers/models.py`, `backend/apps/models_catalog/models.py`
- 서비스: `backend/apps/models_catalog/services.py` (approve_model_upload_request → recipe 복사)
- 시리얼라이저: `backend/apps/containers/serializers.py`, `backend/apps/models_catalog/serializers.py`
- 에이전트 payload: `backend/apps/containers/services/workspace.py` (workspace_payload_for_request)
- 사용자 wizard: `frontend/src/lib/components/UploadModelWizard.svelte`
- preset 데이터: `frontend/src/lib/presets/model-presets.ts`
- 사용자 컨테이너 카드: `frontend/src/routes/user/+page.svelte`
- 새 요청 모달: `frontend/src/lib/components/NewRequestModal.svelte`
- base image: `packaging/ml-images/pytorch-jupyter/*`
- 빌드 스크립트: `packaging/ml-images/build-pytorch-jupyter.sh` (CRLF 이슈)
- 가이드: `docs/guides/multimodal-quickstart.md` (이전 사용자용 가이드, Phase 2 끝나면 갱신 필요)
