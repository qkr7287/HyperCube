---
last-synced-commit: 36a827e
source-of-truth: .github/workflows/deploy-prod.yml
verify: gh workflow view deploy-prod.yml
---

# Deploy Runbook (16번 prod)

## 인프라 구조

| 환경 | 서버 | 방식 | 접속 |
|------|------|------|------|
| 개발 | 로컬 | Docker Compose, bind-mount + uvicorn --reload | `localhost:3000` |
| 운영 | 192.168.0.16 | GHCR pre-built image pull, self-hosted runner | `http://192.168.0.16:3334/hypercube` |

## 운영 배포 — 표준 절차

**현행: dev → main 머지만 하면 자동 배포 (`deploy-prod.yml`).**

```bash
# 1. dev → main PR
gh pr create --base main --head dev --title "..."
gh pr merge <num> --merge

# 자동 동작:
# - "Build and push images" workflow → GHCR에 sha-<7chars> + latest 태그 push (~3분)
# - "Deploy to 16 prod" workflow → 16번 self-hosted runner (label: hc16-prod)
#   /home/agics-ai/docker/hypercube .env의 IMAGE_TAG 갱신
#   docker compose pull && up -d
#   Health check (curl http://localhost:3334/hypercube/) 통과 시 success
```

## 수동 redeploy / 특정 SHA pin

```bash
# 특정 commit으로 pin
gh workflow run deploy-prod.yml -f sha=14e92fa

# 또는 GitHub Actions UI → "Deploy to 16 prod" → Run workflow
```

## Migration

Backend container entrypoint가 자동 처리: `manage.py migrate --noinput`

## Health Check

- URL: `http://192.168.0.16:3334/hypercube/`
- workflow가 24회 × 5초 (총 2분) 폴링
- 실패 시 backend 로그 80줄 + migration 로그 30줄 자동 출력

## prod 배포 정보

| 항목 | 값 |
|------|-----|
| prod 폴더 (16번) | `/home/agics-ai/docker/hypercube` |
| 외부 포트 | 3334 (HC_PORT) |
| 컨테이너 내부 포트 | 7003 |
| Backend image | `ghcr.io/qkr7287/hypercube-backend` |
| Nginx image | `ghcr.io/qkr7287/hypercube-nginx` |
| Tag 형식 | `sha-<7chars>` (commit pin 권장) 또는 `latest` |

## 16번 self-hosted runner 운영

- 위치: `/home/agics-ai/actions-runner-hypercube/` (가칭, 실제 경로 확인 필요)
- 등록: `qkr7287/HyperCube` repo, label `self-hosted, hc16-prod`
- systemd: `actions.runner.qkr7287-HyperCube.<runner-name>.service` (자동시작)

### offline 복구
```bash
sudo systemctl start actions.runner.qkr7287-HyperCube.<name>
sudo systemctl status actions.runner.qkr7287-HyperCube.<name>
```

## Repo 정보

- **HyperCube** (`qkr7287/HyperCube`): 작업 + 배포 single source of truth
- **DCMTool** (`dev-agics/DCMTool`): **deprecated**. 과거 자동 sync 흔적은 모두 무시

### 금지 사항
- `dev-agics/DCMTool`의 `sync-to-dcmtool.yml` / `deploy.yml` 경로는 **사용 금지**
- 구식 chain (HyperCube main → DCMTool dev/main → self-hosted runner) 폐지
- DCMTool 측 잔여 workflow / runner 등록은 무시

## Secret / Server 접속

- 16번 SSH: `ssh -i ~/.ssh/dcmtool_sync -p 2022 root@192.168.0.16`
- prod superuser: `admin / admin1234` (개발 DB와 동일 — prod 변경 권장)

## 변경 시 절차

이 파일은 다음 변경 시 동기화 필요:
- `.github/workflows/deploy-prod.yml` 수정
- `docker-compose*.yml` prod 관련 변경
- 16번 서버 인프라 (포트, 경로, runner) 변경

frontmatter `last-synced-commit`을 현재 HEAD로 갱신하고 `verify` 실행.
