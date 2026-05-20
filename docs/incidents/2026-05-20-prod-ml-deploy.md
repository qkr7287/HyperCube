# Incident — prod ML 컨테이너 첫 배포 디버깅 (2026-05-20)

prod fleet (41/63) 에서 Qwen2.5 0.5B ML 컨테이너를 처음 띄우는 과정에서 버그가
직렬로 터졌다. 최종적으로 41 (RTX 3090) 에서 동작 확인했으나, 그 과정에서
드러난 미해결 이슈들을 다른 세션이 후속 처리할 수 있도록 정리한다.

상태 범례: ✅ 해결 · 🔶 우회(근본 미해결) · ❌ 미해결

---

## 1. Web UI 안 들어가지던 버그

### 🔶 증상 A — "Invalid or expired workspace ticket"
- workspace open ticket TTL 이 60초. Web UI 버튼 클릭 → 새 탭 로드 사이 만료.
- 우회: `/api/workspaces/<cid>/open/` 로 새 ticket 발급 직후 즉시 navigate.
- **후속**: TTL 60초가 실사용에 너무 짧음. `workspace_ticket_ttl_seconds`
  (`backend/apps/containers/services/workspace.py`) 상향 (예 300초), 또는 프론트가
  Web UI 클릭 시점에 ticket 발급하도록.

### 🔶 증상 B — "Workspace upstream fetch failed" (502)
- 근본 원인: Qwen 템플릿 `network_policy=internal_only`. 이 모드는 backend 가
  컨테이너를 공유 docker internal network 의 DNS(컨테이너명)로 접근 → backend 와
  agent 가 **같은 docker daemon** 일 때만 동작 (63 dev). 41 의 컨테이너는 다른
  docker daemon 이라 63 backend 가 41 의 internal network 에 못 닿음.
- 우회: 템플릿 `network_policy` 를 `none` 으로 변경 → agent 가 host port publish →
  backend 가 `agent_ip:host_port` 로 fetch. 재배포 후 Web UI 정상.
- **후속**: 멀티호스트 fleet 에서 `internal_only` 정책은 backend 와 다른 호스트의
  컨테이너엔 구조적으로 불가. `workspace_upstream_endpoint`
  (`backend/apps/containers/services/workspace.py:87`) 가 cross-host 면 항상
  host-port 모드를 쓰도록, 또는 템플릿 생성 UI 에서 `network_policy` 노출 +
  멀티호스트 경고.

---

## 2. 41번에 신청하다 잘 안 됐던 이유 (실패 체인)

| # | 실패 | 원인 | 처리 | 상태 |
|---|------|------|------|------|
| a | Qwen 컨테이너 떴는데 모델 weight 없음 | **frontend race**: `NewRequestModal.selectTemplate()` 가 modelVersions API 응답 전 실행 → `selectedModelVersionIds` 필터가 전부 drop → 요청 `model_version_ids:[]` → prepare job 0건 | API 로 직접 재요청 | 🔶 |
| b | prepare job noop completed | agent `prepare_model_assets` 가 모델을 컨테이너 writable layer 에 받음 (agent compose 에 `/var/lib/hypercube-agent/model-cache` host bind 누락) | agent PR #23 — host mount 추가 | ✅ |
| c | "model cache path is missing verification manifest" | 이전 시도가 남긴 빈 `v1/` 디렉터리를 agent 가 "이미 prepared" 로 오판 | 빈 디렉터리 삭제 | 🔶 |
| d | prepare job preparing 12%/bytes_done:0 stuck | agent download 성공(파일 host 도착)했으나 **command_response 가 backend 에 도달 안 함** → `handle_prepare_response` 미발동 | Django shell 로 job 수동 READY 마크 | ❌ |
| e | request "GPU reservation timeout" | d 의 stuck 동안 GPU slice lease 만료 | request 재생성 | 🔶 |
| f | 41 deploy "image not present locally" | 41 에 `hypercube/ml-pytorch-jupyter:cuda12.4-airgap` 이미지 없음. airgap 정책 = 자동 pull 안 함 | 63→41 `docker save`/SFTP/`load` 로 6.8GB 이미지 전송 | 🔶 |
| g | Web UI 502 | 1-B (network_policy) | 템플릿 `network_policy=none` | 🔶 |

---

## 3. 63번에 했는데 잘 안 됐던 이유

