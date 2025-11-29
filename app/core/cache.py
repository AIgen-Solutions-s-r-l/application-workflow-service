"""
In-memory caching with TTL support for performance optimization.

Provides:
- LRU cache with TTL for frequently accessed data
- Async-compatible caching decorators
- Cache statistics for monitoring
"""
import asyncio
import hashlib
import json
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Callable, Optional, TypeVar, ParamSpec
from threading import Lock

from app.core.config import settings
from app.log.logging import logger


P = ParamSpec("P")
T = TypeVar("T")


@dataclass
class CacheEntry:
    """Represents a cached value with metadata."""
    value: Any
    created_at: float
    ttl: float
    hits: int = 0

    @property
    def is_expired(self) -> bool:
        """Check if the cache entry has expired."""
        return time.time() - self.created_at > self.ttl


@dataclass
class CacheStats:
    """Cache statistics for monitoring."""
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    size: int = 0
    max_size: int = 0

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "size": self.size,
            "max_size": self.max_size,
            "hit_rate": round(self.hit_rate, 4)
        }


class LRUCache:
    """
    Thread-safe LRU cache with TTL support.

    Features:
    - Configurable max size and default TTL
    - Automatic eviction of expired entries
    - Statistics tracking for monitoring
    """

    def __init__(
        self,
        max_size: int = 1000,
        default_ttl: float = 300.0,
        name: str = "default"
    ):
        """
        Initialize the LRU cache.

        Args:
            max_size: Maximum number of entries.
            default_ttl: Default TTL in seconds.
            name: Cache name for logging.
        """
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = Lock()
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._name = name
        self._stats = CacheStats(max_size=max_size)

    def _make_key(self, *args, **kwargs) -> str:
        """Generate a cache key from arguments."""
        key_data = json.dumps(
            {"args": args, "kwargs": kwargs},
            sort_keys=True,
            default=str
        )
        return hashlib.sha256(key_data.encode()).hexdigest()[:32]

    def get(self, key: str) -> Optional[Any]:
        """
        Get a value from cache.

        Args:
            key: Cache key.

        Returns:
            Cached value or None if not found/expired.
        """
        with self._lock:
            entry = self._cache.get(key)

            if entry is None:
                self._stats.misses += 1
                return None

            if entry.is_expired:
                del self._cache[key]
                self._stats.misses += 1
                self._stats.evictions += 1
                self._stats.size = len(self._cache)
                return None

            # Move to end (most recently used)
            self._cache.move_to_end(key)
            entry.hits += 1
            self._stats.hits += 1
            return entry.value

    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        """
        Set a value in cache.

        Args:
            key: Cache key.
            value: Value to cache.
            ttl: Optional TTL override.
        """
        with self._lock:
            # Evict expired entries periodically
            if len(self._cache) >= self._max_size:
                self._evict_expired()

            # Evict LRU if still at capacity
            while len(self._cache) >= self._max_size:
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]
                self._stats.evictions += 1

            self._cache[key] = CacheEntry(
                value=value,
                created_at=time.time(),
                ttl=ttl or self._default_ttl
            )
            self._cache.move_to_end(key)
            self._stats.size = len(self._cache)

    def delete(self, key: str) -> bool:
        """
        Delete a value from cache.

        Args:
            key: Cache key.

        Returns:
            True if key was deleted, False if not found.
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                self._stats.size = len(self._cache)
                return True
            return False

    def clear(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            self._cache.clear()
            self._stats.size = 0

    def _evict_expired(self) -> int:
        """
        Evict all expired entries.

        Returns:
            Number of entries evicted.
        """
        now = time.time()
        expired_keys = [
            key for key, entry in self._cache.items()
            if now - entry.created_at > entry.ttl
        ]

        for key in expired_keys:
            del self._cache[key]

        self._stats.evictions += len(expired_keys)
        self._stats.size = len(self._cache)
        return len(expired_keys)

    @property
    def stats(self) -> CacheStats:
        """Get cache statistics."""
        with self._lock:
            self._stats.size = len(self._cache)
            return self._stats

    def invalidate_pattern(self, pattern: str) -> int:
        """
        Invalidate all keys matching a pattern (prefix match).

        Args:
            pattern: Key prefix to match.

        Returns:
            Number of keys invalidated.
        """
        with self._lock:
            keys_to_delete = [
                key for key in self._cache.keys()
                if key.startswith(pattern)
            ]

            for key in keys_to_delete:
                del self._cache[key]

            self._stats.size = len(self._cache)
            return len(keys_to_delete)


# Global cache instances for different purposes
application_cache = LRUCache(
    max_size=1000,
    default_ttl=60.0,  # 1 minute for application status
    name="application"
)

user_cache = LRUCache(
    max_size=500,
    default_ttl=300.0,  # 5 minutes for user data
    name="user"
)


def cached(
    cache: LRUCache,
    ttl: Optional[float] = None,
    key_prefix: str = ""
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """
    Decorator for caching synchronous function results.

    Args:
        cache: Cache instance to use.
        ttl: Optional TTL override.
        key_prefix: Optional prefix for cache keys.

    Returns:
        Decorated function.
    """
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            # Generate cache key
            key = f"{key_prefix}:{cache._make_key(*args, **kwargs)}"

            # Try to get from cache
            cached_value = cache.get(key)
            if cached_value is not None:
                return cached_value

            # Call function and cache result
            result = func(*args, **kwargs)
            cache.set(key, result, ttl)
            return result

        # Add cache control methods
        wrapper.cache_clear = lambda: cache.invalidate_pattern(key_prefix)
        wrapper.cache_stats = lambda: cache.stats

        return wrapper
    return decorator


def async_cached(
    cache: LRUCache,
    ttl: Optional[float] = None,
    key_prefix: str = ""
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """
    Decorator for caching async function results.

    Args:
        cache: Cache instance to use.
        ttl: Optional TTL override.
        key_prefix: Optional prefix for cache keys.

    Returns:
        Decorated async function.
    """
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            # Generate cache key
            key = f"{key_prefix}:{cache._make_key(*args, **kwargs)}"

            # Try to get from cache
            cached_value = cache.get(key)
            if cached_value is not None:
                return cached_value

            # Call function and cache result
            result = await func(*args, **kwargs)
            cache.set(key, result, ttl)
            return result

        # Add cache control methods
        wrapper.cache_clear = lambda: cache.invalidate_pattern(key_prefix)
        wrapper.cache_stats = lambda: cache.stats

        return wrapper
    return decorator


def invalidate_user_cache(user_id: str) -> None:
    """
    Invalidate all cache entries for a specific user.

    Args:
        user_id: User ID to invalidate.
    """
    pattern = f"user:{user_id}"
    count = user_cache.invalidate_pattern(pattern)
    if count > 0:
        logger.debug(f"Invalidated {count} cache entries for user {user_id}")


def invalidate_application_cache(application_id: str) -> None:
    """
    Invalidate cache entries for a specific application.

    Args:
        application_id: Application ID to invalidate.
    """
    pattern = f"app:{application_id}"
    count = application_cache.invalidate_pattern(pattern)
    if count > 0:
        logger.debug(f"Invalidated {count} cache entries for application {application_id}")


def get_all_cache_stats() -> dict:
    """
    Get statistics for all cache instances.

    Returns:
        Dictionary with cache statistics.
    """
    return {
        "application_cache": application_cache.stats.to_dict(),
        "user_cache": user_cache.stats.to_dict()
    }
