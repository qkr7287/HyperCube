# HyperCube 폐쇄망 설치 가이드

> 인터넷이 없는 환경에 HyperCube를 설치하고 운영하기 위한 문서입니다.
> Linux 명령에 익숙하지 않으셔도 그대로 따라하실 수 있도록 작성했습니다.
> 명령어는 그대로 복사해서 붙여넣으면 됩니다.

---

## 0. 무엇을 설치하나요?

HyperCube는 **서버를 모니터링하는 도구**입니다. 두 가지 부품이 있어요:

| 부품 | 어디에 깔리나 | 역할 |
|------|------------|------|
| **Backend (서버 본체)** | 1대 (관리자가 보는 서버) | 데이터 저장 + 웹 화면 제공 |
| **Agent (수집기)** | N대 (모니터링하고 싶은 서버 전부) | 그 서버 정보를 backend에 보냄 |

**최소 구성**: backend 서버 1대만 있어도 동작합니다 (자기 자신만 모니터링).
**일반 구성**: backend 1대 + agent를 깔 서버 여러 대.

---

## 1. 설치 전 — 폐쇄망 서버에 무엇이 있어야 하나요?

**필요한 것 — `Docker`가 미리 깔려있어야 합니다.** OS 종류는 거의 무관합니다 (Ubuntu / RHEL / Rocky / AlmaLinux / Debian / SUSE 등 systemd + Docker 지원하는 Linux면 OK).

폐쇄망 서버에 다음이 깔려있을 필요가 **전혀 없습니다**:
- ❌ PostgreSQL (자동)
- ❌ Redis (자동)
- ❌ Python / Node.js (자동)
- ❌ Nginx (자동)
- ❌ 인터넷 연결 (필요 없습니다)

**미리 필요한 것**:
- ✅ **Docker 24.0+ 와 docker compose plugin** (인프라팀 / 운영팀이 사전 설치)
- ✅ **systemd** (대부분 OS 기본)

### 확인 명령

```bash
docker --version
docker compose version
```

다음과 같이 둘 다 응답이 나와야 합니다:
```
Docker version 28.0.2, build ...
Docker Compose version v2.x.x
```

### Docker가 아직 없으면 — 사전 설치 명령

> 폐쇄망이면 사내 mirror 또는 Docker 공식 패키지를 USB로 미리 가져와서 설치하세요. 이 단계는 인프라팀 책임입니다.

**Ubuntu 22.04 / 24.04 / Debian**:
```bash
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
sudo systemctl enable --now docker
```

**RHEL 8/9 / Rocky / AlmaLinux**:
```bash
sudo dnf install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
sudo systemctl enable --now docker
```

**SUSE**:
```bash
sudo zypper install -y docker docker-compose
sudo systemctl enable --now docker
```

설치 완료 확인:
```bash
sudo docker run --rm hello-world    # "Hello from Docker!" 메시지가 나오면 OK
```

**디스크 여유공간**: 약 **3GB** 필요합니다.
```bash
df -h /
```

`Avail` 칸에 3G 이상 남아있어야 합니다.

---

## 2. USB로 가져갈 파일

빌드 머신 (인터넷 되는 PC) 에서 다음 두 파일을 USB에 복사하세요:

| 파일 | 위치 | 크기 |
|------|------|-----|
| **HyperCube backend 인스톨러** | `dist/hypercube-1.0.sh` | 약 320 MB |
| **HyperCube agent 인스톨러** | `HyperCube-agent/dist-installer/hypercube-agent-installer-1.0.0.sh` | 약 169 MB |

가이드 자체(이 문서)도 같이 가져가시면 폐쇄망에서 참고할 수 있어 좋습니다:
- `docs/runbooks/airgap-install.md`

전부 합쳐도 약 490MB라 USB 1GB짜리도 충분합니다.

> 💡 backend 인스톨러는 **OS 무관 단일 파일**입니다 (Docker가 사전 설치되어 있다는 전제 하에). Ubuntu / RHEL / Rocky / AlmaLinux / Debian / SUSE 등 systemd + Docker 지원 Linux면 동일하게 동작.

**무결성 확인 (선택사항)**: 파일이 옮겨지는 도중 깨졌는지 확인하고 싶으시면 빌드 머신 PowerShell에서:
```powershell
Get-FileHash "dist\hypercube-1.0.sh" -Algorithm SHA256
```
출력된 해시값을 메모해서 같이 USB에 넣고, 폐쇄망에서 비교하면 됩니다 (자세한 건 §10 참고).

---

## 3. Backend 서버 설치 (5단계)

