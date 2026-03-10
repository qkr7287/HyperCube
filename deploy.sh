#!/bin/bash

# AGICS Container Monitor Docker 배포 스크립트

echo "🚀 AGICS Container Monitor 배포 시작..."

# 기존 컨테이너 정리
echo "📦 기존 컨테이너 정리 중..."
docker compose down

# 이미지 빌드
echo "🔨 Docker 이미지 빌드 중..."
docker compose build --no-cache

# 컨테이너 시작
echo "▶️  컨테이너 시작 중..."
docker compose up -d

# 상태 확인
echo "📊 배포 상태 확인 중..."
sleep 5

# 컨테이너 상태 확인
if docker ps | grep -q "dcm-frontend"; then
    echo "✅ 배포 성공!"
    echo "🌐 접속 URL: http://localhost:3334"
    echo "📋 컨테이너 상태:"
    docker ps | grep dcm-frontend
else
    echo "❌ 배포 실패!"
    echo "📋 로그 확인:"
    docker compose logs
    exit 1
fi

echo "🎉 AGICS Container Monitor가 성공적으로 배포되었습니다!"
