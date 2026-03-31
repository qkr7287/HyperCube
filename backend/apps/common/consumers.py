import json

from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models import AnonymousUser


class MonitoringConsumer(AsyncWebsocketConsumer):
    """
    서버 모니터링 WebSocket Hub.

    Agent가 연결하면 데이터를 전송할 수 있고,
    Browser가 연결하면 같은 그룹의 데이터를 수신만 할 수 있다.
    """

    async def connect(self):
        self.server_id = self.scope["url_route"]["kwargs"]["server_id"]
        self.group_name = f"server_{self.server_id}"
        self.is_agent = self.scope.get("is_agent", False)
        user = self.scope.get("user", AnonymousUser())

        if isinstance(user, AnonymousUser) or not user.is_authenticated:
            await self.close(code=4001)
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        client_type = "agent" if self.is_agent else "browser"
        await self.send(text_data=json.dumps({
            "type": "connection",
            "message": f"Connected to server {self.server_id}",
            "server_id": self.server_id,
            "client_type": client_type,
        }))

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        """Agent만 데이터 전송 가능. Browser는 수신만."""
        if not self.is_agent:
            await self.send(text_data=json.dumps({
                "error": "Only agents can send data",
            }))
            return

        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({"error": "Invalid JSON"}))
            return

        data["server_id"] = self.server_id
        await self.channel_layer.group_send(
            self.group_name,
            {"type": "server_message", "data": data},
        )

    async def server_message(self, event):
        """그룹 메시지를 WebSocket으로 전달"""
        await self.send(text_data=json.dumps(event["data"]))