폐쇄망 서버 한 대를 골라서, 거기 USB에 있는 파일을 복사해 넣고 시작합니다.

### 3-1단계. 파일을 서버에 옮기기

USB를 서버에 꽂고, 다음 폴더로 복사하세요. 예를 들어 root 사용자 홈 디렉터리:
```bash
sudo cp /media/usb/hypercube-1.0.sh /root/
cd /root
ls -lh hypercube-1.0.sh
```

다음과 같이 나와야 합니다:
```
-rw-r--r-- 1 root root 405M ... hypercube-1.0.sh
```

### 3-2단계. 실행 권한 주기

```bash
sudo chmod +x hypercube-1.0.sh
```

(아무 출력도 없으면 정상입니다. 권한이 부여된 거예요.)

### 3-3단계. 인스톨러 실행

```bash
sudo ./hypercube-1.0.sh
```

먼저 압축이 풀립니다 (수십 초):
```
Verifying archive integrity... All good.
Uncompressing HyperCube 1.0 (Ubuntu 24.04) 100%
```

그러면 **두 가지 질문이 나옵니다**:

#### 질문 1: Host IP or DNS name

```
  Host IP or DNS name [192.168.0.16]:
```

대괄호 `[ ]` 안의 값이 **자동 감지된 값**입니다. 보통 그대로 엔터 치면 됩니다. 다만:

- **여러 개의 네트워크 카드가 있는 서버**라면 다른 IP를 입력해야 할 수 있습니다 (운영팀에서 알려준 IP).
- IP 대신 **호스트 이름(예: `monitor.company.com`)**을 입력해도 됩니다.

이 값은 "**다른 PC가 웹 브라우저로 접속할 때 쓰는 주소**"입니다. 잘못 입력하면 외부 PC에서 접속이 안 되지만, 같은 서버 내에서(localhost)는 항상 됩니다. 나중에 수정 가능하니 일단 엔터 쳐도 됩니다.

#### 질문 2: Service port

```
  Service port [7003]:
```

기본 7003번 포트로 둡니다. 다른 서비스가 7003번을 쓰고 있는 게 아니라면 그냥 엔터 치세요.

다른 포트로 바꾸려면 숫자만 입력 (예: `8080`).

### 3-4단계. 자동 설치 진행 (5~10분)

이제 인스톨러가 알아서 다 합니다. 화면에 다음과 같은 메시지들이 차례로 나옵니다:

```
[+] Docker detected: Docker version 28.0.2
[+] Compose detected: v2.x.x
[+] Loading HyperCube images (this can take a minute)...
    Loaded image: ghcr.io/qkr7287/hypercube-backend:latest
    Loaded image: ghcr.io/qkr7287/hypercube-nginx:latest
    Loaded image: pgvector/pgvector:pg16
    Loaded image: redis:7-alpine
[+] Generating .env (interactive)...
    -> wrote /opt/hypercube/.env
[+] Starting HyperCube stack...
    Container hc-postgres   Healthy
    Container hc-redis      Healthy
    Container hc-backend    Started
    Container hc-nginx      Started
    Container hc-celery-worker  Started
    Container hc-celery-beat    Started
[+] Waiting for backend (up to 60s)...
[+] HyperCube installed successfully.
```

마지막에 **`HyperCube installed successfully.`** 줄이 나오면 성공입니다.

### 3-5단계. 설치 정보 확인

설치 마지막에 다음과 같은 안내가 나옵니다 — **이걸 메모해두세요**:

```
  URL        http://192.168.0.16:7003
  Config     /opt/hypercube/.env
  Logs       cd /opt/hypercube && docker compose logs -f
  Stop       systemctl stop hypercube
  Start      systemctl start hypercube
  Uninstall  /opt/hypercube/uninstall.sh
```

여기 `URL`이 **웹 브라우저로 들어가는 주소**입니다. 같은 사내 LAN의 다른 PC에서 이 주소로 접속할 수 있어요.

---

## 4. Backend 설치 후 — 웹 접속 + 관리자 계정 만들기

### 4-1단계. 웹 접속 테스트

같은 서버 안에서 다음 명령으로 동작 확인:

```bash
curl http://localhost:7003/api/health/
```

다음과 같이 나오면 정상:
```
{"status": "ok"}
```

만약 위와 다르게 나오거나 에러가 뜨면 §8 트러블슈팅을 참고하세요.

### 4-2단계. 다른 PC에서 웹 접속

같은 사내망의 다른 PC에서 웹 브라우저를 열고:
```
http://<서버 IP>:7003
```

(예: `http://192.168.0.16:7003`)