### 🔶 CUDA OOM
- 첫 Qwen 을 server_63_prod 에 배포 → gradio 가 `torch.OutOfMemoryError`.
- RTX 3060 Ti 8GB 인데 dev 의 qwen25-custom 컨테이너가 **같은 물리 GPU** 의 7.66GB
  VRAM 점유 중. dev+prod 가 63 한 머신의 단일 GPU 를 공유 → prod Qwen 이 모델
  로드 실패.
- 우회: 41 (RTX 3090 24GB×2) 로 reschedule.
- **후속**: 단일 GPU 호스트에서 dev/prod 컨테이너가 같은 device 를 잡으면 OOM.
  GPU slice 예약이 dev/prod 격리 안 됨 — 같은 물리 GPU 를 dev 와 prod 가
  나눠 잡지 못하게 하거나, slice 예약 시 실제 VRAM 가용량 확인.

### ❌ server_63_dev agent 구 빌드
- dev 에서 Redis create 시 "workspace.port is required and must be a TCP port
  number" 로 거부.
- dev agent (`Dockerfile.dev`) 가 `--build` 재빌드 안 돼 구 코드 상태.
- 우회: server_41_dev 로 생성.
- **후속**: dev agent 들 `docker compose -f docker-compose.dev.yml up -d --build agent`
  로 재빌드 필요.

---

## 4. 시스템 차원 미해결 이슈 (별도 슬라이스 트래킹)

1. **❌ frontend race** — `NewRequestModal` 가 modelVersions 로드 전 select 가능 →
   `selectedModelVersionIds` 빈 채로 제출. 모달 진입을 로드 완료까지 막거나,
   제출 직전 템플릿 `default_model_version_ids` 재적용.
2. **❌ agent → backend prepare command_response 라우팅** —
   `_route_command_response` (`backend/apps/common/consumers.py:492`) 가 `__api__`
   채널일 때 `browser_channel.startswith("__")` 분기로 False 반환 → 그 후
   `_update_request_from_response` → `handle_prepare_response` 가 호출돼야
   함에도 prepare job 이 안 갱신됨. agent 가 command_response 를 실제로 emit
   하는지 / WS 라우팅이 끊기는지 공동 디버깅 필요. (agent dev 가 "별도 backend
   handler 버그" 로 인지)
3. **❌ prepare progress bytes_done 미누적** — agent 가 chunk 마다 progress emit
   한다는데 backend job 의 bytes_done 이 0 에서 안 올라감.
   `handle_prepare_progress` (`backend/apps/models_catalog/prepare.py:164`) 가
   받는 payload 의 `bytesDone`/`bytes_done` 키와 agent emit 키 일치 확인.
4. **❌ ML 이미지 fleet 배포 자동화 부재** — 새 prod 호스트 합류마다
   `docker save`/`load` 수동. GHCR pull 흐름 또는 airgap 이미지 배포 runbook 필요.
5. **❌ workspace ticket TTL 60초** — 1-A.
6. **❌ edgexpert-4cc8 (32번) agent 수동 갱신 남음** — GPU 없는 호스트라 현재
   영향 없음.

---

## 5. 오늘 가한 수동 개입 (재발 방지용 기록)

- prod `.env` `DJANGO_ALLOWED_HOSTS=*` (외부 IP 로그인 fix — 별도 commit 됨)
- Django shell: stuck prepare job (`e4084f5a`, `39a2e52d`) FAILED 마크 +
  cache MISSING 리셋
- Django shell: prepare job (`0260c8b9`, `7aedbe5b`) 수동 READY 마크
  (실제 파일 sha256 `6d45dae364a49ab67dfb1c063ff4215813f16202d02d8959ec7ba41dc7b5252c`
  검증 후)
- 빈 cache 디렉터리 `/var/lib/hypercube-agent/model-cache/qwen25-05b-instruct` 삭제
- 63→41 ML 이미지 전송 (`docker save` → paramiko SFTP → `docker load`)
- Qwen 템플릿 `network_policy` → `none` 패치
- prod 카탈로그 부트스트랩: Redis/Qwen 템플릿 + Qwen model-asset (`37fcc230`)
  / version (`ae839865`) 신규 등록

---

## 6. 최종 동작 상태

- **41 prod**: `qwen-prod-test` (RTX 3090 slice 2) — gradio Web UI 동작 확인.
- **63 prod**: `redis-prod-test`, `redis-prod-test-2` — Redis 정상.
- prod ML E2E (요청 → 승인 → prepare → deploy → Web UI) 는 41 위에서 완성.
  단 prepare 단계의 수동 READY 마크 (4-2) 가 자동화되기 전까지는 운영자 개입 필요.
