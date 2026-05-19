# Build & Test Report — 2026-05-13

대상: dev 서버 `192.168.0.63` / branch `dev` (HEAD `2521d5d`)
실행자: Claude (Opus 4.7) via `ssh hc-dev-63`
범위: backend 이미지 재빌드 → 서비스 기동 → Django check → 백엔드 테스트 71개 → 프론트 `svelte-check`

## 요약

| 단계 | 결과 | 비고 |
|------|------|------|
| `docker compose build backend celery-worker celery-beat migrate-watcher` | PASS | 모두 cache hit, 신규 layer 없음 |
| `docker compose up -d backend …` | PASS (재시도 1회) | 첫 기동 시 `models.E034` 로 unhealthy → 모델 수정 후 성공 |
| `manage.py check` | PASS | `System check identified no issues (0 silenced).` |
| `manage.py test apps.common apps.agents apps.containers apps.models_catalog -v 2` | PASS | 71/71 OK · 50.9s |
| `npm run check` (svelte-check) | PASS | **0 errors**, 189 warnings (29 files) |

## 발견한 회귀: `models.E034` (인덱스 이름 길이 초과)

`backend/apps/containers/models.py:423-424` — `ConsoleSession.Meta.indexes` 의 두 인덱스 이름이 33자였음 (Django 한도 30자).

```
ERRORS:
containers.ConsoleSession: (models.E034) The index name
  'console_ses_cont_id_opened_at_idx' cannot be longer than 30 characters.
containers.ConsoleSession: (models.E034) The index name
  'console_ses_user_id_opened_at_idx' cannot be longer than 30 characters.
```

이 체크 실패로 `hc-backend` 컨테이너가 healthcheck 통과 못 함 → `up -d` 가 `dependency failed to start` 로 종료.

### 조치
- `backend/apps/containers/models.py` : 이름 단축
  - `console_ses_user_id_opened_at_idx` → `console_ses_user_idx` (20자)
  - `console_ses_cont_id_opened_at_idx` → `console_ses_cont_idx` (20자)
- `backend/apps/containers/migrations/0004_consolesession.py` 도 동일하게 수정 (해당 migration 은 dev DB 에 이미 적용된 상태)

### 남은 follow-up (dev DB 한정)
- dev Postgres 의 실제 인덱스 이름은 여전히 길게 남아 있음 (`console_ses_cont_id_opened_at_idx`, `console_ses_user_id_opened_at_idx`).
- 런타임/테스트엔 영향 없음 (Django model state 와 DB 인덱스 이름은 직접 비교되지 않음).
- 권장: dev 환경에서 한 번 수동 rename 또는 `RenameIndex` migration 추가.
  ```sql
  ALTER INDEX console_ses_user_id_opened_at_idx RENAME TO console_ses_user_idx;
  ALTER INDEX console_ses_cont_id_opened_at_idx RENAME TO console_ses_cont_idx;
  ```
  (이번 세션에서 해당 ALTER 는 권한 거부로 미실행 — 사용자 확인 필요.)

Post-report update: `backend/apps/containers/migrations/0008_rename_consolesession_indexes.py` was added to perform this rename conditionally on PostgreSQL. After `manage.py migrate` applies 0008, the manual `ALTER INDEX` step should no longer be needed.

## Backend 테스트 결과 (71 tests, 50.9s, ALL PASS)

| 모듈 | 테스트 수 | 비고 |
|------|-----------|------|
| `apps.common.tests.test_middleware` | 4 | WebSocket auth subprotocol parsing |
| `apps.agents.tests.test_gpu_inventory` | 4 | GPU 인벤토리 upsert / stale / 실패 케이스 |
| `apps.agents.tests.test_serializers` | 3 | token read-only · 응답 노출 |
| `apps.agents.tests.test_viewsets` | 9 | register · idempotent · IP spoof 방지 등 |
| `apps.containers.tests.test_gpu_allocation` | 5 | 할당 lifecycle · 중복 reservation 차단 |
| `apps.containers.tests.test_serializers` | 2 | hostname · 필드 |
| `apps.containers.tests.test_template_and_request` | 20 | template / request CRUD · approval flow |
| `apps.containers.tests.test_viewsets` | 6 | 컨테이너 목록/단건/뷰어 권한/My* |
| `apps.containers.tests.test_workspaces` | 4 | one-time ticket · non-owner reject · approval dispatch |
| `apps.containers.tests.test_workspace_ws` | 4 | proxy URL · cookie · header sanitize · subprotocol strip |
| `apps.models_catalog.tests.test_model_catalog` | 4 | offline import · path traversal 방어 · 사적 자산 격리 |
| `apps.models_catalog.tests.test_model_prepare` | 6 | prepare → create 흐름 · cache status · alias |
| **합계** | **71** | |

### 비 PASS 사인 (참고용 경고)
- `UserWarning: No directory at: /app/staticfiles/` — staticfiles collect 안 된 상태에서 view 가 호출되며 발생. 테스트엔 무해, 운영 배포 직전 `collectstatic` 필요.

## Frontend svelte-check 결과

```
svelte-check found 0 errors and 189 warnings in 29 files
```

**Errors: 0.** TS / Svelte 타입 자체는 깨끗.

189건 warning 분포(대략):
- **Unused CSS selector**: 약 110건 (전체의 ~58%) — 대부분 컨테이너 상세 페이지(`/user/containers/[containerId]/+page.svelte`) 등 큰 페이지에서 더 이상 참조되지 않는 스타일.
- **A11y (a11y_no_static_element_interactions, a11y_click_events_have_key_events 등)**: 약 74건 — modal/overlay 의 `<div onclick=...>` 패턴 다수.
- 기타 (form label association 등): 소수.

### 권장
- a11y 이슈는 `<div>` → `<button>` 또는 `role` + key handler 추가로 정리.
- Unused CSS 는 대규모 리팩토링 시 함께 정리 (지금은 동작에 영향 없음).

## 결론

- 기동 블로커였던 `models.E034` 는 모델/마이그레이션 수정으로 해소되어 backend healthy.
- Backend test suite **71/71 PASS**, frontend type-check **0 errors**.
- 잔여 작업: (1) dev DB 인덱스 이름 rename(사용자 확인 필요), (2) frontend a11y / unused CSS 정리는 별도 리팩토링 트랙.
