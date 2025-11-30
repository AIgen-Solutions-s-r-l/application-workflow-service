"""
Redis health check for FastAPI health check framework.
"""

import time
from dataclasses import dataclass

from app.log.logging import logger


@dataclass
class HealthCheckRedis:
    """
    Health check for Redis connectivity.

    Performs a ping operation to verify Redis is accessible.
    """

    alias: str = "redis"
    tags: tuple[str, ...] = ("cache", "redis")
    _connection_uri: str = "redis://localhost:6379/0"

    def __init__(
        self,
        connection_uri: str = "redis://localhost:6379/0",
        alias: str = "redis",
        tags: tuple[str, ...] = ("cache", "redis"),
    ):
        self._connection_uri = connection_uri
        self.alias = alias
        self.tags = tags

    async def __call__(self) -> dict:
        """
        Perform health check against Redis.

        Returns:
            Dictionary with status and latency.
        """
        start_time = time.time()

        try:
            import redis.asyncio as redis_async

            client = redis_async.from_url(
                self._connection_uri,
                encoding="utf-8",
                socket_connect_timeout=5.0,
            )

            try:
                await client.ping()
                latency_ms = (time.time() - start_time) * 1000

                return {
                    "alias": self.alias,
                    "status": "HEALTHY",
                    "latency_ms": round(latency_ms, 2),
                    "tags": list(self.tags),
                }
            finally:
                await client.aclose()

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            logger.warning(f"Redis health check failed: {e}")

            return {
                "alias": self.alias,
                "status": "UNHEALTHY",
                "latency_ms": round(latency_ms, 2),
                "error": str(e),
                "tags": list(self.tags),
            }
