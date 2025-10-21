"""
Metadata caching service for YouTube video data.

This module provides intelligent caching of YouTube video metadata
to minimize API calls and improve performance.
"""

import json
from typing import List, Dict, Optional, Set
from backend.cache import get_redis_client
from backend.utils.logging_config import get_logger

log = get_logger(__name__)


class MetadataCache:
    """
    Cache video metadata to avoid redundant YouTube API calls.

    Features:
    - Individual video caching
    - Batch get/set operations
    - Configurable TTL (Time To Live)
    - Cache hit/miss statistics
    """

    def __init__(self, ttl: int = 7 * 24 * 3600):
        """
        Initialize metadata cache.

        Args:
            ttl: Time to live in seconds (default: 7 days)
        """
        self.redis_client = get_redis_client()
        self.ttl = ttl
        self.key_prefix = "video_metadata"

        log.info("Metadata cache initialized", ttl_days=ttl // (24 * 3600))

    def _get_key(self, video_id: str) -> str:
        """Get Redis key for a video ID."""
        return f"{self.key_prefix}:{video_id}"

    def get(self, video_id: str) -> Optional[Dict]:
        """
        Get cached metadata for a single video.

        Args:
            video_id: YouTube video ID

        Returns:
            Video metadata dict or None if not cached

        Example:
            >>> cache = MetadataCache()
            >>> metadata = cache.get("dQw4w9WgXcQ")
        """
        key = self._get_key(video_id)

        try:
            data = self.redis_client.get(key)
            if data:
                log.debug("Cache hit", video_id=video_id)
                return json.loads(data)
            else:
                log.debug("Cache miss", video_id=video_id)
                return None
        except Exception as e:
            log.error("Failed to get from cache", video_id=video_id, error=str(e))
            return None

    def set(self, video_id: str, metadata: Dict) -> bool:
        """
        Cache metadata for a single video.

        Args:
            video_id: YouTube video ID
            metadata: Video metadata dictionary

        Returns:
            True if successful, False otherwise

        Example:
            >>> cache = MetadataCache()
            >>> cache.set("dQw4w9WgXcQ", {"title": "...", "views": 1000})
        """
        key = self._get_key(video_id)

        try:
            self.redis_client.setex(
                key,
                self.ttl,
                json.dumps(metadata)
            )
            log.debug("Cached video metadata", video_id=video_id)
            return True
        except Exception as e:
            log.error("Failed to cache metadata", video_id=video_id, error=str(e))
            return False

    def get_many(self, video_ids: List[str]) -> Dict[str, Dict]:
        """
        Get metadata for multiple videos (batch operation).

        Args:
            video_ids: List of YouTube video IDs

        Returns:
            Dictionary mapping video_id -> metadata (only cached videos)

        Example:
            >>> cache = MetadataCache()
            >>> results = cache.get_many(["id1", "id2", "id3"])
            >>> # Returns: {"id1": {...}, "id3": {...}}  # id2 not cached
        """
        if not video_ids:
            return {}

        log.debug("Batch cache lookup", video_count=len(video_ids))

        try:
            # Use pipeline for batch operations
            pipeline = self.redis_client.pipeline()
            for video_id in video_ids:
                pipeline.get(self._get_key(video_id))

            results = pipeline.execute()

            # Parse results
            cached = {}
            for video_id, data in zip(video_ids, results):
                if data:
                    try:
                        cached[video_id] = json.loads(data)
                    except json.JSONDecodeError as e:
                        log.warning("Invalid cached data", video_id=video_id, error=str(e))

            hit_rate = len(cached) / len(video_ids) * 100 if video_ids else 0
            log.info(
                "Batch cache lookup complete",
                requested=len(video_ids),
                cached=len(cached),
                hit_rate=f"{hit_rate:.1f}%"
            )

            return cached

        except Exception as e:
            log.error("Batch cache lookup failed", error=str(e))
            return {}

    def set_many(self, metadata_list: List[Dict]) -> int:
        """
        Cache metadata for multiple videos (batch operation).

        Args:
            metadata_list: List of metadata dictionaries, each must have 'id' key

        Returns:
            Number of successfully cached items

        Example:
            >>> cache = MetadataCache()
            >>> metadata = [
            ...     {"id": "id1", "title": "Video 1"},
            ...     {"id": "id2", "title": "Video 2"}
            ... ]
            >>> cached_count = cache.set_many(metadata)
        """
        if not metadata_list:
            return 0

        log.debug("Batch cache set", video_count=len(metadata_list))

        try:
            pipeline = self.redis_client.pipeline()
            cached_count = 0

            for metadata in metadata_list:
                video_id = metadata.get('id')
                if not video_id:
                    log.warning("Metadata missing 'id' field, skipping")
                    continue

                key = self._get_key(video_id)
                pipeline.setex(key, self.ttl, json.dumps(metadata))
                cached_count += 1

            pipeline.execute()

            log.info("Batch cache set complete", cached_count=cached_count)
            return cached_count

        except Exception as e:
            log.error("Batch cache set failed", error=str(e))
            return 0

    def delete(self, video_id: str) -> bool:
        """
        Delete cached metadata for a video.

        Args:
            video_id: YouTube video ID

        Returns:
            True if deleted, False otherwise
        """
        key = self._get_key(video_id)

        try:
            result = self.redis_client.delete(key)
            if result:
                log.debug("Deleted from cache", video_id=video_id)
            return bool(result)
        except Exception as e:
            log.error("Failed to delete from cache", video_id=video_id, error=str(e))
            return False

    def delete_many(self, video_ids: List[str]) -> int:
        """
        Delete metadata for multiple videos.

        Args:
            video_ids: List of YouTube video IDs

        Returns:
            Number of items deleted
        """
        if not video_ids:
            return 0

        try:
            keys = [self._get_key(vid) for vid in video_ids]
            deleted = self.redis_client.delete(*keys)
            log.info("Batch delete complete", deleted_count=deleted)
            return deleted
        except Exception as e:
            log.error("Batch delete failed", error=str(e))
            return 0

    def get_uncached_ids(self, video_ids: List[str]) -> List[str]:
        """
        Get list of video IDs that are not in cache.

        This is useful to determine which videos need API fetching.

        Args:
            video_ids: List of YouTube video IDs

        Returns:
            List of video IDs not in cache

        Example:
            >>> cache = MetadataCache()
            >>> all_ids = ["id1", "id2", "id3"]
            >>> uncached = cache.get_uncached_ids(all_ids)
            >>> # Fetch only uncached from API
        """
        cached = self.get_many(video_ids)
        cached_set = set(cached.keys())
        uncached = [vid for vid in video_ids if vid not in cached_set]

        log.debug(
            "Identified uncached videos",
            total=len(video_ids),
            cached=len(cached_set),
            uncached=len(uncached)
        )

        return uncached

    def clear_all(self) -> int:
        """
        Clear all cached video metadata.

        WARNING: This deletes all cached videos!

        Returns:
            Number of keys deleted
        """
        log.warning("Clearing all cached metadata")

        try:
            pattern = f"{self.key_prefix}:*"
            keys = list(self.redis_client.scan_iter(match=pattern))

            if keys:
                deleted = self.redis_client.delete(*keys)
                log.warning("Cache cleared", deleted_count=deleted)
                return deleted
            else:
                log.info("No cached items to clear")
                return 0

        except Exception as e:
            log.error("Failed to clear cache", error=str(e))
            return 0

    def get_stats(self) -> Dict[str, int]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache statistics

        Example:
            >>> cache = MetadataCache()
            >>> stats = cache.get_stats()
            >>> print(f"Cached videos: {stats['total_cached']}")
        """
        try:
            pattern = f"{self.key_prefix}:*"
            keys = list(self.redis_client.scan_iter(match=pattern))
            total_cached = len(keys)

            # Calculate total memory used (approximate)
            total_memory = 0
            if keys:
                pipeline = self.redis_client.pipeline()
                for key in keys[:100]:  # Sample first 100 for memory estimate
                    pipeline.memory_usage(key)
                memory_results = pipeline.execute()
                avg_memory = sum(m for m in memory_results if m) / len([m for m in memory_results if m])
                total_memory = int(avg_memory * total_cached)

            stats = {
                "total_cached": total_cached,
                "estimated_memory_bytes": total_memory,
                "estimated_memory_mb": round(total_memory / (1024 * 1024), 2),
                "ttl_seconds": self.ttl,
                "ttl_days": self.ttl // (24 * 3600)
            }

            log.debug("Cache stats retrieved", **stats)
            return stats

        except Exception as e:
            log.error("Failed to get cache stats", error=str(e))
            return {
                "total_cached": 0,
                "estimated_memory_bytes": 0,
                "estimated_memory_mb": 0,
                "ttl_seconds": self.ttl,
                "ttl_days": self.ttl // (24 * 3600)
            }
