"""Redis client singleton for direct cache access (Channel Layer와 분리)."""

import redis
from django.conf import settings

_client: redis.Redis | None = None


def get_redis_client() -> redis.Redis:
    """REDIS_CACHE_URL을 사용하는 lazy singleton 클라이언트.

    Channel Layer는 channels_redis가 별도로 관리하므로, 직접적인
    SET/GET/SCAN 등을 위해 별도의 Python redis 클라이언트가 필요하다.
    """
    global _client
    if _client is None:
        _client = redis.from_url(
            settings.REDIS_CACHE_URL,
            decode_responses=True,
        )
    return _client
