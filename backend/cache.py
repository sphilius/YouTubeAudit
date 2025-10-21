"""
Redis connection and cache management for YouTube Audit Engine.

This module provides a singleton Redis client with connection pooling
for caching and other Redis operations.
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

    Returns:
        Redis client with connection pooling

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
