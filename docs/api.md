# API 명세

## 컨테이너

### GET /api/containers

전체 컨테이너 목록을 반환합니다.

**응답 예시:**
```json
{
  "success": true,
  "data": [
    {
      "id": "a1b2c3d4e5f6...",
      "shortId": "a1b2c3d4e5f6",
      "names": ["/my-container"],
      "image": "nginx:latest",
      "state": "running",
      "status": "Up 3 hours",
      "ports": [...],
      "labels": { "com.docker.compose.project": "myproject" }
    }
  ]
}
```

### GET /api/containers/[id]

특정 컨테이너의 상세 정보를 반환합니다 (Docker inspect + stats).

**응답 예시:**
```json
{
  "success": true,
  "data": {
    "inspect": {
      "Config": {
        "Cmd": ["nginx", "-g", "daemon off;"],
        "WorkingDir": "/app",
        "Env": ["NODE_ENV=production"]
      },
      "State": {
        "Status": "running",
        "StartedAt": "2026-03-16T00:00:00Z"
      }
    },
    "stats": {
      "memory_stats": { "usage": 69087232 }
    }
  }
}
```

### GET /api/containers/[id]/metrics

컨테이너의 리소스 사용량을 반환합니다.

**응답 예시:**
```json
{
  "success": true,
  "data": {
    "cpu": { "usage": 0.08, "cores": 4 },
    "memory": {
      "usage": 69087232,
      "limit": 8350298112,
      "percent": 0.83
    },
    "network": { "rx": 2516582, "tx": 838860 },
    "disk": { "read": 12698, "write": 4194304 }
  }
}
```

**단위:**
- `memory.usage`, `memory.limit`: bytes (MB 변환: / 1048576)
- `network.rx`, `network.tx`: bytes
- `disk.read`, `disk.write`: bytes

### GET /api/containers/[id]/logs?tail=100

컨테이너 로그를 반환합니다.

**Query Parameters:**
- `tail` (optional): 반환할 로그 줄 수 (기본값: 100)

**응답 예시:**
```json
{
  "success": true,
  "data": {
    "logs": ["2026-03-16 log line 1", "2026-03-16 log line 2"],
    "containerId": "a1b2c3d4e5f6"
  }
}
```

### POST /api/containers/[id]/control

컨테이너를 제어합니다.

**Request Body:**
```json
{ "action": "stop" }
```

**지원 액션:** `start`, `stop`, `restart`, `pause`, `unpause`, `kill`, `remove`

**응답 예시:**
```json
{
  "success": true,
  "message": "Container stopped successfully"
}
```

## 시스템

### GET /api/system

호스트 시스템 정보를 반환합니다 (CPU, Memory, Disk, Uptime 등).

### GET /api/system/network

네트워크 연결 정보를 반환합니다 (활성 연결, 리스닝 포트 등).

### GET /api/system/logins

현재 로그인한 사용자 정보를 반환합니다.

### GET /api/system/processes

실행 중인 프로세스 목록을 반환합니다.

## 서버

### GET /api/server/ip

서버의 IP 주소 정보를 반환합니다.

## 에러 응답

모든 API는 에러 시 다음 형식으로 응답합니다:

```json
{
  "success": false,
  "error": "에러 메시지"
}
```

| HTTP 상태 코드 | 설명 |
|---------------|------|
| 200 | 성공 |
| 400 | 잘못된 요청 (유효하지 않은 action 등) |
| 404 | 컨테이너를 찾을 수 없음 |
| 500 | 서버 내부 오류 (Docker API 연결 실패 등) |
