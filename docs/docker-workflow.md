# Docker 개발 & 배포 워크플로우

> HyperCube 프로젝트의 Docker 기반 개발/배포 흐름을 정리한 문서.

---

## 1. 핵심 개념

### 볼륨 마운트 (개발)

로컬 디렉토리를 컨테이너 내부 경로에 연결하는 방식.

```
로컬 PC                    Docker 컨테이너
./backend/src/app.py  ←→  /app/src/app.py   (같은 파일)
```

- 컨테이너는 **계속 실행 중** (재시작 없음)
- 로컬에서 파일 수정 → 컨테이너 내부에서도 즉시 반영
- Django `runserver` / Vite `dev`가 변경 감지 → **자동 리로드**

### 이미지 빌드 (배포)

Dockerfile의 `COPY`로 코드를 이미지 안에 고정 복사.

```
Dockerfile: COPY ./backend /app  →  이미지에 코드가 포함됨
```

- 코드가 이미지에 포함되므로 별도 마운트 불필요
- 이미지 버전 = 코드 버전 (재현 가능)

---

## 2. 개발 vs 배포 비교

| 항목 | 개발 (dev) | 배포 (prod) |
|------|-----------|------------|
| 코드 반영 | 볼륨 마운트 (실시간) | 이미지에 COPY (고정) |
| 서버 실행 | dev 서버 (핫리로드) | 빌드된 결과물 실행 |
| 코드 수정 시 | 자동 반영, 컨테이너 유지 | 이미지 재빌드 필요 |
| DB/Redis | 동일 | 동일 |
| 성능 | 개발 편의 우선 | 최적화 우선 |

---

## 3. Compose 파일 구조

개발/배포 설정을 분리하기 위해 override 패턴을 사용한다.

```
docker-compose.yml          # 공통 설정 (서비스 정의, 네트워크, DB/Redis)
docker-compose.dev.yml      # 개발 override (볼륨 마운트, dev 서버 명령)
docker-compose.prod.yml     # 배포 override (빌드 설정, prod 명령)
```

### 실행 명령

```bash
# 개발 환경
docker compose -f docker-compose.yml -f docker-compose.dev.yml up

# 배포 환경
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

### 예시: 공통 (docker-compose.yml)

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg16
    volumes:
      - postgres_data:/var/lib/postgresql/data
    environment:
      POSTGRES_DB: hypercube
      POSTGRES_USER: hypercube
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    ports:
      - "35432:5432"   # host:container — default 35432 ("3" prefix 로 충돌 회피)

  redis:
    image: redis:7-alpine
    ports:
      - "36379:6379"

  backend:
    depends_on:
      - postgres
      - redis
    environment:
      DATABASE_URL: postgres://hypercube:${DB_PASSWORD}@postgres:5432/hypercube
      REDIS_URL: redis://redis:6379/0

volumes:
  postgres_data:
```

### 예시: 개발 override (docker-compose.dev.yml)

```yaml
services:
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile.dev
    volumes:
      - ./backend:/app          # 소스 코드 마운트 (핫리로드)
    command: python manage.py runserver 0.0.0.0:8000
    ports:
      - "38000:8000"   # host:container
```

### 예시: 배포 override (docker-compose.prod.yml)

```yaml
services:
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    command: uvicorn config.asgi:application --host 0.0.0.0 --port 8000
    # backend 는 prod 에서 외부로 직접 노출하지 않음.
    # nginx 컨테이너(host port 37003) 가 reverse proxy.
```

---

## 4. 컨테이너 재시작이 필요한 경우

일반적인 코드 수정은 핫리로드로 처리되지만, 다음 경우에는 컨테이너 재빌드가 필요하다.

| 변경 사항 | 필요한 명령 |
|----------|-----------|
| Python/Node 소스 코드 수정 | 불필요 (자동 리로드) |
| HTML/CSS/Svelte 수정 | 불필요 (자동 리로드) |
| `requirements.txt` 변경 | `docker compose up --build` |
| `package.json` 변경 | `docker compose up --build` |
| `Dockerfile` 변경 | `docker compose up --build` |
| `docker-compose.yml` 변경 | `docker compose up -d` |
| 환경 변수 (`.env`) 변경 | `docker compose up -d` |
| DB 스키마 변경 | 마이그레이션 실행 (`docker compose exec backend python manage.py migrate`) |

---

## 5. 자주 쓰는 명령어

```bash
# 컨테이너 시작 (개발)
docker compose -f docker-compose.yml -f docker-compose.dev.yml up

# 백그라운드 실행
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# 로그 확인
docker compose logs -f backend

# 컨테이너 안에서 명령 실행
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py createsuperuser

# 컨테이너 중지
docker compose down

# 컨테이너 + 볼륨(DB 데이터) 삭제 (주의)
docker compose down -v

# 이미지 재빌드 후 시작
docker compose up --build
```

---

## 6. HyperCube 컨테이너 구성 (To-Be)

```
┌─────────────────────────────────────────────┐
│  Docker Compose                             │
│                                             │
│  ┌──────────────────────────────────────┐   │
│  │ nginx :7003                          │   │
│  │ 정적 파일 서빙 (SvelteKit 빌드 결과) │   │
│  │ + 리버스 프록시 (/api → Backend)     │   │
│  └──────────┬───────────────────────────┘   │
│             │                               │
│  ┌──────────┴──┐  ┌───────────┐             │
│  │  Backend   │  │  Celery   │             │
│  │  :8000     │  │  Worker   │             │
│  └──────┬──────┘  └─────┬─────┘             │
│         │               │                   │
│    ┌────┴─────┐   ┌─────┴────┐              │
│    │PostgreSQL│   │  Redis   │              │
│    │  :5432   │   │  :6379   │              │
│    └──────────┘   └──────────┘              │
│                                             │
│  ┌──────────┐                               │
│  │  Agent   │  (메인 서버 모니터링)          │
│  └──────────┘                               │
└─────────────────────────────────────────────┘
```

- Frontend는 별도 Node.js 컨테이너 없이 nginx가 정적 파일(SvelteKit adapter-static 빌드 결과)을 직접 서빙한다.
- Phase 1에서는 PostgreSQL, Redis, Backend(Django)만 먼저 구성한다.
- nginx 컨테이너는 Phase 1.2에서 API 이관 완료 후 추가한다.
