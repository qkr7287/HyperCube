# 🐳 Docker Container Monitor

SvelteKit으로 구축된 실시간 Docker 컨테이너 모니터링 웹 애플리케이션입니다.

## ✨ 주요 기능

- **실시간 컨테이너 모니터링**: 5초마다 자동으로 컨테이너 상태 업데이트
- **컨테이너 목록 보기**: 실행 중인 모든 컨테이너의 상태, 이미지, 포트 정보 표시
- **상세 정보 조회**: 각 컨테이너의 상세 설정, 리소스 사용량, 환경 변수 확인
- **로그 뷰어**: 실시간 컨테이너 로그 확인
- **컨테이너 제어**: 시작, 중지, 재시작, 삭제 등 컨테이너 관리 기능
- **반응형 UI**: 모바일과 데스크톱에서 모두 사용 가능한 현대적인 인터페이스

## 🚀 설치 및 실행

### 필요 조건

- Node.js 20.19.0 이상
- Docker가 실행 중인 시스템
- Docker API 접근 권한

### 설치

1. 의존성 설치:
```bash
npm install
```

2. 개발 서버 실행:
```bash
npm run dev
```

3. 브라우저에서 `http://localhost:5173` 접속

### 프로덕션 빌드

```bash
npm run build
npm run preview
```

## 🛠️ 기술 스택

- **Frontend**: SvelteKit 2.22.0
- **Backend**: SvelteKit API Routes
- **Docker API**: dockerode
- **Styling**: CSS3 (반응형 디자인)
- **TypeScript**: 완전한 타입 지원

## 📁 프로젝트 구조

```
src/
├── lib/
│   └── components/
│       ├── ContainerCard.svelte      # 컨테이너 카드 컴포넌트
│       └── ContainerDetails.svelte   # 컨테이너 상세 정보 모달
├── routes/
│   ├── api/
│   │   └── containers/
│   │       ├── +server.ts            # 컨테이너 목록 API
│   │       └── [id]/
│   │           ├── +server.ts        # 컨테이너 상세 정보 API
│   │           ├── logs/
│   │           │   └── +server.ts    # 컨테이너 로그 API
│   │           └── control/
│   │               └── +server.ts    # 컨테이너 제어 API
│   ├── +layout.svelte                # 메인 레이아웃
│   └── +page.svelte                  # 메인 대시보드
```

## 🔧 API 엔드포인트

### 컨테이너 목록
- `GET /api/containers` - 모든 컨테이너 목록 조회

### 컨테이너 상세 정보
- `GET /api/containers/[id]` - 특정 컨테이너 상세 정보 조회

### 컨테이너 로그
- `GET /api/containers/[id]/logs?tail=100` - 컨테이너 로그 조회

### 컨테이너 제어
- `POST /api/containers/[id]/control` - 컨테이너 제어 (start, stop, restart, pause, unpause, kill, remove)

## 🎨 UI 특징

- **현대적인 디자인**: 그라데이션 배경과 카드 기반 레이아웃
- **상태 표시**: 컨테이너 상태에 따른 색상 구분
- **반응형 그리드**: 화면 크기에 따라 자동 조정되는 컨테이너 카드 레이아웃
- **모달 인터페이스**: 상세 정보를 위한 깔끔한 모달 창
- **탭 인터페이스**: 정보와 로그를 구분하여 표시

## 🔒 보안 고려사항

- Docker API는 로컬 시스템에서만 접근 가능
- 컨테이너 제어 기능은 신중하게 사용
- 프로덕션 환경에서는 적절한 인증 및 권한 관리 필요

## 📱 브라우저 지원

- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

## 🤝 기여하기

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다.

## 🐛 문제 신고

버그를 발견하거나 기능 요청이 있으시면 GitHub Issues를 통해 알려주세요.

---

**주의**: 이 애플리케이션은 Docker API에 직접 접근하므로, 프로덕션 환경에서 사용할 때는 적절한 보안 조치를 취하시기 바랍니다.