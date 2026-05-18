# User Model Upload Flow Handoff

작성일: 2026-05-18

## 배경

사용자 페이지 구조를 단순화하는 중이었다.

목표 흐름:

1. 일반 사용자는 `/user`에 들어온다.
2. 사용자는 컨테이너 생성을 요청한다.
3. 승인되면 자기 컨테이너를 `/user` 대시보드와 `/user/containers`에서 관제한다.
4. 워크스페이스/Jupyter는 별도 메뉴가 아니라 자기 컨테이너의 액션으로 진입한다.
5. 일반 사용자의 모델 업로드는 직접 모델 카탈로그 등록이 아니라 “모델 등록 요청”으로 받는다.
6. 관리자가 모델 등록 요청을 승인하면 공유 모델 자산과 모델 버전이 생성되고, 이 모델을 기본 포함하는 컨테이너 템플릿이 생성된다.

사용자 피드백:

- `/user/workspaces`는 삭제.
- 일반 사용자용 `/user/models` 페이지도 삭제.
- 개인 모델 업로드는 요청만 만들고, 관리자가 승인하면 템플릿으로 등록.
- 자기 컨테이너 관제/제어 권한은 일반 사용자에게 있어야 함.
- 현재 가장 큰 불만: “user1이 신청했던 것도 다 날아간 것처럼 보인다.”

중요: 지금까지 확인한 변경/명령 기준으로 DB 삭제 명령, migration 실행, flush/reset, Docker Postgres 접속은 없었다. 다만 사용자 UI에서 모델 등록 요청 이력 확인 경로가 아직 없어서 “신청이 사라진 것처럼 보이는” 문제가 생겼을 가능성이 높다. 실제 dev DB는 반드시 조회해서 확인해야 한다.

## 현재 작업 상태

이미 구현된 부분:

- 사용자 상단 nav에서 `/user/workspaces`, `/user/models` 링크 제거.
- `frontend/src/routes/user/workspaces/+page.svelte` 삭제.
- `frontend/src/routes/user/models/+page.svelte` 삭제.
- `/user` 대시보드 hero에 `모델 등록 요청` 버튼 추가.
- `ModelUploadRequestModal.svelte` 추가. 브라우저 파일을 `multipart/form-data`로 `/api/model-upload-requests/`에 업로드한다.
- 백엔드에 `ModelUploadRequest` 모델/API/serializer/service/admin 추가.
- `/api/model-upload-requests/` 라우터 등록.
- 관리자 nav에 `모델 요청` 추가.
- `/admin/model-requests` 페이지 추가. 모델 업로드 요청 목록을 보고 승인/반려한다.
- 승인 시 `ModelAsset`, `ModelVersion`, `ContainerTemplate`을 생성하도록 서비스 구현.
- `ContainerTemplate.default_model_version_ids` 필드 추가.
- `NewRequestModal.svelte`에서 템플릿의 `default_model_version_ids`를 기본 선택하도록 연결.

현재 남은 핵심 문제:

- 일반 사용자가 자기가 올린 `ModelUploadRequest` 이력을 볼 UI가 없다.
- 그래서 `/user/models` 삭제 후 user1 입장에서는 모델 등록 신청이 사라진 것처럼 보일 수 있다.
- 먼저 `/user` 대시보드 안에 “모델 등록 요청 이력”을 붙여서 대기/승인/반려 상태, 파일명, 생성 템플릿명을 보여줘야 한다.
- 실제 user1의 기존 `ContainerRequest`와 `ModelUploadRequest`가 DB에 남아 있는지 dev DB에서 확인해야 한다.

## 변경된 파일

백엔드:

- `backend/apps/containers/models.py`
  - `ContainerTemplate.default_model_version_ids` 추가.
- `backend/apps/containers/serializers.py`
  - `ContainerTemplateSerializer`에 `default_model_version_ids` 추가.
- `backend/apps/containers/migrations/0013_template_default_models.py`
  - 신규 migration.
- `backend/apps/models_catalog/models.py`
  - `ModelUploadRequest` 모델 추가.
- `backend/apps/models_catalog/services.py`
  - `create_model_upload_request`
  - `approve_model_upload_request`
  - `reject_model_upload_request`
  - 업로드 파일 저장/이동 helpers 추가.
- `backend/apps/models_catalog/serializers.py`
  - `ModelUploadRequestSerializer`
  - `ModelUploadRequestReviewSerializer`
- `backend/apps/models_catalog/viewsets.py`
  - `ModelUploadRequestViewSet` 추가.
  - 일반 사용자는 shared model만 보도록 조정.
  - 모델 자산 생성/업로드/import는 admin only로 조정.
- `backend/apps/models_catalog/urls.py`
  - `model-upload-requests` router 등록.
- `backend/apps/models_catalog/admin.py`
  - `ModelUploadRequestAdmin` 추가.
- `backend/apps/models_catalog/migrations/0003_model_upload_request.py`
  - 신규 migration.