화면이 정상적으로 뜨면 OK입니다.

### 4-3단계. 관리자 계정 생성

처음에는 관리자 계정이 없습니다. 다음 명령으로 만드세요:

```bash
sudo docker compose -f /opt/hypercube/docker-compose.yml exec backend python manage.py createsuperuser
```

다음과 같이 입력하라는 안내가 나옵니다:
```
Username (leave blank to use 'app'): admin
Email address: admin@company.com
Password: ********
Password (again): ********
Superuser created successfully.
```

비밀번호는 화면에 안 보이니 그냥 입력하시면 됩니다.

이제 브라우저에서 `http://<서버IP>:7003/admin/` 으로 접속해서 위에서 만든 계정으로 로그인할 수 있습니다.

---

## 5. Agent 설치 — 모니터링하고 싶은 서버에

Backend가 다 떴으니, 이제 모니터링하고 싶은 서버들에 agent를 깔면 됩니다. 같은 서버에 둘 다 깔아도 되고, 다른 서버에 따로 깔아도 됩니다.

### 5-1단계. 파일 준비

USB에서 agent 인스톨러를 모니터링 대상 서버로 복사:
```bash
sudo cp /media/usb/hypercube-agent-installer-1.0.0.sh /root/
sudo chmod +x /root/hypercube-agent-installer-1.0.0.sh
```

### 5-2단계. 인스톨러 실행

```bash
sudo /root/hypercube-agent-installer-1.0.0.sh
```

압축이 풀린 뒤 **5가지 질문**이 나옵니다:

#### 질문 1: Backend WebSocket URL

```
  Backend WebSocket URL [ws://192.168.0.16:8000]:
```

**중요**: 기본값은 무시하시고, **3-5단계에서 메모한 URL**을 변형해서 입력하세요.

**같은 서버에 backend도 있으면** (= 자기 자신 모니터링):
```
ws://localhost:7003
```

**다른 서버의 backend를 모니터링하면**:
```
ws://<backend서버IP>:7003
```
(예: `ws://192.168.0.16:7003`)

> ⚠️ `ws://`로 시작해야 합니다 (`http://`가 아닙니다). WebSocket 통신용이라 `ws`예요.

#### 질문 2: Backend REST API URL

```
  Backend REST API URL [http://192.168.0.16:7003]:
```

위 WebSocket URL을 자동으로 `http://...`로 변환해서 보여줍니다. 그냥 엔터 치면 됩니다.

#### 질문 3: Agent hostname

```
  Agent hostname [server-01]:
```

이 서버를 backend에서 어떤 이름으로 표시할지. 기본값(현재 호스트명) 그대로 엔터 치셔도 됩니다.

#### 질문 4: Enable per-container GPU monitoring? (y/n)

```
  Enable per-container GPU monitoring? (y/n) [y]:
```

**서버에 NVIDIA GPU가 없다면** `n` + 엔터를 입력하세요. GPU가 있으면 `y` (또는 그냥 엔터).

#### 질문 5: Auto-start on boot via systemd? (y/n)

```
  Auto-start on boot via systemd? (y/n) [y]:
```

서버 재부팅 시 자동으로 agent를 시작할지. 그냥 엔터 (= y) 권장.

#### 마지막 확인:

입력한 값들이 요약돼서 보여집니다:
```
  Backend WS  : ws://192.168.0.16:7003
  Backend API : http://192.168.0.16:7003
  Hostname    : server-01
  GPU         : n
  Auto-start  : y

  Proceed? [Y/n]: ↵
```

엔터 치면 설치가 진행됩니다.

### 5-3단계. 설치 진행 (2~5분)

```
[+] Pre-flight checks...
[+] Extracting bundled payload...
[+] Loading agent image into Docker...
[+] Writing /opt/hypercube-agent/{.env,docker-compose.yml}...
[+] Installing systemd unit...
[+] Starting agent...
[OK] Agent container is running.
[OK] Install complete.
```

`Install complete.` 나오면 끝입니다.

### 5-4단계. Backend admin에서 agent 승인

브라우저에서 backend admin 페이지(`http://<서버IP>:7003/admin/`) 접속 후:
1. **Agents** 메뉴 클릭
2. 방금 설치한 agent가 **"Pending approval"** 상태로 보임
3. 체크 후 **Approve** (또는 활성화) 버튼 클릭

승인 후 1~2분 안에 메트릭이 들어오기 시작합니다.

여러 대에 깔려면 5-1 ~ 5-4 단계를 그 서버 수만큼 반복하세요.

---

## 6. 설치 확인 — 어떻게 알 수 있나요?

