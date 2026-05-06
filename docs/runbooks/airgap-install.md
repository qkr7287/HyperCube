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

## 9. 트러블슈팅 — 단계별 진단

증상부터 찾아서 해당 항목으로. 그래도 안 풀리면 §10의 로그 수집 절차로 넘어가서 개발자에게 보냄.

### 9.1 install.sh 단계별 실패

#### "This installer targets Ubuntu 24.04 LTS only"

빌드된 `.run`과 호스트 OS 버전이 안 맞음.

```bash
lsb_release -cs   # 호스트 codename 확인 (noble / jammy)
```

→ 빌드 머신에서 `UBUNTU_VERSION=22.04 ./packaging/build.sh`로 그 버전용 `.run`을 새로 받아 옴.

#### `dpkg -i` 실패 (기존 Docker 충돌)

이미 snap이나 apt로 다른 Docker가 깔려있는 경우.

```bash
sudo snap remove docker 2>/dev/null
sudo apt-get remove -y docker docker-engine docker.io containerd runc 2>/dev/null
sudo dpkg --configure -a    # 보류 중인 dpkg 작업 정리
sudo ./hypercube-1.0-ubuntu2404.run
```

#### `dpkg -i`가 의존성 누락으로 실패

거의 발생 안 하지만 (24.04 base에 다 있음), 만약 발생하면:

```bash
sudo dpkg --configure -a
ls /opt/hypercube/docker-debs/    # 어떤 .deb이 들어있는지
```

→ 누락된 의존성 정보(에러 메시지)와 함께 §10 절차로 보고. 빌드 머신에서 해당 패키지 추가 번들링 필요.

#### `systemctl enable --now docker` 실패

```bash
sudo systemctl status docker
journalctl -u docker -n 50 --no-pager
```

흔한 원인:
- iptables 모듈 누락 (`/etc/modules-load.d`에 `iptable_nat` 없음) — 거의 24.04 기본 OK
- AppArmor 충돌 — `dmesg | grep -i apparmor`
- cgroup v2 → v1 mismatch — `mount | grep cgroup`

#### `docker load -i` 도중 "no space left on device"

`.run`은 2~3GB 여유 필요. 이미지 unpack 중 임시공간이 부족하면 실패.

```bash
df -h /var/lib/docker /tmp
```

→ 공간 확보 후 재시도 (이미지 일부만 import된 상태일 수 있어 `docker images`로 확인 후 누락분 별도 import).

#### 인터랙티브 prompt 입력 후 멈춤

`openssl rand` 실행 시 엔트로피 부족(가상화 환경 일부)에서 발생 가능.

```bash
sudo apt-get install -y haveged    # 안 됨 (폐쇄망) — 빌드 머신에서 미리 패키지 추가 또는
echo "manual-secret-key-50-chars-..." | sudo tee /opt/hypercube/.env-pre
```

거의 발생 안 하지만 발생하면 §10으로 보고.

### 9.2 컨테이너 상태별 진단

#### `docker compose ps`에서 상태별 의미

```bash
cd /opt/hypercube
sudo docker compose ps
```

| 상태 | 의미 | 다음 조치 |
|------|------|----------|
| `Up X minutes (healthy)` | 정상 | — |
| `Up X minutes` (healthy 표시 없음) | healthcheck 미정의 또는 아직 통과 전 | 30초 더 기다림 |
| `Restarting` | crash 후 자동 재시작 루프 | 9.3 보기 |
| `Exited (N)` | 죽음 | 9.3 보기 |
| `Created` (Up 아님) | 시작 자체 실패 | 9.4 보기 |

#### 9.3 backend가 `Restarting` (가장 흔함)

```bash
cd /opt/hypercube
sudo docker compose logs --tail 100 backend
```

원인별:

