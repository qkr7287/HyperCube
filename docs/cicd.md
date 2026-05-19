# CI/CD 파이프라인

## 전체 흐름

```
HyperCube repo (qkr7287/HyperCube)
    │
    ├── 개발자가 dev 브랜치에서 작업 → push
    │
    ▼
dev (origin/dev)
    │
    ├── 검증 (npm run check + 백엔드 test) 후 dev → main PR 생성·머지
    │
    ▼
main (origin/main)
    │
    └── [자동] GitHub Actions
        ┌──────────────────────────────────────────┐
        │ build-push-images.yml (ubuntu-latest)    │
        │  backend / nginx 이미지 빌드 후 GHCR push │
        │  태그: latest + sha-<7chars>             │
        └────────────────┬─────────────────────────┘
                         │ workflow_run chain
                         ▼
        ┌──────────────────────────────────────────┐
        │ deploy-prod.yml                          │
        │  runs-on: [self-hosted, hc63-prod]       │
        │  cd /docker/hypercube-prod               │
        │  sed -i 's|IMAGE_TAG=.*|sha-<…>|' .env   │
        │  docker compose pull && up -d            │
        │  curl /api/health/ 24×5s wait            │
        └────────────────┬─────────────────────────┘
                         │
                         ▼
              http://192.168.0.63:37003/ 가용
```

## 워크플로우 파일

| 파일 | 트리거 | 결과 |
|---|---|---|
| `.github/workflows/build-push-images.yml` | main push, manual | GHCR `ghcr.io/qkr7287/hypercube-{backend,nginx}:{latest,sha-…}` |
| `.github/workflows/deploy-prod.yml` | "Build and push images" workflow_run, manual | 63번 prod 컨테이너 6개 (hcprod-*) 갱신 |
| `.github/workflows/publish-deploy-bundle.yml` | main push | `qkr7287/hypercube-deploy` 외부 배포 번들 — 현재 `DEPLOY_BUNDLE_PAT` secret 미설정이라 fail 한다 (deploy 흐름과 무관) |

## Self-hosted runner

| 라벨 | 호스트 | 역할 |
|---|---|---|
| `hc63-prod` | 63번 (`agics@192.168.0.63`) | prod 배포 |

위치: `/docker/actions-runner-hc63-prod/`
systemd 서비스: `actions.runner.qkr7287-HyperCube.hc63-prod-runner.service`

상태 확인:
```bash
ssh hc-dev-63
sudo systemctl status actions.runner.qkr7287-HyperCube.hc63-prod-runner.service
```

GitHub UI 에서도: repo → Settings → Actions → Runners → 라벨 `hc63-prod` (Status: Idle/Active).

## 수동 트리거

- 같은 commit 으로 재배포: GitHub Actions 탭 → "Deploy to 63 prod" → Run workflow → sha 빈칸 → Run.
- 특정 commit pin: sha 입력란에 7자 short SHA.
- 이미지만 다시 빌드: "Build and push images" → Run workflow.

## Rollback

```bash
ssh hc-dev-63
cd /docker/hypercube-prod
sed -i 's|^IMAGE_TAG=.*|IMAGE_TAG=sha-<이전7자>|' .env
docker compose pull
docker compose up -d
```
또는 GitHub Actions UI 의 "Deploy to 63 prod" 수동 실행에 이전 sha 지정.

## dev 는 이 흐름과 무관

dev 는 **mutagen sync** 로 로컬 Windows → 63번 코드 sync → bind-mount → uvicorn / Vite reload. GHCR 이미지 안 거치고 즉시 반영. 배포 워크플로우는 dev 무관.

## 비밀 (secrets)

| Secret | 어디서 쓰나 | 필수 여부 |
|---|---|---|
| `GITHUB_TOKEN` | build-push-images 가 GHCR 로그인 | auto (no action) |
| `DEPLOY_BUNDLE_PAT` | publish-deploy-bundle 가 외부 repo push | 선택 — 미설정 시 해당 workflow 만 fail |

prod 자체의 시크릿 (`DJANGO_SECRET_KEY`, `DB_PASSWORD` 등) 은 GitHub 에 없고
63번 `/docker/hypercube-prod/.env` 에만 존재. 자동 배포는 그 파일을 건드리지
않음 (IMAGE_TAG 한 줄만 sed). 시크릿 분실 위험 X.
