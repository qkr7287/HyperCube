# 63번 prod 세팅 절차

작성일: 2026-05-19
목적: 63번 서버에 dev 와 함께 prod stack 띄우고, main push 시 자동 배포.

## 충돌 회피 설계

| 항목 | dev | prod |
|---|---|---|
| Compose project | `hypercube` | `hypercube-prod` |
| Container name | `hc-postgres`, `hc-backend`, ... | `hcprod-postgres`, `hcprod-backend`, ... |
| Source 위치 | `/home/agics/ts/HyperCube` (mutagen sync) | `/home/agics/docker/hypercube-prod` (image-only) |
| 포트 노출 | frontend 33000 / backend 38000 / pg 35432 / redis 36379 | nginx **37003** (단일) |
| 네트워크 | `hc-network` (project-scoped) + `hc-ml-internal` (external 공유) | 동일 — external `hc-ml-internal` 만 공유 |
| GHCR image | (build 안 함, source bind-mount) | `ghcr.io/qkr7287/hypercube-{backend,nginx}:latest` |

→ container_name 이 `hc-` (dev) vs `hcprod-` (prod) 라 `docker ps` 에서 즉시 구분.

## 1. 한 번만 — prod 디렉터리 + .env

이미 `/home/agics/docker/hypercube-prod/{docker-compose.yml,.env}` 가 복사돼 있다. .env 를 실제 값으로 채워야 함:

```bash
ssh hc-dev-63
cd /home/agics/docker/hypercube-prod
# secret 생성:
python3 -c "import secrets; print(secrets.token_urlsafe(50))"   # → DJANGO_SECRET_KEY 에 붙여넣기
python3 -c "import secrets; print(secrets.token_urlsafe(24))"   # → DB_PASSWORD 에 붙여넣기
# 편집:
nano .env
```

필수 값:
```env
IMAGE_TAG=latest
HC_PORT=37003
DJANGO_SECRET_KEY=<위 50바이트 값>
DJANGO_ALLOWED_HOSTS=192.168.0.63,localhost
CORS_ALLOWED_ORIGINS=http://192.168.0.63:37003
CSRF_TRUSTED_ORIGINS=http://192.168.0.63:37003
DB_NAME=hypercube
DB_USER=hypercube
DB_PASSWORD=<위 24바이트 값>
```

## 2. 한 번만 — GitHub self-hosted runner (label `hc63-prod`)

GitHub repo settings → Settings → Actions → Runners → "New self-hosted runner" → Linux x64 → 표시되는 명령어를 63번에서 실행:

```bash
ssh hc-dev-63
mkdir -p /home/agics/actions-runner-hc63-prod && cd /home/agics/actions-runner-hc63-prod
# GitHub 화면에 표시되는 ./config.sh ... 명령 그대로 실행
# 설정 중 "labels" 물어볼 때 hc63-prod 입력
./config.sh --url https://github.com/qkr7287/HyperCube \
            --token <GITHUB이 발급한 토큰> \
            --labels hc63-prod \
            --name hc63-prod-runner \
            --unattended
# systemd 서비스로 등록 (재부팅 후 자동 시작):
sudo ./svc.sh install agics
sudo ./svc.sh start
```

확인: GitHub repo → Settings → Actions → Runners 에 `hc63-prod-runner` (status Idle / labels hc63-prod) 나오면 OK.

## 3. 첫 배포 (수동)

main 에 머지된 직후, GitHub Actions 탭 → "Deploy to 63 prod" → Run workflow → 그냥 Run.

또는 수동으로 63에서:

```bash
cd /home/agics/docker/hypercube-prod
docker compose pull
docker compose up -d
docker ps --filter "name=hcprod-"   # hcprod-postgres hcprod-redis hcprod-backend hcprod-celery-* hcprod-nginx 다 Up
curl -sf http://localhost:37003/api/health/   # 200 OK
```

브라우저: `http://192.168.0.63:37003/`

## 4. 이후 — 자동

main 에 push (또는 PR 머지) → `Build and push images` workflow 가 GHCR 에
새 image push → `Deploy to 63 prod` workflow 가 트리거되어 63번에서:
1. `.env` 의 `IMAGE_TAG=sha-<short>` 갱신
2. `docker compose pull && up -d`
3. `/api/health/` 200 응답 대기 (24회 × 5초)
4. migration log tail 출력

## 5. dev 와 함께 운영 시 주의

- `docker compose down` 할 때 **반드시 디렉터리를 명시**:
  - dev: `cd /home/agics/ts/HyperCube && docker compose -f docker-compose.yml -f docker-compose.dev.yml --env-file .env.dev down`
  - prod: `cd /home/agics/docker/hypercube-prod && docker compose down`
  - 둘은 다른 compose project 라 한쪽 명령이 다른 쪽 영향 X.
- prod 컨테이너는 `hcprod-*` prefix 라 dev 의 `hc-*` 와 절대 충돌 X.
- `hc-ml-internal` 네트워크는 공유 — agent / 사용자 workspace 컨테이너가 둘 다 reach 가능.

## 6. 트러블슈팅

| 증상 | 원인 | 조치 |
|---|---|---|
| `Deploy to 63 prod` 가 "no runner available" | hc63-prod runner 안 떠있음 | `sudo ./svc.sh status` (63에서) — Stop 이면 `start` |
| backend 가 unhealthy | DB_PASSWORD 잘못, migration 실패 | `docker logs hcprod-backend --tail 80` |
| 37003 :: bind already in use | 다른 서비스가 37003 쓰는 중 | `HC_PORT=37004` 등으로 변경 |
| `docker compose pull` 401/403 | GHCR pull 권한 | `docker login ghcr.io -u <user> -p <PAT>` (한 번) |

## 참조

- workflow: `.github/workflows/deploy-prod.yml`
- compose: `deploy/docker-compose.yml`
- 포트 정책: `docs/handoffs/agent-port-update.md`