### 6-1. Backend 정상 동작 확인

```bash
curl http://localhost:7003/api/health/
```
정상: `{"status": "ok"}`

### 6-2. 컨테이너 상태 확인

```bash
sudo docker compose -f /opt/hypercube/docker-compose.yml ps
```

다음 6개가 모두 `running` 또는 `Up (healthy)`로 나와야 정상:
```
NAME             STATUS
hc-postgres      Up X minutes (healthy)
hc-redis         Up X minutes (healthy)
hc-backend       Up X minutes
hc-celery-beat   Up X minutes
hc-celery-worker Up X minutes
hc-nginx         Up X minutes
```

### 6-3. Agent 동작 확인 (agent 깔린 서버에서)

```bash
sudo docker ps --filter name=hypercube-agent
```
정상이면 `hypercube-agent` 컨테이너 한 줄이 `Up`으로 보입니다.

### 6-4. Agent 로그 보기

```bash
sudo docker logs --tail 30 hypercube-agent
```
다음과 같이 backend에 잘 붙은 메시지가 보여야 합니다:
```
[INFO] Connected to backend ws://192.168.0.16:7003
[INFO] Sending metrics every 2000ms
```

### 6-5. 웹 화면에서 확인

브라우저로 `http://<서버IP>:7003`에 접속해서:
- 대시보드에 servers / containers / metrics가 표시되는지
- admin 페이지의 Agents에 등록된 agent들이 활성 상태인지

다 OK면 설치 완료입니다.

---

## 7. 운영 명령 — 자주 쓰는 것

### Backend 시작 / 중지 / 재시작

```bash
sudo systemctl start hypercube      # 시작
sudo systemctl stop hypercube       # 중지
sudo systemctl restart hypercube    # 재시작
sudo systemctl status hypercube     # 현재 상태 확인
```

### Agent 시작 / 중지 / 재시작

```bash
sudo systemctl start hypercube-agent
sudo systemctl stop hypercube-agent
sudo systemctl restart hypercube-agent
sudo systemctl status hypercube-agent
```

### 로그 보기

**Backend 전체**:
```bash
cd /opt/hypercube
sudo docker compose logs -f
```
(`Ctrl+C`로 종료)

**특정 서비스만**:
```bash
sudo docker compose -f /opt/hypercube/docker-compose.yml logs -f backend
sudo docker compose -f /opt/hypercube/docker-compose.yml logs -f postgres
```

**Agent**:
```bash
sudo docker logs -f hypercube-agent
```

### 설정 변경

```bash
sudo nano /opt/hypercube/.env       # backend 설정
sudo nano /opt/hypercube-agent/.env # agent 설정
```

수정 후 재시작:
```bash
sudo systemctl restart hypercube       # backend 재시작
sudo systemctl restart hypercube-agent # agent 재시작
```

### 데이터베이스 백업

```bash
sudo docker compose -f /opt/hypercube/docker-compose.yml exec -T postgres \
    pg_dump -U hypercube hypercube > /root/hypercube-backup-$(date +%Y%m%d).sql
```

`/root/`에 SQL 파일이 만들어집니다. USB로 복사해두면 좋아요.

### 데이터베이스 복원 (백업 파일 있을 때)

```bash
cat /root/hypercube-backup-20260506.sql | \
    sudo docker compose -f /opt/hypercube/docker-compose.yml exec -T postgres \
    psql -U hypercube hypercube
```

---

## 8. 업그레이드 — 새 버전이 나왔을 때

개발팀에서 새 `.sh` 파일을 받으셨다면:

```bash
sudo cp /media/usb/hypercube-1.1.sh /root/
sudo chmod +x /root/hypercube-1.1.sh
sudo /root/hypercube-1.1.sh
```

기존 설정(`.env`)과 데이터베이스는 그대로 보존됩니다. 컨테이너 이미지만 새 버전으로 교체되고, DB 마이그레이션은 자동으로 처리됩니다.

업그레이드 후 다시 위 §6 절차로 동작 확인하세요.

---

## 9. 제거 — 완전히 지우고 싶을 때

### Backend 제거

```bash
sudo /opt/hypercube/uninstall.sh
```

3가지 질문이 나옵니다 (각각 y/n):
1. **HyperCube를 정말 제거하시겠습니까?** → `y`
2. **Docker 이미지도 제거하시겠습니까?** → `y` (재설치 시 USB 다시 필요)
3. **Docker 엔진 자체도 제거하시겠습니까?** → `n` (다른 컨테이너도 쓰면 두기)

⚠️ 백업 안 한 데이터베이스는 사라집니다. 미리 §7의 백업 명령 실행하세요.

