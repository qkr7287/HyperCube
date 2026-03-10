# 🐳 AGICS Container Monitor Docker 배포 가이드

## 📋 개요

AGICS Container Monitor를 Docker 컨테이너로 배포하여 Docker 환경에서 실행 중인 컨테이너들을 모니터링할 수 있습니다.

## 🚀 빠른 시작

### 1. 자동 배포 (권장)

```bash
# 배포 스크립트 실행
./deploy.sh
```

### 2. 수동 배포

```bash
# Docker Compose로 배포
docker-compose up -d

# 또는 Docker 명령어로 직접 빌드 및 실행
docker build -t agics-container-monitor .
docker run -d \
  --name agics-container-monitor \
  -p 5173:5173 \
  -v /var/run/docker.sock:/var/run/docker.sock:ro \
  -v /proc:/host/proc:ro \
  -v /sys:/host/sys:ro \
  -v /etc:/host/etc:ro \
  --privileged \
  agics-container-monitor
```

## 🔧 설정

### 포트 설정
- **호스트 포트**: 3333
- **컨테이너 포트**: 5173
- **매핑**: `3333:5173` (호스트:컨테이너)
- **변경 방법**: `docker-compose.yml`에서 `ports` 섹션 수정

### 볼륨 마운트
- `/var/run/docker.sock`: Docker API 접근
- `/proc`, `/sys`, `/etc`: 시스템 정보 수집

### 환경 변수
- `NODE_ENV=production`: 프로덕션 모드
- `HOST=0.0.0.0`: 모든 인터페이스에서 접근 허용
- `PORT=5173`: 컨테이너 내부 애플리케이션 포트

## 📊 모니터링 기능

### 컨테이너 모니터링
- ✅ 실시간 컨테이너 상태
- ✅ CPU/메모리 사용률
- ✅ 네트워크/디스크 I/O
- ✅ 컨테이너 로그

### 프로젝트 그룹화
- ✅ Docker Compose 프로젝트별 그룹화
- ✅ 컨테이너 타입 분석
- ✅ 프로젝트별 통계

### 서버 모니터링
- ✅ 시스템 리소스 사용률
- ✅ 네트워크 연결 상태
- ✅ 로그인 사용자
- ✅ 프로세스 정보

## 🛠️ 관리 명령어

### 컨테이너 관리
```bash
# 컨테이너 시작
docker-compose up -d

# 컨테이너 중지
docker-compose down

# 컨테이너 재시작
docker-compose restart

# 로그 확인
docker-compose logs -f

# 컨테이너 상태 확인
docker ps | grep agics-container-monitor
```

### 업데이트
```bash
# 최신 코드로 재빌드
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

## 🔒 보안 고려사항

### 권한 설정
- `privileged: true`: 시스템 정보 접근을 위해 필요
- Docker 소켓은 읽기 전용으로 마운트

### 네트워크 보안
- 내부 네트워크에서만 접근하도록 방화벽 설정 권장
- 필요시 HTTPS 프록시 사용

## 🌐 접속

배포 완료 후 다음 URL로 접속:
- **로컬**: http://localhost:3333
- **원격**: http://[서버IP]:3333

## 📝 로그

### 애플리케이션 로그
```bash
docker-compose logs -f container-monitor
```

### Docker 로그
```bash
docker logs agics-container-monitor
```

## 🔧 문제 해결

### 포트 충돌
```bash
# 포트 사용 중인 프로세스 확인
sudo netstat -tulpn | grep 3333

# 포트 변경
# docker-compose.yml에서 ports 섹션 수정
```

### 권한 문제
```bash
# Docker 소켓 권한 확인
ls -la /var/run/docker.sock

# 사용자를 docker 그룹에 추가
sudo usermod -aG docker $USER
```

### 컨테이너 시작 실패
```bash
# 상세 로그 확인
docker-compose logs

# 컨테이너 내부 접속
docker exec -it agics-container-monitor sh
```

## 📈 성능 최적화

### 리소스 제한
```yaml
# docker-compose.yml에 추가
deploy:
  resources:
    limits:
      memory: 512M
      cpus: '0.5'
```

### 헬스체크
- 30초마다 헬스체크 실행
- 3초 타임아웃
- 3회 재시도

## 🎯 프로덕션 배포

### 1. 환경 변수 설정
```bash
# .env 파일 생성
echo "NODE_ENV=production" > .env
echo "HOST=0.0.0.0" >> .env
echo "PORT=5173" >> .env
```

### 2. 리버스 프록시 설정 (Nginx)
```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    location / {
        proxy_pass http://localhost:3333;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### 3. SSL 인증서 설정
```bash
# Let's Encrypt 사용
sudo certbot --nginx -d your-domain.com
```

## 📞 지원

문제가 발생하면 다음을 확인하세요:
1. Docker 및 Docker Compose 설치 상태
2. 포트 5173 사용 가능 여부
3. Docker 소켓 권한
4. 시스템 리소스 사용량

---

**AGICS Container Monitor** - Docker 환경의 모든 컨테이너를 한눈에! 🐳✨
