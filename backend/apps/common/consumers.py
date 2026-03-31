import json

from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models import AnonymousUser


class MonitoringConsumer(AsyncWebsocketConsumer):
    """
    서버 모니터링 WebSocket Hub.

    Agent/Browser가 연결하면 server:{server_id} 그룹에 가입.
    Agent가 보낸 데이터는 같은 그룹의 모든 Browser에 브로드캐스트.
    """

    async def connect(self):
        self.server_id = self.scope["url_route"]["kwargs"]["server_id"]
        self.group_name = f"server_{self.server_id}"
        user = self.scope.get("user", AnonymousUser())

        if isinstance(user, AnonymousUser) or not user.is_authenticated:
            await self.close(code=4001)
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        await self.send(text_data=json.dumps({
            "type": "connection",
            "message": f"Connected to server {self.server_id}",
            "server_id": self.server_id,
        }))

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        """Agent/client에서 받은 데이터를 그룹에 브로드캐스트"""
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