- `backend/apps/models_catalog/tests/test_model_catalog.py`
  - admin 직접 업로드 테스트, user 직접 업로드 금지 테스트, user 업로드 요청 승인 테스트 추가/변경.

프론트:

- `frontend/src/lib/components/ModelUploadRequestModal.svelte`
  - 신규 파일. 사용자 모델 파일 등록 요청 모달.
- `frontend/src/lib/components/NewRequestModal.svelte`
  - 템플릿 기본 모델 버전 자동 선택.
  - 템플릿 카드에 `모델 포함` badge 표시.
- `frontend/src/lib/components/AdminHeader.svelte`
  - `모델 요청` nav 추가.
- `frontend/src/routes/admin/model-requests/+page.svelte`
  - 신규 관리자 모델 요청 승인/반려 화면.
- `frontend/src/routes/user/+layout.svelte`
  - user nav를 `대시보드`, `내 컨테이너`로 축소.
- `frontend/src/routes/user/+page.svelte`
  - `모델 등록 요청` 버튼과 업로드 모달 연결.
- `frontend/src/routes/user/workspaces/+page.svelte`
  - 삭제.
- `frontend/src/routes/user/models/+page.svelte`
  - 삭제.

작업 전부터 있던 것으로 보이는 미추적 항목:

- `.agent-lvm-verify-20260516-1/`
- `.agent-remote-safe-pr-20260516/`
- `docs/gpu-ml-workspace-구현-요약.ko.html`

이 항목들은 이번 작업에서 만들거나 수정한 핵심 산출물이 아니므로 건드리지 말 것.

## 실행한 검증과 결과

통과:

```powershell
python -m compileall backend/apps/models_catalog backend/apps/containers
```

결과:

- `backend/apps/models_catalog`
- `backend/apps/containers`

두 경로의 Python compile이 통과했다.

통과:

```powershell
node -e "const fs=require('fs'); const svelte=require('svelte/compiler'); for (const f of ['src/lib/components/ModelUploadRequestModal.svelte','src/routes/admin/model-requests/+page.svelte','src/routes/user/+page.svelte','src/routes/user/+layout.svelte','src/lib/components/AdminHeader.svelte']) { const src=fs.readFileSync(f,'utf8'); svelte.compile(src,{filename:f,generate:false}); console.log('ok',f); }"
```

결과:

- 변경한 Svelte 파일 직접 parser compile은 모두 `ok`.

실패 또는 환경 문제:

```powershell
npm run check
```

결과:

- `esbuild spawn EPERM`
- 여러 Svelte 파일의 `<style>` preprocessing 단계에서 실패.
- repo 기존 환경에서 반복되는 Windows/esbuild spawn 문제로 보인다.

```powershell
python backend/manage.py test apps.models_catalog.tests.test_model_catalog
```

결과:

- `ModuleNotFoundError: No module named 'celery'`
- 로컬 Python 환경 dependency 부족으로 Django 초기화 실패.

```powershell
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

결과:

- Docker daemon 접속 실패.
- `npipe:////./pipe/dockerDesktopLinuxEngine` 없음.

주의:

- `npm run dev -- --host 127.0.0.1 --port 5173`를 foreground로 실행했다가 장시간 대기했고 사용자가 중단했다. 이 명령은 dev server라 정상적으로 계속 떠 있는 명령이다. 재실행 시 background로 띄우거나 기존 dev stack URL을 사용할 것.

## Claude Code가 먼저 해야 할 일

### P0. user1 신청 데이터가 실제로 남아 있는지 확인

실제 dev stack에서 Django shell로 확인한다. 로컬 Windows Python은 `celery`가 없어 실패하므로 Docker/dev server 환경에서 실행할 것.

예시:

```bash
python manage.py shell -c "
from django.contrib.auth import get_user_model
from apps.containers.models import ContainerRequest
from apps.models_catalog.models import ModelUploadRequest
User = get_user_model()
u = User.objects.filter(username='user1').first()
print('user1', u and u.id)
if u:
    print('container_requests', ContainerRequest.objects.filter(requester=u).count())
    print(list(ContainerRequest.objects.filter(requester=u).order_by('-created_at').values('id','action','status','custom_name','created_at')[:20]))
    print('model_upload_requests', ModelUploadRequest.objects.filter(requester=u).count())
    print(list(ModelUploadRequest.objects.filter(requester=u).order_by('-created_at').values('id','name','version','status','original_filename','created_template__name','created_at')[:20]))
"
```

확인 포인트:

- `ContainerRequest`가 없어졌는지, 단순히 UI에서 안 보이는지.
- `ModelUploadRequest`가 생성됐는지.
- user1이 보는 계정과 실제 requester가 일치하는지.

### P0. 사용자 대시보드에 모델 등록 요청 이력 추가

`frontend/src/routes/user/+page.svelte`에 다음을 추가한다.

