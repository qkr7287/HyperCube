# Build & Test Follow-up Report — 2026-05-13 (2nd run)

대상: dev 서버 `192.168.0.63` / branch `dev`
실행자: Claude (Opus 4.7) via `ssh hc-dev-63`
직전 보고서: `docs/test-reports/2026-05-13-build-test.md`

이번 세션의 차이점
1. 1차 보고서에서 남겨둔 follow-up(`console_sessions` 인덱스 rename)을 `0008_rename_consolesession_indexes` 마이그레이션으로 처리 → 그 적용 확인.
2. `apps.containers.tests.test_policy` 가 새로 합류 → 1건 실패 발견 후 수정.
3. 전체 backend 테스트 재실행.

## 요약

| 단계 | 결과 | 비고 |
|------|------|------|
| `manage.py migrate` | PASS | `containers.0008_rename_consolesession_indexes` 적용 |
| `manage.py check` | PASS | `System check identified no issues (0 silenced).` |
| `test_policy + test_gpu_allocation` (좁은 범위) | **PASS, 11/11** · 8.3s | 1차 실행에서 `test_policy` 1건 실패 → 헬퍼 수정 후 재실행 PASS |
| `test apps.common apps.agents apps.containers apps.models_catalog` (전체) | **PASS, 77/77** · 55.6s | 직전 71건 + 신규 6건 (test_policy 5 + gpu_allocation 1) |

## 1) `migrate` — 0008 마이그레이션 적용

```
Applying containers.0008_rename_consolesession_indexes... OK
```

dev DB 인덱스 확인 (`\d console_sessions` 발췌):

```
Indexes:
    "console_sessions_pkey" PRIMARY KEY, btree (id)
    "console_ses_cont_idx" btree (container_id, opened_at DESC)
    "console_ses_user_idx" btree (user_id, opened_at DESC)
    ...
```

→ 1차 보고서에서 남았던 옛 인덱스 이름 (`console_ses_cont_id_opened_at_idx` / `console_ses_user_id_opened_at_idx`) 이 새 이름으로 변경됨. 잔여 follow-up 종결.

## 2) `manage.py check`

```
System check identified no issues (0 silenced).
```

## 3) 좁은 범위 테스트 (`test_policy` + `test_gpu_allocation`)

### 1차 시도 — 1 ERROR

```
FAILED (errors=1)
```

```
ERROR: test_approval_rejects_active_gpu_quota_exceeded
  (apps.containers.tests.test_policy.WorkspacePolicyAPITest)
django.db.utils.IntegrityError:
  duplicate key value violates unique constraint
  "agents_gpudevice_agent_id_index_85318233_uniq"
DETAIL: Key (agent_id, index)=(..., 0) already exists.
```

### 원인

`backend/apps/containers/tests/test_policy.py:11-20` 의 헬퍼가 항상 `index=0` 으로 `GpuDevice` 를 생성하는데, 같은 테스트가 동일 agent 에 대해 헬퍼를 두 번 호출(`setUp` 의 `self.slice` + 본문의 `other_slice`)함. `GpuDevice` 의 `unique_together = [("agent", "index")]` 제약과 충돌.

### 조치

`backend/apps/containers/tests/test_policy.py`:

```python
def create_gpu_slice(agent, device_id="GPU-policy", index=None):
    if index is None:
        index = GpuDevice.objects.filter(agent=agent).count()
    gpu = GpuDevice.objects.create(
        agent=agent,
        index=index,
        ...
    )
```

`index` 를 명시하지 않으면 해당 agent 의 기존 GpuDevice 개수로 자동 부여 → 호출이 반복돼도 unique 충돌 없음.

### 2차 시도 — PASS

```
Ran 11 tests in 8.290s
OK
```

| 테스트 | 결과 |
|--------|------|
| test_approval_rejects_active_gpu_quota_exceeded | ok |
| test_approval_rejects_active_workspace_quota_exceeded | ok |
| test_runtime_request_cannot_exceed_policy_limit | ok |
| test_shared_gpu_request_is_rejected_when_shared_mode_disabled | ok |
| test_template_default_runtime_cannot_exceed_policy_limit | ok |
| test_allocation_lifecycle_helpers_activate_fail_and_cleanup | ok |
| test_approve_reserves_gpu_and_dispatches_create_payload | ok |
| test_request_create_writes_gpu_slice_selection_rows | ok |
| test_request_rejects_gpu_slice_from_different_agent | ok |
| test_second_exclusive_approval_for_same_slice_is_rejected | ok |
| test_shared_approval_allows_same_shareable_slice | ok |

## 4) 전체 backend 테스트 (`apps.common apps.agents apps.containers apps.models_catalog`)

```
Ran 77 tests in 55.577s
OK
```

| 모듈 | 테스트 수 | 비고 |
|------|-----------|------|
| `apps.common.tests.test_middleware` | 4 | WebSocket auth subprotocol parsing |
| `apps.agents.tests.test_gpu_inventory` | 4 | upsert / stale / 실패 |
| `apps.agents.tests.test_serializers` | 3 | token read-only · 응답 노출 |
| `apps.agents.tests.test_viewsets` | 9 | register · IP spoof 방지 |
| `apps.containers.tests.test_gpu_allocation` | 6 | 할당 lifecycle · shared / exclusive |
| `apps.containers.tests.test_policy` | 5 | quota · runtime · shared GPU 정책 |
| `apps.containers.tests.test_serializers` | 2 | hostname · 필드 |
| `apps.containers.tests.test_template_and_request` | 20 | template / request CRUD · approval |
| `apps.containers.tests.test_viewsets` | 6 | 컨테이너 목록 · 단건 · 권한 · My* |
| `apps.containers.tests.test_workspaces` | 4 | one-time ticket · 비소유자 거부 |
| `apps.containers.tests.test_workspace_ws` | 4 | proxy URL · cookie · header · subprotocol |
| `apps.models_catalog.tests.test_model_catalog` | 4 | offline import · path traversal · 사적 자산 |
| `apps.models_catalog.tests.test_model_prepare` | 6 | prepare → create · cache status · alias |
| **합계** | **77** | (1차 보고서 대비 +6: test_policy 5 + gpu_allocation 의 신규 1건) |

### 참고용 경고
- `UserWarning: No directory at: /app/staticfiles/` — 테스트엔 무해. 운영 배포 직전 `collectstatic` 필요.

## 결론

- 인덱스 rename follow-up 종결 (`0008` 적용 확인).
- `test_policy` 헬퍼 버그(`index=0` 고정으로 인한 `unique_together` 위반) 수정.
- 최종 상태: **migrate OK · check OK · 77/77 PASS · 55.6s**.

### 변경된 파일

- `backend/apps/containers/tests/test_policy.py` — `create_gpu_slice` 헬퍼에 `index` 자동 부여.
