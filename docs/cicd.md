# CI/CD 파이프라인

## 전체 흐름

```
DCMTool_TS (dev)
    │
    ├── 개발자가 코드 작성 & commit & push
    │
    ▼
DCMTool_TS (dev → main PR)
    │
    ├── 개발자가 Pull Request 생성 & 리뷰 & merge
    │
    ▼
DCMTool_TS (main) ──── [자동] GitHub Actions ────▶ DCMTool (dev)
    │                   sync-to-dcmtool.yml           │
    │                   SSH deploy key 사용            │
    │                                                  │
    │                                          개발자가 PR 생성
    │                                          & merge
    │                                                  │
    │                                                  ▼
    │                                           DCMTool (main)
    │                                                  │
    │                                          [자동] GitHub Actions
    │                                          deploy.yml
    │                                          self-hosted runner
    │                                                  │
    │                                                  ▼
    │                                           16번 서버 (192.168.0.16)
    │                                           git pull + docker rebuild
    └──────────────────────────────────────────────────┘
```

## 단계별 설명

### 1단계: DCMTool_TS에서 개발 (수동)

- `dev` 브랜치에서 작업
- 완료 후 `dev → main` Pull Request 생성
- 리뷰 후 merge

### 2단계: DCMTool로 자동 동기화

- **트리거**: DCMTool_TS의 main 브랜치에 push 발생 시
- **워크플로우**: `.github/workflows/sync-to-dcmtool.yml`
- **동작**: DCMTool_TS main 코드를 `dev-agics/DCMTool` dev 브랜치에 force push
- **인증**: SSH deploy key (DEPLOY_KEY secret)

```yaml
# sync-to-dcmtool.yml 핵심 부분
on:
  push:
    branches: [main]

steps:
  - uses: webfactory/ssh-agent@v0.9.0
    with:
      ssh-private-key: ${{ secrets.DEPLOY_KEY }}
  - run: |
      git remote add dcmtool git@github.com:dev-agics/DCMTool.git
      git push dcmtool main:dev --force
```

### 3단계: DCMTool에서 배포 승인 (수동)

- `dev-agics/DCMTool`에서 `dev → main` Pull Request 생성
- 리뷰 후 merge

### 4단계: 16번 서버 자동 배포

- **트리거**: DCMTool의 main 브랜치에 push 발생 시
- **워크플로우**: `.github/workflows/deploy.yml`
- **실행 환경**: self-hosted runner (16번 서버에 설치됨)
- **동작**: git pull → docker compose down → docker compose up -d --build

```yaml
# deploy.yml 핵심 부분
on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: self-hosted
    steps:
      - run: |
          cd /home/agics-ai/docker/DCMTool
          git pull origin main
          docker compose down
          docker compose up -d --build
```

## Secrets 설정

### qkr7287/DCMTool_TS

| Secret | 용도 |
|--------|------|
| `DEPLOY_KEY` | SSH private key. dev-agics/DCMTool에 push할 때 사용 |

### dev-agics/DCMTool

| 설정 | 위치 |
|------|------|
| Deploy Key (public) | Settings > Deploy keys (write access 허용) |
| Self-hosted Runner | `/opt/actions-runner/dcmtool` (systemd 서비스로 등록) |

## Self-hosted Runner 정보

- **위치**: 192.168.0.16 서버의 `/opt/actions-runner/dcmtool`
- **서비스명**: `actions.runner.dev-agics-DCMTool.agicsai-desktop`
- **상태 확인**: `systemctl status actions.runner.dev-agics-DCMTool.agicsai-desktop`
- **재시작**: `systemctl restart actions.runner.dev-agics-DCMTool.agicsai-desktop`

## 문제 해결

### sync workflow 실패 시
1. `qkr7287/DCMTool_TS` > Settings > Secrets에서 `DEPLOY_KEY` 확인
2. `dev-agics/DCMTool` > Settings > Deploy keys에서 public key 확인 (write access)
3. GitHub Actions 탭에서 로그 확인 후 Re-run

### deploy workflow 실패 시
1. 16번 서버에서 runner 상태 확인: `systemctl status actions.runner.dev-agics-DCMTool.agicsai-desktop`
2. runner 재시작: `systemctl restart actions.runner.dev-agics-DCMTool.agicsai-desktop`
3. 수동 배포: 서버에서 `cd /home/agics-ai/docker/DCMTool && git pull origin main && docker compose up -d --build`
