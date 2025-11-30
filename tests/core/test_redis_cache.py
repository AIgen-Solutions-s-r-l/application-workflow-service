"""Tests for Redis cache implementation."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.redis_cache import (
    CacheInterface,
    CacheKey,
    CircuitBreaker,
    CircuitState,
    RedisCache,
    get_cache,
)


class TestCacheKey:
    """Tests for CacheKey builder."""

    def test_build_simple_key(self):
        """Test building a simple cache key."""
        key = CacheKey.build("app", "123", "status")
        assert key == "app_manager:app:123:status"

    def test_build_with_custom_prefix(self):
        """Test building key with custom prefix."""
        key = CacheKey.build("user", "456", prefix="custom")
        assert key == "custom:user:456"

    def test_build_rate_limit_key(self):
        """Test building rate limit key."""
        key = CacheKey.rate_limit("user123", "/applications")
        assert key == "app_manager:ratelimit:user123:/applications"

    def test_build_idempotency_key(self):
        """Test building idempotency key."""
        key = CacheKey.idempotency("req-abc123")
        assert key == "app_manager:idempotency:req-abc123"

    def test_build_application_key(self):
        """Test building application status key."""
        key = CacheKey.application("app123")
        assert key == "app_manager:app:app123:status"

    def test_build_user_apps_key(self):
        """Test building user applications list key."""
        key = CacheKey.user_apps("user456")
        assert key == "app_manager:user:user456:apps"


class TestCircuitBreaker:
    """Tests for CircuitBreaker."""

    def test_initial_state_closed(self):
        """Test circuit breaker starts closed."""
        cb = CircuitBreaker()
        assert cb.state == CircuitState.CLOSED
        assert cb.is_closed

    def test_record_success_resets_failures(self):
        """Test recording success resets failure count."""
        cb = CircuitBreaker(failure_threshold=3)
        cb._failure_count = 2
        cb.record_success()
        assert cb._failure_count == 0

    def test_record_failure_increments_count(self):
        """Test recording failure increments count."""
        cb = CircuitBreaker(failure_threshold=3)
        cb.record_failure()
        assert cb._failure_count == 1

    def test_opens_after_threshold(self):
        """Test circuit opens after failure threshold."""
        cb = CircuitBreaker(failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert not cb.is_closed

    def test_half_open_after_reset_timeout(self):
        """Test circuit becomes half-open after reset timeout."""
        cb = CircuitBreaker(failure_threshold=2, reset_timeout=0.1)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

        # Wait for reset timeout
        import time

        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN

    def test_closes_after_success_in_half_open(self):
        """Test circuit closes after success in half-open state."""
        cb = CircuitBreaker(failure_threshold=2, reset_timeout=0.01)
        cb.record_failure()
        cb.record_failure()

        import time

        time.sleep(0.02)
        assert cb.state == CircuitState.HALF_OPEN

        cb.record_success()
        assert cb.state == CircuitState.CLOSED


class TestCacheInterface:
    """Tests for CacheInterface abstract class."""

    def test_cannot_instantiate_interface(self):
        """Test that CacheInterface cannot be instantiated directly."""
        with pytest.raises(TypeError):
            CacheInterface()


class TestRedisCache:
    """Tests for RedisCache implementation."""

    @pytest.fixture
    def mock_redis(self):
        """Create a mock Redis client."""
        mock = AsyncMock()
        mock.ping = AsyncMock(return_value=True)
        mock.get = AsyncMock(return_value=None)
        mock.set = AsyncMock(return_value=True)
        mock.delete = AsyncMock(return_value=1)
        mock.exists = AsyncMock(return_value=1)
        mock.incr = AsyncMock(return_value=1)
        mock.expire = AsyncMock(return_value=True)
        mock.scan = AsyncMock(return_value=(0, []))
        mock.info = AsyncMock(return_value={"redis_version": "7.0.0"})
        mock.close = AsyncMock()
        return mock

    @pytest.fixture
    def cache(self, mock_redis):
        """Create a RedisCache instance with mock."""
        cache = RedisCache(redis_url="redis://localhost:6379/0")
        cache._redis = mock_redis
        cache._connected = True
        return cache

    async def test_get_returns_cached_value(self, cache, mock_redis):
        """Test get returns cached value."""
        mock_redis.get.return_value = b'{"status": "success"}'
        result = await cache.get("test_key")
        assert result == '{"status": "success"}'
        mock_redis.get.assert_called_once()

    async def test_get_returns_none_on_miss(self, cache, mock_redis):
        """Test get returns None on cache miss."""
        mock_redis.get.return_value = None
        result = await cache.get("missing_key")
        assert result is None

    async def test_set_stores_value(self, cache, mock_redis):
        """Test set stores value in cache."""
        await cache.set("test_key", '{"data": "value"}', ttl=60)
        mock_redis.set.assert_called_once()

    async def test_set_with_default_ttl(self, cache, mock_redis):
        """Test set uses default TTL when not specified."""
        cache._default_ttl = 300
        await cache.set("test_key", "value")
        mock_redis.set.assert_called_once()
        # Verify TTL was passed
        call_args = mock_redis.set.call_args
        assert call_args.kwargs.get("ex") == 300 or call_args.args[-1] == 300

    async def test_delete_removes_key(self, cache, mock_redis):
        """Test delete removes key from cache."""
        result = await cache.delete("test_key")
        assert result is True
        mock_redis.delete.assert_called_once()

    async def test_delete_pattern_removes_matching_keys(self, cache, mock_redis):
        """Test delete_pattern removes keys matching pattern."""
        mock_redis.scan.return_value = (0, [b"key1", b"key2", b"key3"])
        count = await cache.delete_pattern("prefix:*")
        assert count == 3
        assert mock_redis.delete.call_count == 3

    async def test_exists_returns_true_when_key_exists(self, cache, mock_redis):
        """Test exists returns True when key exists."""
        mock_redis.exists.return_value = 1
        result = await cache.exists("test_key")
        assert result is True

    async def test_exists_returns_false_when_key_missing(self, cache, mock_redis):
        """Test exists returns False when key doesn't exist."""
        mock_redis.exists.return_value = 0
        result = await cache.exists("missing_key")
        assert result is False

    async def test_incr_increments_counter(self, cache, mock_redis):
        """Test incr increments counter and returns new value."""
        mock_redis.incr.return_value = 5
        result = await cache.incr("counter_key")
        assert result == 5

    async def test_expire_sets_ttl(self, cache, mock_redis):
        """Test expire sets TTL on key."""
        await cache.expire("test_key", 120)
        mock_redis.expire.assert_called_once()

    async def test_ping_returns_true_when_connected(self, cache, mock_redis):
        """Test ping returns True when Redis is connected."""
        result = await cache.ping()
        assert result is True

    async def test_ping_returns_false_on_error(self, cache, mock_redis):
        """Test ping returns False on Redis error."""
        mock_redis.ping.side_effect = Exception("Connection error")
        result = await cache.ping()
        assert result is False

    async def test_info_returns_redis_info(self, cache, mock_redis):
        """Test info returns Redis server info."""
        mock_redis.info.return_value = {"redis_version": "7.0.0", "used_memory": 1024}
        result = await cache.info()
        assert "redis_version" in result

    async def test_fallback_to_memory_on_redis_failure(self, mock_redis):
        """Test cache falls back to memory when Redis fails."""
        cache = RedisCache(
            redis_url="redis://localhost:6379/0", fallback_to_memory=True, failure_threshold=1
        )
        cache._redis = mock_redis
        cache._connected = True
        cache._fallback_cache = MagicMock()
        cache._fallback_cache.get = MagicMock(return_value="fallback_value")

        # Simulate Redis failure
        mock_redis.get.side_effect = Exception("Redis error")

        result = await cache.get("test_key")
        assert result == "fallback_value"
        cache._fallback_cache.get.assert_called_once()

    async def test_circuit_breaker_opens_on_failures(self, mock_redis):
        """Test circuit breaker opens after multiple failures."""
        cache = RedisCache(redis_url="redis://localhost:6379/0", failure_threshold=2)
        cache._redis = mock_redis
        cache._connected = True

        # Simulate failures
        mock_redis.get.side_effect = Exception("Redis error")

        await cache.get("key1")
        await cache.get("key2")

        assert cache._circuit_breaker.state == CircuitState.OPEN

    async def test_circuit_open_skips_redis_calls(self, cache, mock_redis):
        """Test that open circuit skips Redis calls."""
        cache._circuit_breaker._state = CircuitState.OPEN
        cache._circuit_breaker._last_failure_time = asyncio.get_event_loop().time()

        # Should not call Redis when circuit is open
        await cache.get("test_key")
        mock_redis.get.assert_not_called()