| 로그 키워드 | 원인 | 조치 |
|----------|------|------|
| `password authentication failed for user` | postgres 볼륨이 옛 비밀번호로 초기화 (재설치 케이스) | `sudo docker compose down -v && sudo systemctl restart hypercube` (DB 데이터 삭제됨) |
| `could not connect to server` / `Connection refused` | postgres 자체가 미기동 | `sudo docker compose logs postgres` |
| `OperationalError: relation "..." does not exist` | migration 실패 | `sudo docker compose run backend python manage.py migrate` 수동 실행 |
| `ImproperlyConfigured: SECRET_KEY` | `.env` 누락 또는 잘못된 형식 | `sudo cat /opt/hypercube/.env`로 점검 |
| `bind: address already in use` | 7003 포트 충돌 | 9.5 |
| (시작 후 즉시 SIGTERM) | OOM | `dmesg | tail -50 | grep -i memory` |

#### 9.4 컨테이너가 `Created`에서 안 넘어감

```bash
sudo docker compose ps
sudo docker events --since 5m | head -30
```

→ Docker daemon 자체 문제 가능. `sudo systemctl status docker` 확인.

#### 9.5 포트 충돌 (`bind: address already in use`)

다른 서비스가 같은 포트 점유 중.

```bash
sudo ss -tlnp | grep ':7003'      # 누가 잡고 있는지
sudo sed -i 's/^HC_PORT=.*/HC_PORT=7080/' /opt/hypercube/.env
sudo systemctl restart hypercube
```

### 9.6 네트워크 / 접속 문제

#### nginx 200 응답인데 화면이 빈 화면

```bash
curl -I http://localhost:7003/         # 200 정상이면
curl http://localhost:7003/ | head -50 # HTML 내용 확인
```

브라우저 캐시(`Ctrl+Shift+R`) 또는 시크릿 창 시도. 그래도 빈 화면이면 frontend 빌드 자체 깨짐 → `.run` 재빌드 필요.

#### nginx 502 Bad Gateway

backend가 죽은 상태. 9.3 참고.

#### `/api/...` 401 Unauthorized

정상 동작입니다. DRF 인증 미통과. 로그인 후 다시 시도.

#### 외부 PC에서 접속 시 "Bad Request (400)"

`DJANGO_ALLOWED_HOSTS`에 그 IP/도메인이 없음. `.env` 수정:

```bash
sudo nano /opt/hypercube/.env
# DJANGO_ALLOWED_HOSTS=192.168.0.16,localhost,127.0.0.1
# CSRF_TRUSTED_ORIGINS=http://192.168.0.16:7003
sudo systemctl restart hypercube
```

#### admin 로그인 시 CSRF 에러

`CSRF_TRUSTED_ORIGINS`에 접속 origin 추가 필요. 위 항목과 동일하게 처리.

### 9.7 Agent 연결 문제

#### Agent 컨테이너 내려가있음

```bash
docker ps --filter name=hypercube-agent --all
docker logs hypercube-agent --tail 100
```

원인별:

| 로그 키워드 | 원인 | 조치 |
|----------|------|------|
| `getaddrinfo ENOTFOUND <hostname>` | backend hostname/IP가 agent에서 resolve 안 됨 | `/opt/hypercube-agent/.env`의 `BACKEND_URL` 값을 IP로 변경 |
| `connect ECONNREFUSED` | backend 포트에 실제로 listen 중인 게 없음 | backend 서버에서 9.3 점검 |
| `WebSocket handshake error 401/403` | enrollment token 잘못됨 | admin에서 token 재발급, agent 재설치 |
| `WebSocket handshake error 400` | `DJANGO_ALLOWED_HOSTS` 또는 `CSRF` 문제 | 9.6 참고 |
| `WebSocket handshake error 404` | URL path 오타 (`ws://...:7003/ws/` 누락) | `BACKEND_URL` 검토 |

#### Agent는 떠있는데 admin 페이지에 안 보임

approval 대기 중일 가능성. Backend admin → Agents → Pending approval 확인.

#### Agent 메트릭이 끊김 / 갱신 안 됨

```bash
docker logs hypercube-agent --tail 100 --follow
```

