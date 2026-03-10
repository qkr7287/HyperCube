# Node.js 20 Alpine 이미지 사용
FROM node:20-alpine

# 필요한 패키지 설치
RUN apk add --no-cache procps net-tools iproute2

# 작업 디렉토리 설정
WORKDIR /app

# 패키지 파일 복사
COPY package*.json ./

# 의존성 설치 (빌드를 위해 모든 의존성 포함)
RUN npm ci

# 소스 코드 복사
COPY . .

# SvelteKit 빌드
RUN npm run build

# 캐시 정리만 수행 (vite preview에 필요한 의존성 유지)
RUN npm cache clean --force

# 포트 노출
EXPOSE 3334

# 헬스체크 추가
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:3334/ || exit 1

# 애플리케이션 실행
CMD ["npm", "run", "preview", "--", "--host", "0.0.0.0", "--port", "3334"]