- `/api/model-upload-requests/?page_size=20&ordering=-created_at` fetch.
- `modelUploadRequests` state.
- hero 또는 side panel에 `모델 등록 요청` 상태 요약.
- 요청 이력 영역 또는 별도 섹션에 다음 컬럼 표시:
  - 모델명
  - 버전
  - 파일명
  - 상태: 대기/승인/반려/실패
  - 생성 템플릿명
  - 제출일
  - 반려 사유
- 제출 성공 후 `load()` 또는 별도 `loadModelUploadRequests()`를 호출해서 즉시 보이게 한다.

이렇게 해야 `/user/models`를 삭제해도 사용자가 자기 신청이 어디 갔는지 알 수 있다.

### P0. API 응답 shape 확인

이 repo는 API 응답이 보통 `json.data.results` 구조다. `ModelUploadRequestViewSet` 응답도 같은 pagination wrapper로 내려오는지 실제 dev backend에서 확인한다.

예시:

```bash
curl -H "Authorization: Bearer <user1 token>" \
  "http://localhost:8000/api/model-upload-requests/?page_size=20&ordering=-created_at"
```

### P1. 관리자 승인 후 사용자 화면 반영 확인

관리자에서 `/admin/model-requests` 승인:

- shared `ModelAsset` 생성 확인.
- `ModelVersion` 생성 확인.
- `ContainerTemplate` 생성 확인.
- `ContainerTemplate.default_model_version_ids`에 승인된 version id가 들어갔는지 확인.
- user의 `새 요청` 모달에서 생성된 템플릿이 보이고, 모델 버전이 기본 선택되는지 확인.

### P1. migrations 실제 적용 확인

신규 migration:

- `backend/apps/containers/migrations/0013_template_default_models.py`
- `backend/apps/models_catalog/migrations/0003_model_upload_request.py`

dev stack에서:

```bash
python manage.py showmigrations containers models_catalog
python manage.py migrate --noinput
```

주의:

- `docker-compose.dev.yml`에는 `migrate-watcher`가 있어 migration 파일 변경 시 자동 적용될 수 있다.
- 하지만 실제 서버/stack 상태를 먼저 확인하고 실행한다.

### P2. UX 정리

- `/user`에서 “워크스페이스”라는 필터는 컨테이너 속성으로 유지 가능하다. 별도 페이지는 없음.
- 모델 등록 요청 버튼은 `+ 새 요청` 옆에 있으나, 사용자가 업로드 요청 후 이력이 바로 보이지 않으면 혼란스럽다. P0 이력 UI가 먼저다.
- `/admin/model-requests`는 현재 단순 테이블이다. 이후 detail modal이 있으면 좋지만 지금은 필수 아님.

## 주의해야 할 점

- user1 데이터가 없어졌다고 단정하지 말 것. 실제 DB 조회 전에는 “UI에서 안 보이는 문제”와 “DB 삭제”를 구분해야 한다.
- `git reset --hard`, `git checkout -- .`, DB flush/reset 금지.
- 기존 미추적 `.agent-*` 디렉터리와 `docs/gpu-ml-workspace-구현-요약.ko.html`는 이번 작업과 무관하므로 건드리지 말 것.
- 로컬 Windows Python은 dependency 부족으로 Django test가 안 돌 수 있다. backend container/dev server에서 검증할 것.
- `npm run dev`는 foreground로 실행하면 계속 대기한다. 백그라운드로 띄우거나 현재 dev stack의 frontend를 사용할 것.

## Claude Code용 실행 프롬프트

아래 프롬프트를 Claude Code에 그대로 넘겨도 된다.

```text
You are working in C:\Users\agics\Desktop\workspace\01. git\HyperCube.

Continue the user model upload flow refactor from docs/user-model-upload-claude-handoff.md.

Priority:
P0. Do not assume user1's requests were deleted. First verify the actual dev DB state for user1:
- ContainerRequest count/list
- ModelUploadRequest count/list
Use the running dev backend/container environment, not local Windows Python if it is missing celery.

P0. Fix the UI confusion:
- /user/workspaces and /user/models were intentionally removed.
- Add a model upload request history/status section to /user so normal users can see their own model registration requests after submitting.
- Fetch /api/model-upload-requests/?page_size=20&ordering=-created_at.
- Show model name, version, filename, status, created template name, created_at, and review_note.
- After ModelUploadRequestModal submit, refresh that list immediately.

P1. Validate the admin approval flow:
- /admin/model-requests approves/rejects model upload requests.
- Approval should create shared ModelAsset, ModelVersion, and an ML ContainerTemplate with default_model_version_ids set.
- Confirm the new template appears in NewRequestModal and auto-selects the approved model version.

Do not run destructive git or DB commands. Do not revert unrelated untracked .agent-* dirs or docs/gpu-ml-workspace-구현-요약.ko.html.

Report:
- exact files changed
- exact validation commands and results
- whether user1 data exists in DB or was only hidden by UI
- any remaining blockers
```