`HC_GPU_ENABLED=true`로 설치했는데 호스트에 GPU 없으면 nvidia-smi 호출에서 멈출 수 있음. `.env`에서 `GPU_PER_CONTAINER_ENABLED=false`로 바꾸고 재시작:

```bash
sudo sed -i 's/^GPU_PER_CONTAINER_ENABLED=.*/GPU_PER_CONTAINER_ENABLED=false/' /opt/hypercube-agent/.env
sudo systemctl restart hypercube-agent
```

---

## 10. 장애 발생 시 정보 수집 — 운영자가 개발자에게 보내는 절차

위 9번에서 풀리지 않으면 **로그 한 묶음을 가져와서** 개발자(빌드 머신 환경)로 보냄. 폐쇄망이라 화면 공유가 안 되니, **하나의 tar.gz 파일로 모아서 USB로 전달**하는 게 표준.

### 10.1 한 번에 모으는 인라인 명령 (운영자 실행)

폐쇄망 서버에서 그대로 복붙:

```bash
sudo bash -c '
TS=$(date +%Y%m%d-%H%M%S)
DIR=/tmp/hc-diag-$TS
mkdir -p $DIR
cd $DIR

# --- system ---
{
  echo "=== uname ==="; uname -a
  echo "=== os ==="; lsb_release -a 2>/dev/null
  echo "=== uptime ==="; uptime
  echo "=== disk ==="; df -h
  echo "=== mem ==="; free -h
  echo "=== mounts ==="; mount | grep -E "cgroup|overlay" | head
  echo "=== version manifest ==="; cat /opt/hypercube/VERSION 2>/dev/null
  cat /opt/hypercube-agent/VERSION 2>/dev/null
} > 01-system.txt

# --- docker ---
{
  echo "=== version ==="; docker version 2>&1
  echo "=== info ==="; docker info 2>&1 | head -50
  echo "=== ps -a ==="; docker ps -a
  echo "=== images ==="; docker images
  echo "=== networks ==="; docker network ls
  echo "=== volumes ==="; docker volume ls
} > 02-docker.txt

# --- compose state ---
if [ -f /opt/hypercube/docker-compose.yml ]; then
  cd /opt/hypercube
  {
    echo "=== compose ps ==="; docker compose ps
    echo "=== compose config ==="; docker compose config
  } > $DIR/03-compose.txt 2>&1
fi

# --- service logs (last 500 lines each) ---
cd $DIR
mkdir -p logs
for svc in postgres redis backend nginx celery-worker celery-beat; do
  docker compose -f /opt/hypercube/docker-compose.yml logs --tail 500 --no-color $svc \
    > logs/$svc.log 2>&1 || true
done
docker logs --tail 500 hypercube-agent > logs/hypercube-agent.log 2>&1 || true

# --- env (시크릿 마스킹) ---
sed -E "s/^(DJANGO_SECRET_KEY|DB_PASSWORD|.*PASSWORD|.*TOKEN|.*KEY)=.*/\1=***REDACTED***/i" \
  /opt/hypercube/.env > 04-env-redacted.txt 2>/dev/null || true
sed -E "s/^(.*PASSWORD|.*TOKEN|.*KEY|.*SECRET)=.*/\1=***REDACTED***/i" \
  /opt/hypercube-agent/.env >> 04-env-redacted.txt 2>/dev/null || true

# --- systemd / journal ---
{
  echo "=== systemd hypercube ==="; systemctl status hypercube --no-pager -l
  echo "=== systemd docker ==="; systemctl status docker --no-pager -l
  echo "=== journal hypercube ==="; journalctl -u hypercube -n 100 --no-pager
  echo "=== journal docker ==="; journalctl -u docker -n 100 --no-pager
} > 05-systemd.txt 2>&1

# --- kernel / network ---
{
  echo "=== dmesg tail ==="; dmesg | tail -100
  echo "=== ports ==="; ss -tlnp 2>/dev/null
  echo "=== ip ==="; ip a
  echo "=== iptables ==="; iptables -L -n 2>/dev/null
} > 06-kernel-net.txt

# --- healthcheck ---
{
  echo "=== /api/health/ ==="
  curl -fsS --max-time 5 http://localhost:7003/api/health/ 2>&1
  echo "=== / (head) ==="
  curl -fsS --max-time 5 -I http://localhost:7003/ 2>&1
} > 07-healthcheck.txt

# --- archive ---
cd /tmp
tar czf hc-diag-$TS.tar.gz hc-diag-$TS/
sha256sum hc-diag-$TS.tar.gz > hc-diag-$TS.tar.gz.sha256
ls -lh /tmp/hc-diag-$TS.tar.gz*

echo
echo "==============================================="
echo "  DIAGNOSTIC BUNDLE: /tmp/hc-diag-'$TS'.tar.gz"
echo "  Copy this file (and .sha256) to USB and"
echo "  send to the dev team."
echo "==============================================="
'
```

