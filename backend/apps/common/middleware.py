from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import AccessToken


class AgentUser:
    """Agent를 Django User처럼 보이게 하는 래퍼"""

    def __init__(self, agent):
        self.agent = agent
        self.id = agent.id
        self.is_authenticated = True

    def __str__(self):
        return f"AgentUser({self.agent.hostname})"


@database_sync_to_async
def get_user_from_token(token_str):
    """JWT access token에서 user 객체를 추출"""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    try:
        token = AccessToken(token_str)
        return User.objects.get(id=token["user_id"])
    except Exception:
        return AnonymousUser()


@database_sync_to_async
def get_agent_from_token(token_str):
    """Agent 토큰으로 인증"""
    from apps.agents.models import Agent

    try:
        agent = Agent.objects.get(token=token_str, status="approved")
        return AgentUser(agent)
    except Agent.DoesNotExist:
        return AnonymousUser()


class JWTAuthMiddleware(BaseMiddleware):
    """WebSocket 연결 시 query string의 token 파라미터로 JWT/Agent 인증"""

    async def __call__(self, scope, receive, send):
        query_string = scope.get("query_string", b"").decode()
        params = parse_qs(query_string)
        token_list = params.get("token", [])

        if token_list:
            token_str = token_list[0]
            if token_str.startswith("agent_"):
                scope["user"] = await get_agent_from_token(token_str)
                scope["is_agent"] = True
            else:
                scope["user"] = await get_user_from_token(token_str)
                scope["is_agent"] = False
        else:
            scope["user"] = AnonymousUser()
            scope["is_agent"] = False

        return await super().__call__(scope, receive, send)
