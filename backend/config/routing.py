from django.urls import re_path

from apps.common.consumers import GlobalEventsConsumer, MonitoringConsumer

websocket_urlpatterns = [
    re_path(r"ws/server/(?P<server_id>[^/]+)/$", MonitoringConsumer.as_asgi()),
    re_path(r"ws/global/$", GlobalEventsConsumer.as_asgi()),
]