### Agent 제거

```bash
sudo systemctl stop hypercube-agent
sudo systemctl disable hypercube-agent
sudo rm /etc/systemd/system/hypercube-agent.service
sudo systemctl daemon-reload
cd /opt/hypercube-agent && sudo docker compose down
sudo rm -rf /opt/hypercube-agent
sudo docker rmi hypercube-agent:1.0.0
```

---

## 10. 문제 발생 시 — 단계별 해결

> 문제가 생기면 무엇보다 먼저 **어떤 화면이 보이는지** 정확히 파악하는 게 중요합니다.
> 아래 증상별로 해결 명령을 정리했어요. **명령은 그대로 복사해서 붙여넣으면 됩니다.**

### 10-1. 인스톨러 실행 자체가 안 될 때

#### 증상: `Permission denied`

```
bash: ./hypercube-1.0.sh: Permission denied
```

**원인**: 실행 권한이 없습니다.
**해결**:
```bash
sudo chmod +x hypercube-1.0.sh
sudo ./hypercube-1.0.sh
```

#### 증상: `Docker is not installed`

**원인**: 서버에 Docker가 깔려있지 않습니다.
**해결**: §1의 "Docker가 아직 없으면 — 사전 설치 명령" 절차로 Docker 먼저 설치 후 재시도. OS 종류별로 명령이 다릅니다:

```bash
# Ubuntu / Debian
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# RHEL / Rocky / AlmaLinux
sudo dnf install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# 그 후 공통
sudo systemctl enable --now docker
sudo docker run --rm hello-world      # 동작 확인
```

#### 증상: `Docker is installed but daemon is not running`

```bash
sudo systemctl start docker
sudo systemctl enable docker          # 부팅 자동시작
```

#### 증상: `docker compose plugin missing`

```bash
# Ubuntu / Debian
sudo apt-get install -y docker-compose-plugin

# RHEL / Rocky
sudo dnf install -y docker-compose-plugin
```

옛 docker-compose v1(`docker-compose` 하이픈 명령)은 지원하지 않습니다. 반드시 v2 plugin(`docker compose` 띄어쓰기) 필요.

### 10-2. Docker 자체 동작 문제

#### 증상: `failed to start docker.service`

**확인**:
```bash
sudo systemctl status docker
sudo journalctl -u docker -n 50 --no-pager
```

위 출력을 그대로 복사해서 §11 절차로 개발팀에 보고하세요.

### 10-3. 설치는 끝났는데 backend 컨테이너가 안 뜰 때

증상: 설치 마지막에 다음 메시지가 나옴:
```
[!] Installed, but health check did not respond yet.
```

또는 `docker compose ps`에서 `hc-backend`가 `Restarting`으로 보임.

**1단계 — 로그 확인**:
```bash
cd /opt/hypercube
sudo docker compose logs --tail 50 backend
```

**2단계 — 로그에서 에러 메시지 찾기**:

| 로그에 보이는 키워드 | 원인 | 해결 명령 |
|--------------------|------|----------|
| `password authentication failed` | DB 비밀번호 불일치 (재설치 시 흔함) | `sudo docker compose -f /opt/hypercube/docker-compose.yml down -v && sudo systemctl restart hypercube` ⚠️ DB 데이터 사라짐 |
| `could not connect to server` | postgres가 안 떠있음 | `sudo docker compose -f /opt/hypercube/docker-compose.yml logs postgres` 보고 §11 |
| `relation "..." does not exist` | DB 마이그레이션 미실행 | `sudo docker compose -f /opt/hypercube/docker-compose.yml run backend python manage.py migrate` |
| `bind: address already in use` | 다른 서비스가 7003 포트 사용 중 | 10-4 항목 참고 |
| `MemoryError` 또는 OOM | 메모리 부족 | `free -h`로 메모리 확인. 4GB 미만이면 부족 |

해결 후 재시작:
```bash
sudo systemctl restart hypercube
```

### 10-4. 포트 7003이 이미 사용 중일 때

**확인**:
```bash
sudo ss -tlnp | grep ':7003'
```
무언가 출력되면 그 프로세스가 7003 포트를 점유 중.

**해결 — HyperCube 포트를 다른 번호로 변경**:
```bash
sudo nano /opt/hypercube/.env
```
`HC_PORT=7003`을 `HC_PORT=8080` (또는 비어있는 포트)로 수정 후 저장 (`Ctrl+O`, 엔터, `Ctrl+X`).

```bash
sudo systemctl restart hypercube
```

### 10-5. 웹 브라우저에서 안 보일 때