class TestGetCache:
    """Tests for get_cache factory function."""

    def test_get_cache_returns_redis_when_enabled(self):
        """Test get_cache returns RedisCache when enabled."""
        import app.core.redis_cache as redis_cache_module

        # Reset global instance
        redis_cache_module._cache_instance = None

        with patch("app.core.redis_cache.settings") as mock_settings:
            mock_settings.cache_enabled = True
            mock_settings.redis_url = "redis://localhost:6379/0"
            mock_settings.cache_default_ttl = 300
            mock_settings.cache_key_prefix = "test"
            mock_settings.cache_fallback_to_memory = True

            cache = get_cache()
            assert isinstance(cache, RedisCache)

        # Clean up
        redis_cache_module._cache_instance = None

    def test_get_cache_returns_memory_fallback_when_disabled(self):
        """Test get_cache returns memory cache when Redis disabled."""
        import app.core.redis_cache as redis_cache_module

        # Reset global instance
        redis_cache_module._cache_instance = None

        with patch("app.core.redis_cache.settings") as mock_settings:
            mock_settings.cache_enabled = False

            from app.core.cache import LRUCache

            cache = get_cache()
            assert isinstance(cache, LRUCache)

        # Clean up
        redis_cache_module._cache_instance = None


class TestRedisCacheIntegration:
    """Integration tests using fakeredis."""

    @pytest.fixture
    async def fake_redis_cache(self):
        """Create cache with fakeredis for integration testing."""
        try:
            import fakeredis.aioredis

            fake_redis = fakeredis.aioredis.FakeRedis()
            cache = RedisCache(redis_url="redis://localhost:6379/0")
            cache._redis = fake_redis
            cache._connected = True
            yield cache
            await fake_redis.close()
        except ImportError:
            pytest.skip("fakeredis not installed")

    async def test_full_cache_workflow(self, fake_redis_cache):
        """Test complete cache workflow: set, get, delete."""
        cache = fake_redis_cache

        # Set
        await cache.set("workflow:key", "test_value", ttl=60)

        # Get
        result = await cache.get("workflow:key")
        assert result == "test_value"

        # Delete
        deleted = await cache.delete("workflow:key")
        assert deleted is True

        # Verify deleted
        result = await cache.get("workflow:key")
        assert result is None

    async def test_incr_and_expire(self, fake_redis_cache):
        """Test increment and expire operations."""
        cache = fake_redis_cache

        # Increment
        count = await cache.incr("counter:test")
        assert count == 1

        count = await cache.incr("counter:test")
        assert count == 2

        # Set expiry
        await cache.expire("counter:test", 60)

        # Verify still exists
        exists = await cache.exists("counter:test")
        assert exists is True
