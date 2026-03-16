# 시스템 아키텍처

## 전체 구성도

```
┌─────────────────────────────────────────────────────────────────┐
│                    개발자 PC (Windows)                           │
│                                                                 │
│   npm run dev (localhost:3334)                                  │
│       │                                                         │
│       ├── UI 렌더링 (SvelteKit dev server)                      │
│       └── API 요청 → hooks.server.ts → 192.168.0.16:3334 전달   │
└─────────────────────────────────────────────────────────────────┘
                              │
                         개발 완료 후
                         git push & PR
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    GitHub                                        │
│                                                                 │
│   qkr7287/DCMTool_TS (개인)  ──sync──▶  dev-agics/DCMTool (팀)  │
│   dev → main (PR)                       dev → main (PR)         │
└─────────────────────────────────────────────────────────────────┘
                                                    │
                                               자동 배포
                                          (self-hosted runner)
                                                    │
                                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│               192.168.0.16 (운영 서버, Ubuntu)                   │
│                                                                 │
│   ┌──────────────────────────────────────────────┐              │
│   │  nginx (port 7003)                           │              │
│   │    /dcmtool → http://localhost:3334           │              │
│   └──────────────┬───────────────────────────────┘              │
│                  │                                               │
│   ┌──────────────▼───────────────────────────────┐              │
│   │  Docker: dcm-frontend (port 3334)            │              │
│   │                                              │              │
│   │  node build (adapter-node)                   │              │
│   │    ├── UI 서빙 (SvelteKit SSR)               │              │
│   │    └── API 처리 (/api/*)                     │              │
│   │         ├── dockerode → Docker Engine API     │              │
│   │         └── procps/iproute2 → 시스템 정보     │              │
│   └──────────────────────────────────────────────┘              │
│                                                                 │
│   ┌──────────────────────────────────────────────┐              │
│   │  Docker Engine                               │              │
│   │    ├── 컨테이너 A (모니터링 대상)              │              │
│   │    ├── 컨테이너 B (모니터링 대상)              │              │
│   │    └── ...                                   │              │
│   └──────────────────────────────────────────────┘              │
│                                                                 │
│   ┌──────────────────────────────────────────────┐              │
│   │  Self-hosted Runner                          │              │
│   │  /opt/actions-runner/dcmtool                 │              │
│   │  (systemd 서비스로 상시 실행)                  │              │
│   └──────────────────────────────────────────────┘              │
└─────────────────────────────────────────────────────────────────┘
```

## 네트워크 구성

| 구성 요소 | 주소 | 포트 | 설명 |
|-----------|------|------|------|
| 개발 서버 | localhost | 3334 | npm run dev (로컬 개발용) |
| nginx | 192.168.0.16 | 7003 | 리버스 프록시 (여러 서비스 호스팅) |
| DCM 컨테이너 | 192.168.0.16 | 3334 | Docker 컨테이너 (운영) |
| Docker Engine | 192.168.0.16 | unix socket | /var/run/docker.sock |

## Docker 컨테이너 구성

### dcm-frontend

```yaml
# docker-compose.yml 주요 설정
services:
  dcm-frontend:
    build: .                           # 멀티스테이지 Dockerfile
    container_name: dcm-frontend
    ports:
      - "3334:3334"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro   # Docker API 접근
      - /proc:/host/proc:ro                            # 시스템 정보
      - /etc/hostname:/etc/hostname:ro                 # 호스트명
      - /var/run/utmp:/var/run/utmp:ro                 # 로그인 정보
    privileged: true                   # 시스템 정보 수집에 필요
    pid: host                          # 호스트 프로세스 목록 접근
    restart: unless-stopped
```

### Dockerfile (멀티스테이지 빌드)

```
Stage 1: builder
  - Node 20-alpine
  - npm ci → npm run build
  - SvelteKit adapter-node로 빌드

Stage 2: production
  - Node 20-alpine + 시스템 도구 (procps, iproute2, net-tools)
  - build/, package.json, node_modules 복사
  - CMD: node build (포트 3334)
```

## 개발 환경 vs 운영 환경

| 항목 | 개발 (npm run dev) | 운영 (Docker) |
|------|-------------------|---------------|
| 서버 | Vite dev server | node build (adapter-node) |
| API 데이터 | 192.168.0.16 프록시 (hooks.server.ts) | 자체 Docker 소켓 |
| 포트 | 3334 | 3334 |
| 접속 URL | http://localhost:3334 | http://192.168.0.16:3334 |
| HMR | 지원 | 미지원 |

## 데이터 흐름

```
브라우저 → GET /api/containers → SvelteKit API Route → dockerode → Docker Engine
                                                                        │
브라우저 ← JSON 응답 ← SvelteKit ← 컨테이너 목록/상태/메트릭 ←───────────┘
```

### API 엔드포인트 목록

- `GET /api/containers` - 전체 컨테이너 목록
- `GET /api/containers/[id]` - 컨테이너 상세 (inspect + stats)
- `GET /api/containers/[id]/metrics` - CPU, Memory, Network, Disk
- `GET /api/containers/[id]/logs` - 컨테이너 로그
- `POST /api/containers/[id]/control` - 컨테이너 제어 (start/stop/restart/...)
- `GET /api/system` - 시스템 정보
- `GET /api/system/network` - 네트워크 연결
- `GET /api/system/logins` - 로그인 사용자
- `GET /api/system/processes` - 프로세스 목록
- `GET /api/server/ip` - 서버 IP 정보