산출물:
- `/tmp/hc-diag-<timestamp>.tar.gz` (보통 1~5MB)
- `/tmp/hc-diag-<timestamp>.tar.gz.sha256` (무결성 해시)

### 10.2 개발자에게 보낼 때 같이 적어주면 좋은 정보

진단 묶음 + 다음 항목을 짧게 메일/메신저(외부 채널)로:

```
[증상]    예: "agent가 backend에 안 붙음. admin Agents 페이지가 빈 채로 유지됨"
[발생 시점] 예: "2026-05-06 14:30 즈음, agent 설치 후 약 5분 뒤"
[기간]    예: "10분째 동일", "한 번 발생하고 사라짐"
[재현]    예: "재시작하면 잠깐 붙었다가 다시 끊김"
[직전 변경] 예: "agent를 192.168.0.20에 새로 설치했더니"
[운영자 추가 시도]
  - docker compose restart backend → 변화 없음
  - .env에서 DJANGO_ALLOWED_HOSTS 수정 → 안 됨
[첨부] hc-diag-<timestamp>.tar.gz
```

### 10.3 개발자가 빨리 보는 순서 (분석 흐름)

진단 묶음을 풀고 (`tar xzf hc-diag-*.tar.gz`):

1. `01-system.txt` — OS / disk / VERSION → 빌드본과 일치하는지
2. `03-compose.txt` — 컨테이너 상태로 어디 죽었는지 한눈에
3. `logs/<죽은 서비스>.log` — 첫 ERROR/Traceback 줄
4. `05-systemd.txt` — docker daemon / systemd unit 정상 여부
5. `04-env-redacted.txt` — 설정 누락/오타
6. `06-kernel-net.txt` — OOM, port 충돌, iptables 룰

대부분 9.3 표의 키워드 매칭으로 원인 추정 가능. 매칭 안 되면 stack trace 전체 분석.

### 10.4 핫픽스 전달 절차 (개발자 → 운영자)

원인 파악 후 수정이 backend/frontend 코드 수준이면:
1. dev 브랜치 fix → main 머지 → CI build → 새 `.run`
2. 새 `.run`을 USB로 전달
3. 운영자가 같은 명령으로 덮어쓰기 (`sudo ./hypercube-x.y-ubuntu2404.run`) — `.env`/DB는 보존

설정 수준이면:
- 운영자가 `.env`만 수정 후 `systemctl restart hypercube`

---

## 11. 산출물 점검 체크리스트

빌드 머신에서 새 `.run`을 만들 때 사용:

- [ ] `./packaging/build.sh` 종료 코드 0
- [ ] `dist/hypercube-X.Y-ubuntu2404.run` 존재
- [ ] `--check` 무결성 OK
- [ ] 크기 350~500MB 범위
- [ ] 깨끗한 Ubuntu 24.04 VM에서 1회 설치 검증
- [ ] 헬스체크 200 OK
- [ ] (또는) `packaging/test-airgap` 시뮬레이션 컨테이너에서 검증
- [ ] `sha256sum`으로 해시 기록 (반입 검증용)
- [ ] `sha256sum`으로 해시 기록 (반입 검증용)
