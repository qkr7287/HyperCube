# HyperCube - Server & Container Monitoring Platform

> **IMPORTANT: main 브랜치에 직접 push하지 마세요!**
>
> 이 프로젝트는 CI/CD 자동화가 구성되어 있습니다.
> main 브랜치에 push되면 **운영 서버(192.168.0.16)에 자동 배포**됩니다.
> 반드시 `dev` 브랜치에서 작업한 뒤 **Pull Request**를 통해 main에 병합하세요.

---

Docker 컨테이너를 실시간으로 모니터링하는 웹 대시보드입니다.
3D 토폴로지 시각화, 컨테이너 제어, 시스템 리소스 모니터링 기능을 제공합니다.

## 주요 기능

- **3D 토폴로지 뷰**: 프로젝트별 컨테이너 그룹을 3D Force Graph로 시각화
- **실시간 모니터링**: 5초 간격 자동 갱신 (CPU, Memory, Network, Disk I/O)
- **컨테이너 제어**: 시작, 중지, 재시작, 일시정지, 삭제
- **GROUP/LIST 뷰**: 프로젝트 카드 뷰와 테이블 리스트 뷰 전환
- **시스템 정보**: 네트워크 연결, 로그인 사용자, 프로세스 현황
- **스크린샷**: 대시보드 전체 화면 캡처

## 기술 스택

| 구분 | 기술 |
|------|------|
| Frontend | SvelteKit 2.22 + Svelte 5 (runes mode) |
| Backend | SvelteKit API Routes + dockerode |
| 3D 시각화 | 3d-force-graph + Three.js |
| 차트 | Chart.js |
| 빌드 | Vite 7 + adapter-node |
| 배포 | Docker + GitHub Actions |

## 빠른 시작

```bash
# 의존성 설치
npm install

# 개발 서버 실행 (192.168.0.16 서버 API를 프록시)
npm run dev
# -> http://localhost:3334

# 프로덕션 빌드
npm run build
```

## 프로젝트 구조

```
DCMTool_TS/
├── src/
│   ├── hooks.server.ts              # dev 모드 API 프록시
│   ├── routes/
│   │   ├── +page.svelte             # 메인 대시보드
│   │   └── api/                     # REST API 엔드포인트
│   │       ├── containers/          # 컨테이너 CRUD
│   │       ├── system/              # 시스템 정보
│   │       └── server/              # 서버 정보
│   └── lib/
│       ├── components/              # UI 컴포넌트 (10개)
│       └── assets/icons/            # SVG 아이콘
├── Dockerfile                       # 멀티스테이지 빌드
├── docker-compose.yml               # Docker 배포 설정
└── .github/workflows/               # CI/CD 파이프라인
```

## 문서

| 문서 | 설명 |
|------|------|
| [CI/CD 파이프라인](docs/cicd.md) | 전체 배포 자동화 흐름, GitHub Actions 설정 |
| [시스템 아키텍처](docs/architecture.md) | 인프라 구성, 네트워크, Docker 설정 |
| [API 명세](docs/api.md) | REST API 엔드포인트 상세 |
| [개발 가이드](docs/development.md) | 로컬 개발 환경, 브랜치 전략, 커밋 규칙 |

## 저장소 구조

| 저장소 | 용도 |
|--------|------|
| `qkr7287/DCMTool_TS` | 개인 개발 저장소 (이 저장소) |
| `dev-agics/DCMTool` | 팀 배포 저장소 (운영 서버 연결) |

## 라이선스

MIT License
