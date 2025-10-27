"""
Redis connection and cache management for YouTube Audit Engine.

This module provides a singleton Redis client with connection pooling
for caching and other Redis operations.

Supports both real Redis and fakeredis (for testing without Redis installation).
"""

import redis
from typing import Optional
from backend.config import get_config
from backend.utils.logging_config import get_logger

log = get_logger(__name__)

# Global Redis client instance
_redis_client: Optional[redis.Redis] = None


def get_redis_client() -> redis.Redis:
    """
    Get the Redis client instance (singleton).

    Automatically uses fakeredis if REDIS_URL starts with 'fakeredis://'.
    This allows testing without a Redis server installation.

    Returns:
        Redis client (real or fake) with connection pooling

    Example:
        >>> from backend.cache import get_redis_client
        >>> redis_client = get_redis_client()
        >>> redis_client.set('key', 'value')
    """
    global _redis_client

    if _redis_client is None:
        config = get_config()

        log.info(
            "Initializing Redis client",
            redis_url=config.redis_url,
            max_connections=config.redis_max_connections
        )

        # Check if using fakeredis
        if config.redis_url.startswith('fakeredis://'):
            log.info("Using fakeredis (testing mode - no Redis server required)")
            try:
                import fakeredis
                _redis_client = fakeredis.FakeStrictRedis(decode_responses=True)
                log.info("fakeredis client created successfully")
            except ImportError:
                log.error("fakeredis not installed. Install with: pip install fakeredis")
                raise ImportError(
                    "fakeredis is required when using fakeredis:// URL. "
                    "Install with: pip install fakeredis[lua]"
                )
        else:
            # Use real Redis
            # Create connection pool
            pool = redis.ConnectionPool.from_url(
                config.redis_url,
                max_connections=config.redis_max_connections,
                decode_responses=True,  # Automatically decode bytes to strings
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True
            )

            # Create Redis client with pool
            _redis_client = redis.Redis(connection_pool=pool)

            # Test connection
            try:
                _redis_client.ping()
                log.info("Redis connection established successfully")
            except redis.ConnectionError as e:
                log.error("Failed to connect to Redis", error=str(e))
                raise

    return _redis_client


def close_redis_client() -> None:
    """
    Close the Redis client connection.

    This should be called on application shutdown.
    """
    global _redis_client

    if _redis_client is not None:
        log.info("Closing Redis connection")
        _redis_client.close()
        _redis_client = None


def health_check() -> bool:
    """
    Check if Redis is healthy.

    Returns:
        True if Redis is responsive, False otherwise
    """
    try:
        client = get_redis_client()
        client.ping()
        return True
    except Exception as e:
        log.error("Redis health check failed", error=str(e))
        return False
