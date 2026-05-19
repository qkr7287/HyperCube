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
    """로그인: JWT access + refresh 토큰 발급 (user 정보 포함).

    DRF 의 ``DEFAULT_AUTHENTICATION_CLASSES`` 에 ``SessionAuthentication`` 이
    포함돼 있어 모든 unsafe POST 가 CSRF 검증을 거치는데, 외부 IP/포트포워딩
    (예: 106.255.245.242:3334 → 192.168.0.63:37003) 으로 접속하면 그 Origin
    이 ``CSRF_TRUSTED_ORIGINS`` 에 없는 한 403 으로 끊긴다. 로그인 endpoint
    는 정의상 인증 자체를 받는 자리라 session 인증 의존이 의미가 없으므로
    인증 클래스를 비워 CSRF 체인 자체를 우회한다.
    """

    serializer_class = CustomTokenObtainPairSerializer
    authentication_classes: list = []


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
