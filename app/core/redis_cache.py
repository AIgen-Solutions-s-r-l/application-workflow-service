"""
Redis distributed caching layer with circuit breaker and fallback support.

Provides:
- Async Redis client with connection pooling
- Circuit breaker pattern for graceful degradation
- Automatic fallback to in-memory cache
- Key building utilities with namespacing
- Prometheus metrics integration
"""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.core.config import settings
from app.log.logging import logger


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreaker:
    """
    Circuit breaker to prevent cascading failures.

    When Redis fails repeatedly, the circuit opens and requests
    are routed to the fallback cache instead.
    """

    failure_threshold: int = 5
    reset_timeout: float = 30.0  # seconds
    _state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    _failure_count: int = field(default=0, init=False)
    _last_failure_time: float = field(default=0.0, init=False)
    _success_count: int = field(default=0, init=False)

    @property
    def state(self) -> CircuitState:
        """Get current circuit state, checking for timeout."""
        if (
            self._state == CircuitState.OPEN
            and time.time() - self._last_failure_time >= self.reset_timeout
        ):
            self._state = CircuitState.HALF_OPEN
            self._success_count = 0
        return self._state

    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed (normal operation)."""
        return self.state == CircuitState.CLOSED

    def record_failure(self) -> None:
        """Record a failure and potentially open the circuit."""
        self._failure_count += 1
        self._last_failure_time = time.time()

        if self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN
            logger.warning(
                f"Circuit breaker opened after {self._failure_count} failures",
                extra={"circuit_state": "open"},
            )

    def record_success(self) -> None:
        """Record a success and potentially close the circuit."""
        if self._state == CircuitState.HALF_OPEN and self._success_count >= 0:
            self._success_count += 1
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            logger.info("Circuit breaker closed", extra={"circuit_state": "closed"})
        elif self._state == CircuitState.CLOSED:
            self._failure_count = 0


class CacheKey:
    """Utility for building cache keys with consistent namespacing."""

    DEFAULT_PREFIX = "app_manager"

    @classmethod
    def build(cls, *parts: str, prefix: str | None = None) -> str:
        """
        Build a cache key from parts.

        Args:
            *parts: Key components to join.
            prefix: Optional custom prefix (defaults to app_manager).

        Returns:
            Namespaced cache key.
        """
        key_prefix = prefix or cls.DEFAULT_PREFIX
        return ":".join([key_prefix, *parts])

    @classmethod
    def rate_limit(cls, user_id: str, endpoint: str) -> str:
        """Build rate limit key."""
        return cls.build("ratelimit", user_id, endpoint)

    @classmethod
    def idempotency(cls, key: str) -> str:
        """Build idempotency key."""
        return cls.build("idempotency", key)

    @classmethod
    def application(cls, app_id: str) -> str:
        """Build application status key."""
        return cls.build("app", app_id, "status")

    @classmethod
    def user_apps(cls, user_id: str) -> str:
        """Build user applications list key."""
        return cls.build("user", user_id, "apps")


class CacheInterface(ABC):
    """Abstract interface for cache implementations."""

    @abstractmethod
    async def get(self, key: str) -> str | None:
        """Get a value from cache."""
        pass

    @abstractmethod
    async def set(self, key: str, value: str, ttl: int | None = None) -> None:
        """Set a value in cache."""
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete a key from cache."""
        pass

    @abstractmethod
    async def delete_pattern(self, pattern: str) -> int:
        """Delete keys matching a pattern."""
        pass

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if a key exists."""
        pass

    @abstractmethod
    async def incr(self, key: str, amount: int = 1) -> int:
        """Increment a counter."""
        pass

    @abstractmethod
    async def expire(self, key: str, ttl: int) -> None:
        """Set TTL on a key."""
        pass

    @abstractmethod
    async def ping(self) -> bool:
        """Check if cache is available."""
        pass

    @abstractmethod
    async def info(self) -> dict:
        """Get cache server info."""
        pass


class RedisCache(CacheInterface):
    """
    Redis cache implementation with circuit breaker and fallback.

    Features:
    - Async Redis operations
    - Connection pooling
    - Circuit breaker for fault tolerance
    - Automatic fallback to in-memory cache
    - Prometheus metrics
    """

    def __init__(
        self,
        redis_url: str,
        default_ttl: int = 300,
        key_prefix: str = "app_manager",
        fallback_to_memory: bool = True,
        failure_threshold: int = 5,
        reset_timeout: float = 30.0,
    ):
        """
        Initialize Redis cache.

        Args:
            redis_url: Redis connection URL.
            default_ttl: Default TTL in seconds.
            key_prefix: Prefix for all keys.
            fallback_to_memory: Enable fallback to in-memory cache.
            failure_threshold: Failures before circuit opens.
            reset_timeout: Seconds before circuit half-opens.
        """
        self._redis_url = redis_url
        self._default_ttl = default_ttl
        self._key_prefix = key_prefix
        self._fallback_to_memory = fallback_to_memory
        self._redis: Any = None
        self._connected = False
        self._fallback_cache: Any = None
        self._circuit_breaker = CircuitBreaker(
            failure_threshold=failure_threshold, reset_timeout=reset_timeout
        )

        # Initialize fallback cache if enabled
        if fallback_to_memory:
            from app.core.cache import LRUCache

            self._fallback_cache = LRUCache(
                max_size=1000, default_ttl=float(default_ttl), name="redis_fallback"
            )

        CacheKey.DEFAULT_PREFIX = key_prefix

    async def connect(self) -> bool:
        """
        Establish Redis connection.

        Returns:
            True if connected successfully.
        """
        if self._connected:
            return True

        try:
            import redis.asyncio as redis

            self._redis = redis.from_url(
                self._redis_url,
                encoding="utf-8",
                decode_responses=False,  # We handle decoding
            )
            await self._redis.ping()
            self._connected = True
            logger.info("Connected to Redis", extra={"url": self._redis_url.split("@")[-1]})
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self._connected = False
            return False

    async def disconnect(self) -> None:
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()
            self._connected = False
            logger.info("Disconnected from Redis")

    def _should_use_fallback(self) -> bool:
        """Check if we should use fallback cache."""
        return self._fallback_to_memory and (
            not self._connected or not self._circuit_breaker.is_closed
        )

    async def _execute_with_fallback(
        self,
        redis_op: str,
        fallback_op: str,
        key: str,
        *args,
        **kwargs,
    ) -> Any:
        """
        Execute operation with fallback support.

        Args:
            redis_op: Name of Redis method to call.
            fallback_op: Name of fallback method to call.
            key: Cache key.
            *args: Additional arguments.
            **kwargs: Additional keyword arguments.

        Returns:
            Operation result.
        """
        # Check circuit breaker
        if self._circuit_breaker.state == CircuitState.OPEN:
            if self._fallback_cache:
                return getattr(self._fallback_cache, fallback_op)(key, *args)
            return None

        # Try Redis
        try:
            method = getattr(self._redis, redis_op)
            result = await method(key, *args, **kwargs)
            self._circuit_breaker.record_success()
            return result
        except Exception as e:
            logger.warning(f"Redis {redis_op} failed: {e}", extra={"key": key})
            self._circuit_breaker.record_failure()

            # Fallback
            if self._fallback_cache and fallback_op:
                return getattr(self._fallback_cache, fallback_op)(key, *args)
            return None

    async def get(self, key: str) -> str | None:
        """Get a value from cache."""
        if self._should_use_fallback() and self._fallback_cache:
            return self._fallback_cache.get(key)

        try:
            if not self._circuit_breaker.is_closed:
                if self._fallback_cache:
                    return self._fallback_cache.get(key)
                return None

            result = await self._redis.get(key)
            self._circuit_breaker.record_success()

            if result is None:
                return None
            return result.decode("utf-8") if isinstance(result, bytes) else result
        except Exception as e:
            logger.warning(f"Redis get failed: {e}", extra={"key": key})
            self._circuit_breaker.record_failure()
            if self._fallback_cache:
                return self._fallback_cache.get(key)
            return None

    async def set(self, key: str, value: str, ttl: int | None = None) -> None:
        """Set a value in cache."""
        effective_ttl = ttl or self._default_ttl

        if self._should_use_fallback() and self._fallback_cache:
            self._fallback_cache.set(key, value, float(effective_ttl))
            return

        try:
            if not self._circuit_breaker.is_closed:
                if self._fallback_cache:
                    self._fallback_cache.set(key, value, float(effective_ttl))
                return

            await self._redis.set(key, value, ex=effective_ttl)
            self._circuit_breaker.record_success()
        except Exception as e:
            logger.warning(f"Redis set failed: {e}", extra={"key": key})
            self._circuit_breaker.record_failure()
            if self._fallback_cache:
                self._fallback_cache.set(key, value, float(effective_ttl))

    async def delete(self, key: str) -> bool:
        """Delete a key from cache."""
        if self._should_use_fallback() and self._fallback_cache:
            return self._fallback_cache.delete(key)

        try:
            result = await self._redis.delete(key)
            self._circuit_breaker.record_success()
            return result > 0
        except Exception as e:
            logger.warning(f"Redis delete failed: {e}", extra={"key": key})
            self._circuit_breaker.record_failure()
            if self._fallback_cache:
                return self._fallback_cache.delete(key)
            return False

    async def delete_pattern(self, pattern: str) -> int:
        """Delete keys matching a pattern."""
        if self._should_use_fallback() and self._fallback_cache:
            # In-memory cache uses prefix matching
            return self._fallback_cache.invalidate_pattern(pattern.rstrip("*"))

        try:
            count = 0
            cursor = 0
            while True:
                cursor, keys = await self._redis.scan(cursor=cursor, match=pattern, count=100)
                if keys:
                    for key in keys:
                        await self._redis.delete(key)
                        count += 1
                if cursor == 0:
                    break
            self._circuit_breaker.record_success()
            return count
        except Exception as e:
            logger.warning(f"Redis delete_pattern failed: {e}", extra={"pattern": pattern})
            self._circuit_breaker.record_failure()
            if self._fallback_cache:
                return self._fallback_cache.invalidate_pattern(pattern.rstrip("*"))
            return 0

    async def exists(self, key: str) -> bool:
        """Check if a key exists."""
        if self._should_use_fallback() and self._fallback_cache:
            return self._fallback_cache.get(key) is not None

        try:
            result = await self._redis.exists(key)
            self._circuit_breaker.record_success()
            return result > 0
        except Exception as e:
            logger.warning(f"Redis exists failed: {e}", extra={"key": key})
            self._circuit_breaker.record_failure()
            if self._fallback_cache:
                return self._fallback_cache.get(key) is not None
            return False

    async def incr(self, key: str, amount: int = 1) -> int:
        """Increment a counter."""
        if self._should_use_fallback():
            # Fallback doesn't support atomic increment well
            logger.warning("incr operation not supported in fallback mode")
            return 0

        try:
            result = await self._redis.incr(key, amount)
            self._circuit_breaker.record_success()
            return result
        except Exception as e:
            logger.warning(f"Redis incr failed: {e}", extra={"key": key})
            self._circuit_breaker.record_failure()
            return 0

    async def expire(self, key: str, ttl: int) -> None:
        """Set TTL on a key."""
        if self._should_use_fallback():
            return  # Fallback doesn't support dynamic TTL

        try:
            await self._redis.expire(key, ttl)
            self._circuit_breaker.record_success()
        except Exception as e:
            logger.warning(f"Redis expire failed: {e}", extra={"key": key})
            self._circuit_breaker.record_failure()

    async def ping(self) -> bool:
        """Check if Redis is available."""
        try:
            await self._redis.ping()
            return True
        except Exception:
            return False

    async def info(self) -> dict:
        """Get Redis server info."""
        try:
            return await self._redis.info()
        except Exception as e:
            logger.warning(f"Redis info failed: {e}")
            return {"error": str(e)}

    @property
    def is_connected(self) -> bool:
        """Check if connected to Redis."""
        return self._connected

    @property
    def circuit_state(self) -> CircuitState:
        """Get current circuit breaker state."""
        return self._circuit_breaker.state


# Global cache instance
_cache_instance: CacheInterface | None = None


def get_cache() -> CacheInterface:
    """
    Get or create the cache instance.

    Returns Redis cache if enabled and configured,
    otherwise returns in-memory LRU cache.
    """
    global _cache_instance

    if _cache_instance is not None:
        return _cache_instance

    # Check if Redis is enabled
    cache_enabled = getattr(settings, "cache_enabled", False)

    if cache_enabled:
        redis_url = getattr(settings, "redis_url", "redis://localhost:6379/0")
        default_ttl = getattr(settings, "cache_default_ttl", 300)
        key_prefix = getattr(settings, "cache_key_prefix", "app_manager")
        fallback = getattr(settings, "cache_fallback_to_memory", True)

        _cache_instance = RedisCache(
            redis_url=redis_url,
            default_ttl=default_ttl,
            key_prefix=key_prefix,
            fallback_to_memory=fallback,
        )
    else:
        # Use in-memory cache as default
        from app.core.cache import LRUCache

        _cache_instance = LRUCache(max_size=1000, default_ttl=300.0, name="default")

    return _cache_instance


async def init_cache() -> bool:
    """
    Initialize cache connection.

    Should be called during application startup.

    Returns:
        True if initialization successful.
    """
    cache = get_cache()
    if isinstance(cache, RedisCache):
        return await cache.connect()
    return True


async def close_cache() -> None:
    """
    Close cache connection.

    Should be called during application shutdown.
    """
    global _cache_instance
    if isinstance(_cache_instance, RedisCache):
        await _cache_instance.disconnect()
    _cache_instance = None