#### 증상: "사이트에 연결할 수 없음" / `ERR_CONNECTION_REFUSED`

**확인 1 — 서버 자체에서 응답 오는지**:
```bash
curl http://localhost:7003/api/health/
```
- 응답 옴 (`{"status": "ok"}`) → 서버는 정상. 네트워크/방화벽 문제.
- 응답 안 옴 → 컨테이너 다운. 10-3 참고.

**확인 2 — 방화벽 확인**:
```bash
sudo ufw status
```
`Status: active`면 7003 포트 허용 추가:
```bash
sudo ufw allow 7003/tcp
```

#### 증상: 화면이 빈 흰 화면

브라우저 캐시 문제일 가능성이 큽니다.
- `Ctrl + Shift + R` (강제 새로고침)
- `Ctrl + Shift + N` (시크릿 창)으로 시도

#### 증상: `Bad Request (400)`

`.env`의 `DJANGO_ALLOWED_HOSTS`에 접속하는 IP/도메인이 빠져있습니다.

```bash
sudo nano /opt/hypercube/.env
```
`DJANGO_ALLOWED_HOSTS` 줄에 접속하려는 IP를 콤마로 추가:
```
DJANGO_ALLOWED_HOSTS=192.168.0.16,localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=http://192.168.0.16:7003
```
(예시 IP 부분에 실제 서버 IP를 적으세요)

```bash
sudo systemctl restart hypercube
```

#### 증상: `502 Bad Gateway`

backend 컨테이너가 죽어있는 상태. 10-3으로 가세요.

### 10-6. Agent가 backend에 안 붙을 때

**확인 — agent 로그 보기**:
```bash
sudo docker logs --tail 50 hypercube-agent
```

| 로그에 보이는 키워드 | 원인 | 해결 |
|--------------------|------|------|
| `getaddrinfo ENOTFOUND` | URL의 호스트 이름을 못 찾음 | `/opt/hypercube-agent/.env`의 `BACKEND_URL`을 IP 주소로 수정 |
| `connect ECONNREFUSED` | backend 서버가 꺼져있거나 포트가 다름 | backend 서버에서 `curl http://localhost:7003/api/health/` 확인 |
| `WebSocket handshake error 400/401/403` | URL 또는 인증 문제 | `.env`의 `BACKEND_URL`이 `ws://...`로 시작하는지 확인 |
| `WebSocket handshake error 404` | URL 경로가 틀림 | `BACKEND_URL`을 `ws://<IP>:7003` 으로만 (뒤에 path 빼고) |

수정 후:
```bash
sudo systemctl restart hypercube-agent
sudo docker logs -f hypercube-agent  # 잘 붙는지 실시간 보기
```

### 10-7. 디스크 가득 참

**증상**: 설치 도중 `no space left on device`

**확인**:
```bash
df -h
```

`/` 또는 `/var/lib/docker`가 `Use% 100%`이면 공간 부족.

**해결 — 사용 안 하는 도커 데이터 정리**:
```bash
sudo docker system prune -a -f --volumes
```
⚠️ 사용 중인 다른 컨테이너의 이미지/볼륨도 지워질 수 있으니 운영팀과 협의 후 실행.

---

## 11. 그래도 안 되면 — 로그 모아서 개발팀에 보내기

위 §10에서 해결이 안 되면 **하나의 진단 패키지**를 만들어서 USB로 빌드 머신에 가져가시면 개발팀이 분석할 수 있습니다.

### 11-1. 진단 패키지 자동 수집 명령

폐쇄망 서버에서 **아래 명령을 그대로 복사해서 붙여넣고 엔터**:

```bash
sudo bash -c '
TS=$(date +%Y%m%d-%H%M%S)
DIR=/tmp/hc-diag-$TS
mkdir -p $DIR
cd $DIR

{
  echo "=== uname ==="; uname -a
  echo "=== os ==="; lsb_release -a 2>/dev/null
  echo "=== uptime ==="; uptime
  echo "=== disk ==="; df -h
  echo "=== mem ==="; free -h
  echo "=== version manifest ==="
  cat /opt/hypercube/VERSION 2>/dev/null
  cat /opt/hypercube-agent/VERSION 2>/dev/null
} > 01-system.txt

{
  echo "=== docker version ==="; docker version 2>&1
  echo "=== docker info ==="; docker info 2>&1 | head -50
  echo "=== ps -a ==="; docker ps -a
  echo "=== images ==="; docker images
} > 02-docker.txt

if [ -f /opt/hypercube/docker-compose.yml ]; then
  cd /opt/hypercube
  {
    echo "=== compose ps ==="; docker compose ps
    echo "=== compose config ==="; docker compose config
  } > $DIR/03-compose.txt 2>&1
fi

cd $DIR
mkdir -p logs
for svc in postgres redis backend nginx celery-worker celery-beat; do
  docker compose -f /opt/hypercube/docker-compose.yml logs --tail 500 --no-color $svc \
    > logs/$svc.log 2>&1 || true
done
docker logs --tail 500 hypercube-agent > logs/hypercube-agent.log 2>&1 || true

sed -E "s/^(.*PASSWORD|.*TOKEN|.*KEY|.*SECRET)=.*/\1=***REDACTED***/i" \
  /opt/hypercube/.env > 04-env-redacted.txt 2>/dev/null || true
sed -E "s/^(.*PASSWORD|.*TOKEN|.*KEY|.*SECRET)=.*/\1=***REDACTED***/i" \
  /opt/hypercube-agent/.env >> 04-env-redacted.txt 2>/dev/null || true

{
  echo "=== systemd hypercube ==="; systemctl status hypercube --no-pager -l 2>&1
  echo "=== systemd docker ==="; systemctl status docker --no-pager -l 2>&1
  echo "=== systemd hypercube-agent ==="; systemctl status hypercube-agent --no-pager -l 2>&1
  echo "=== journal hypercube ==="; journalctl -u hypercube -n 100 --no-pager 2>&1
  echo "=== journal docker ==="; journalctl -u docker -n 100 --no-pager 2>&1
} > 05-systemd.txt

{
  echo "=== dmesg tail ==="; dmesg | tail -100
  echo "=== ports ==="; ss -tlnp 2>/dev/null
  echo "=== ip ==="; ip a
} > 06-kernel-net.txt

{
  echo "=== /api/health/ ==="
  curl -fsS --max-time 5 http://localhost:7003/api/health/ 2>&1
  echo
  echo "=== / (head) ==="
  curl -fsS --max-time 5 -I http://localhost:7003/ 2>&1
} > 07-healthcheck.txt

cd /tmp
tar czf hc-diag-$TS.tar.gz hc-diag-$TS/
sha256sum hc-diag-$TS.tar.gz > hc-diag-$TS.tar.gz.sha256
ls -lh /tmp/hc-diag-$TS.tar.gz*

echo
echo "==============================================="
echo "  DIAGNOSTIC BUNDLE: /tmp/hc-diag-$TS.tar.gz"
echo "  USB로 복사해서 개발팀에 전달하세요."
echo "==============================================="
'
```

명령이 끝나면 약 1~5MB 크기의 `tar.gz` 파일이 `/tmp/`에 만들어집니다.

### 11-2. USB로 옮기기

```bash
sudo cp /tmp/hc-diag-*.tar.gz /media/usb/
sudo cp /tmp/hc-diag-*.sha256 /media/usb/
```

(`/media/usb/`는 USB 마운트 경로 — 환경에 따라 다를 수 있으니 운영팀에 확인)

### 11-3. 개발팀에 같이 보낼 정보 (메일/메신저용)

진단 파일과 함께 다음 양식으로 짧게 적어주시면 분석이 훨씬 빨라집니다:

```
[증상]
  예: agent가 backend에 안 붙음. admin 페이지의 Agents가 빈 채로 유지됨

[발생 시점]
  예: 2026-05-06 14:30 즈음, agent를 192.168.0.20에 새로 설치한 직후

[지속 시간]
  예: 30분째 동일

[재현]
  예: agent를 재시작하면 잠깐 붙었다가 다시 끊김

[운영자가 시도한 것]
  - docker compose restart backend → 변화 없음
  - .env 수정해서 ALLOWED_HOSTS에 IP 추가 → 안 됨

[첨부]
  hc-diag-20260506-143000.tar.gz
```

---

## 12. 자주 묻는 질문 (FAQ)

### Q1. 인터넷이 진짜로 0% 필요한가요?

**네**. 인스톨러 안에 모든 게(Docker 엔진, Postgres, Redis, Python, Node 등 다) 들어있습니다. 외부 어떤 서버에도 접속하지 않고 동작합니다.

### Q2. 재부팅 후 자동으로 시작되나요?

**네**. systemd unit이 자동 등록되어 부팅 시 자동 시작됩니다.

### Q3. Backend 서버 IP가 바뀌면 어떻게 하나요?

`.env` 두 곳을 수정해야 합니다:

**Backend 서버**:
```bash
sudo nano /opt/hypercube/.env
# DJANGO_ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS, HC_HOST 줄의 IP 수정
sudo systemctl restart hypercube
```

