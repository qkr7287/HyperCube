from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from .token_serializers import CustomTokenObtainPairSerializer


class CustomTokenObtainPairView(TokenObtainPairView):
    """로그인: JWT access + refresh 토큰 발급 (user 정보 포함)"""

    serializer_class = CustomTokenObtainPairSerializer


class LogoutView(APIView):
    """로그아웃: refresh token을 blacklist에 추가"""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="로그아웃",
        description="refresh token을 무효화합니다.",
        tags=["Auth"],
    )
    def post(self, request):
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response(
                {"detail": "refresh token is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except TokenError:
            return Response(
                {"detail": "Invalid or expired token"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({"detail": "Logged out"})
