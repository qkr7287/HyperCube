# 폐쇄망(Air-gapped) 설치 가이드

인터넷이 차단된 환경에 HyperCube를 설치하는 절차. Ubuntu 24.04 LTS 타겟.

대상 산출물: 단일 파일 `dist/hypercube-1.0-ubuntu2404.run` (~405MB)
포함된 것: Docker engine + 의존성 .deb + HyperCube 이미지 4개 + 인스톨러 스크립트

전체 흐름:

```
[빌드 머신 (인터넷 O)] -- USB --> [폐쇄망 서버 (인터넷 X)]
   build.sh                           ./hypercube-...run
   .run 생성                          한 줄 실행 → 완료
```

---

## 1. 빌드 단계 (인터넷 되는 환경)

### 사전 조건

- Docker 20.10+ (Docker Desktop, Linux Docker, WSL2 Docker 다 가능)
- `makeself` (`sudo apt-get install makeself` 또는 https://makeself.io)
- Git checkout된 HyperCube 소스 트리

### 빌드 실행

```bash
chmod +x packaging/build.sh
./packaging/build.sh
```

`VERSION`, `IMAGE_TAG`로 버전 지정 가능:

```bash
VERSION=1.2 IMAGE_TAG=sha-abc1234 ./packaging/build.sh
```

빌드 시간: 5~15분 (이미지 pull 네트워크 속도에 따라).

### 빌드 결과

```
dist/hypercube-1.0-ubuntu2404.run   (~405MB, 단일 파일)
```

### 무결성 검증 (선택)

```bash
./dist/hypercube-1.0-ubuntu2404.run --check
# Verifying archive integrity... MD5 checksums are OK. All good.
```

---

## 2. 반입 단계

USB 또는 인가된 매체로 폐쇄망 서버에 옮길 파일은 **`.run` 파일 1개만**:

```
hypercube-1.0-ubuntu2404.run   (405MB)
```

권한 정책상 SHA256 같은 별도 해시가 필요하면 빌드 머신에서:

```bash
sha256sum dist/hypercube-1.0-ubuntu2404.run > dist/hypercube-1.0-ubuntu2404.run.sha256
```

---

## 3. 폐쇄망 서버 설치

### 사전 조건

- Ubuntu 24.04 LTS (codename `noble`)
- root 또는 sudo 권한
- 디스크 여유 ~3GB (이미지 + 컨테이너 + 볼륨)
- 외부 인터넷 0% 가능 — Docker도 미리 깔려있을 필요 없음

### 설치

`.run` 파일을 적당한 경로(예: `/root/`)에 두고:

```bash
chmod +x hypercube-1.0-ubuntu2404.run
sudo ./hypercube-1.0-ubuntu2404.run
```

설치 스크립트가 자동으로 진행:

1. Ubuntu 버전 검증 (noble 아니면 abort)
2. Docker 설치 (이미 있으면 skip) — 24개의 .deb를 `dpkg -i`로 오프라인 설치
3. `systemctl enable --now docker`
4. `docker load`로 HyperCube 이미지 4개 import
5. `/opt/hypercube/`에 compose 파일 + 스크립트 배치
6. **인터랙티브 입력 (2가지)**:
   - Host IP/DNS: 외부에서 접속할 IP (기본값: 호스트의 첫 번째 IP)
   - Service port: 노출 포트 (기본값: 7003)
7. `DJANGO_SECRET_KEY`, `DB_PASSWORD` 자동 생성 (`openssl rand`)
8. `docker compose up -d`
9. `systemctl enable hypercube` 등록 → 재부팅 자동시작
10. 헬스체크 후 접속 정보 출력

### 정상 출력 예시

```
[+] HyperCube installed successfully.

  URL        http://192.168.1.50:7003
  Config     /opt/hypercube/.env
  Logs       cd /opt/hypercube && docker compose logs -f
  Stop       systemctl stop hypercube
  Start      systemctl start hypercube
  Uninstall  /opt/hypercube/uninstall.sh
```

---

## 4. 설치 후 확인

### 컨테이너 상태

```bash
cd /opt/hypercube
docker compose ps
```

기대 결과:

```
NAME               STATUS                    PORTS
hc-postgres        Up (healthy)              5432/tcp
hc-redis           Up (healthy)              6379/tcp
hc-backend         Up                        8000/tcp
hc-celery-worker   Up
hc-celery-beat     Up
hc-nginx           Up                        0.0.0.0:7003->7003/tcp
```

### 헬스체크

```bash
curl -fsS http://127.0.0.1:7003/api/health/
```

200 OK 응답 받으면 정상.

### 웹 접속

브라우저에서 `http://<서버IP>:7003` 접속.

### 관리자 계정

기본 superuser는 자동 생성되지 않음. 수동으로:

```bash
docker compose -f /opt/hypercube/docker-compose.yml exec backend \
    python manage.py createsuperuser
```

---

## 5. Agent 설치 (모니터링 대상 서버)

Agent는 **별도 패키지**로 별도 서버에 설치. 같은 서버 1대만 필요한 경우 메인 서버에서 같이 돌려도 됨.

Agent 패키지 빌드는 `hypercube-agent` repo에서 별도. 설치 흐름은 동일한 `.run` 패턴 (이 문서가 적용되지 않음).

연결 정보:
- Backend WS URL: `ws://<메인서버IP>:7003/ws/agent/`
- Agent enrollment token: 메인 서버 admin에서 발급

방화벽: Agent 서버 → 메인 서버 7003 포트 허용 필요.

---

## 6. 운영

### 시작 / 중지 / 재시작

```bash
sudo systemctl start hypercube
sudo systemctl stop hypercube
sudo systemctl restart hypercube
```

또는 docker compose 직접:

```bash
cd /opt/hypercube
sudo docker compose up -d        # start
sudo docker compose down         # stop (volume 유지)
sudo docker compose restart      # restart
```

### 로그

```bash
cd /opt/hypercube
sudo docker compose logs -f                    # 전체
sudo docker compose logs -f backend            # backend만
sudo docker compose logs --tail 100 backend    # 마지막 100줄
```

### 설정 변경

`.env` 수정 후 재시작:

```bash
sudo nano /opt/hypercube/.env
sudo systemctl restart hypercube
```

주의: `DB_PASSWORD`는 처음 한 번만 적용됨 (postgres가 첫 부팅에 사용자 생성). 변경하려면 별도 절차 필요.

### DB 백업

```bash
sudo docker compose -f /opt/hypercube/docker-compose.yml exec -T postgres \
    pg_dump -U hypercube hypercube > /backup/hypercube-$(date +%Y%m%d).sql
```

### DB 복원

```bash
cat /backup/hypercube-20260506.sql | \
    sudo docker compose -f /opt/hypercube/docker-compose.yml exec -T postgres \
    psql -U hypercube hypercube
```

---

## 7. 업그레이드

새 버전 `.run` 파일을 받아서 같은 절차로 다시 실행:

```bash
chmod +x hypercube-1.1-ubuntu2404.run
sudo ./hypercube-1.1-ubuntu2404.run
```

기존 `.env`는 보존됨. 이미지만 새것으로 교체되고 `compose up -d`가 자동 재시작.

DB 마이그레이션은 backend 컨테이너 시작 시 자동 실행 (`python manage.py migrate`).

---

## 8. 제거

```bash
sudo /opt/hypercube/uninstall.sh
```

3단계 인터랙티브 확인:

1. HyperCube 컨테이너 + `/opt/hypercube/` 제거? (y/n)
2. Docker 이미지도 제거? (y/n)
3. Docker engine 자체도 제거? (y/n)

볼륨 데이터는 step 1에서 `compose down -v`로 같이 삭제됩니다. 보존하려면 사전에 백업.

---

## 9. 트러블슈팅

### 설치 도중 "Ubuntu 24.04 LTS only" 에러

다른 버전(20.04, 22.04 등)에서 실행한 경우. 빌드 머신에서 해당 버전용 `.run`을 별도로 만들어야 함.

### `dpkg -i` 실패

기존 Docker가 다른 방식(예: snap)으로 설치된 경우 충돌. 제거 후 재시도:

```bash
sudo snap remove docker 2>/dev/null
sudo apt-get remove -y docker docker-engine docker.io containerd runc 2>/dev/null
sudo ./hypercube-1.0-ubuntu2404.run
```

### backend가 `Restarting` 상태

```bash
cd /opt/hypercube
sudo docker compose logs --tail 50 backend
```

가장 흔한 원인:

- **DB 연결 실패** (`password authentication failed`): postgres 볼륨이 이전 비밀번호로 초기화됨. `.env`의 `DB_PASSWORD`를 옛값으로 맞추거나, 볼륨 삭제 후 재시작:
  ```bash
  sudo docker compose down -v
  sudo systemctl restart hypercube
  ```
- **Migration 실패**: backend 로그에서 stack trace 확인. 보통 DB 스키마 충돌.
- **Disk full**: `df -h`로 확인.

### nginx가 502

backend가 죽은 상태. 위 backend 트러블슈팅 참고.

### 포트 7003 충돌

다른 서비스가 점유 중. `.env`에서 `HC_PORT`를 다른 값으로 변경 후 재시작:

```bash
sudo sed -i 's/^HC_PORT=.*/HC_PORT=7080/' /opt/hypercube/.env
sudo systemctl restart hypercube
```

### Docker 명령이 안 먹힘

```bash
sudo systemctl status docker
sudo systemctl start docker
```

---

## 10. 산출물 점검 체크리스트

빌드 머신에서 새 `.run`을 만들 때 사용:

- [ ] `./packaging/build.sh` 종료 코드 0
- [ ] `dist/hypercube-X.Y-ubuntu2404.run` 존재
- [ ] `--check` 무결성 OK
- [ ] 크기 350~500MB 범위
- [ ] 깨끗한 Ubuntu 24.04 VM에서 1회 설치 검증
- [ ] 헬스체크 200 OK
- [ ] `sha256sum`으로 해시 기록 (반입 검증용)