**Agent가 깔린 모든 서버**:
```bash
sudo nano /opt/hypercube-agent/.env
# BACKEND_URL, BACKEND_API_URL 줄의 IP 수정
sudo systemctl restart hypercube-agent
```

### Q4. DB 비밀번호 잊어버렸어요

`.env`에 평문으로 들어있습니다:
```bash
sudo cat /opt/hypercube/.env | grep DB_PASSWORD
```

### Q5. 한 서버에 여러 backend를 띄울 수 있나요?

권장하지 않습니다. 굳이 한다면 `.env`에서 포트 + DB명을 다르게 해야 합니다. 운영팀 / 개발팀과 협의 후 진행하세요.

### Q6. Agent를 100대 이상 깔아도 되나요?

기본 설정은 50대까지 권장. 그 이상이면 backend 서버 사양을 높이고 일부 설정 튜닝이 필요합니다 — 개발팀에 문의.

### Q7. 인스톨러를 두 번 실행하면 어떻게 되나요?

기존 설정과 데이터는 보존되고, 컨테이너만 재시작됩니다 (= 업그레이드와 같은 동작). 안전합니다.

### Q8. 22.04와 24.04를 분리해서 따로 받아야 하나요?

**아닙니다.** 인스톨러 한 파일(`hypercube-X.Y.sh`)이 22.04(jammy)와 24.04(noble) **둘 다 지원**합니다. 호스트 OS는 인스톨러가 자동 감지해서 맞는 Docker `.deb`을 사용해요.

20.04(focal) 같이 더 오래된 버전은 별도 빌드가 필요하니 개발팀 문의.

---

## 13. 용어 사전 — 가이드에 나온 단어들

| 단어 | 뜻 |
|------|-----|
| **컨테이너 (container)** | 격리된 공간에서 도는 작은 가상 환경. 호스트 OS와 분리됨 |
| **이미지 (image)** | 컨테이너를 만들 수 있는 "설계도" 같은 것 |
| **Docker** | 컨테이너를 띄워주는 프로그램 |
| **systemd** | Linux의 서비스 관리자. 자동 시작/중지/재시작 담당 |
| **systemctl** | systemd를 다루는 명령. 예: `systemctl start`, `systemctl status` |
| **PostgreSQL** | 데이터베이스. 줄여서 `postgres` |
| **Redis** | 메모리 기반 캐시 데이터베이스 |
| **Nginx** | 웹 서버. 브라우저 요청을 받아 backend로 전달 |
| **WebSocket / ws://** | 실시간 양방향 통신용 프로토콜. agent ↔ backend가 이걸로 통신 |
| **REST API / http://** | 일반적인 HTTP 요청 방식 |
| **호스트 (host)** | 컨테이너가 도는 진짜 서버 (= 폐쇄망 서버) |
| **호스트네임 (hostname)** | 그 서버의 이름 |
| **healthcheck** | 서비스가 정상 동작하는지 자동 점검 |
| **마이그레이션 (migration)** | 데이터베이스 스키마 변경을 적용하는 작업 |
| **enrollment / approve** | agent를 backend에 등록하고 승인하는 절차 |
| **.env 파일** | 설정값들이 들어있는 파일 (DB 비번, 호스트 IP 등) |
| **.run / .sh 인스톨러** | 자동 압축 풀고 설치까지 한 번에 해주는 단일 파일 |

---

## 14. 빌드 머신 체크리스트 (개발자용)

새로운 `.sh` 파일을 만들 때 사용 (이 문서를 USB로 가져가는 운영자용 아닙니다):

- [ ] `./packaging/build.sh` 종료 코드 0
- [ ] `dist/hypercube-X.Y.sh` 존재
- [ ] `--check`로 무결성 OK 확인
- [ ] 크기 ~320MB (Docker 엔진 미포함, 이미지만)
- [ ] `packaging/test-airgap` 시뮬레이터에서 검증 완료 (Docker 사전 설치된 컨테이너)
- [ ] 깨끗한 Ubuntu/RHEL VM에서 1회 설치 검증 (가능하면 — Docker 사전 설치 후)
- [ ] 헬스체크 200 OK
- [ ] `sha256sum`으로 해시 기록 (USB에 같이 넣음)

빌드 명령:
```bash
./packaging/build.sh
```

산출물 1개:
```
dist/hypercube-X.Y.sh    ← OS 무관 (Docker만 있으면 동작)
```

운영자에게 줄 때는 OS 버전에 맞는 `.sh` 한 개만 USB에 넣으면 됩니다.
