"""
YouTube Data API v3 client with quota management and caching.

This module provides a production-ready YouTube API client with:
- Intelligent quota management
- Response caching to minimize API calls
- Batch request optimization
- Retry logic for transient failures
- Comprehensive error handling
"""

from typing import List, Dict, Optional
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from backend.services.metadata_cache import MetadataCache
from backend.services.quota_manager import QuotaManager
from backend.utils.logging_config import get_logger
from backend.utils.retry import exponential_backoff
from backend.exceptions import (
    YouTubeAPIError,
    QuotaExceededError,
    RateLimitError,
    EnrichmentError
)

log = get_logger(__name__)


class YouTubeAPIClient:
    """
    Production YouTube API client with quota management and error handling.

    Features:
    - Automatic batching (50 videos per request)
    - Quota tracking and prediction
    - Response caching (7-day TTL)
    - Exponential backoff retry
    - Comprehensive error handling
    """

    # YouTube API constraints
    MAX_VIDEOS_PER_REQUEST = 50
    QUOTA_COST_VIDEO_LIST = 1

    def __init__(
        self,
        api_key: str,
        quota_manager: Optional[QuotaManager] = None,
        metadata_cache: Optional[MetadataCache] = None
    ):
        """
        Initialize YouTube API client.

        Args:
            api_key: Google API key for YouTube Data API v3
            quota_manager: Optional quota manager (creates new if None)
            metadata_cache: Optional metadata cache (creates new if None)
        """
        self.api_key = api_key
        self.quota_manager = quota_manager or QuotaManager()
        self.metadata_cache = metadata_cache or MetadataCache()

        log.info("Initializing YouTube API client")

        try:
            self.youtube = build('youtube', 'v3', developerKey=api_key)
            log.info("YouTube API client initialized successfully")
        except Exception as e:
            log.error("Failed to initialize YouTube API client", error=str(e))
            raise EnrichmentError(f"Failed to initialize YouTube API: {str(e)}")

    @exponential_backoff(max_retries=3, initial_delay=2.0)
    def get_video_metadata(
        self,
        video_ids: List[str],
        use_cache: bool = True,
        force_refresh: bool = False
    ) -> List[Dict]:
        """
        Fetch metadata for multiple videos with batching and caching.

        Args:
            video_ids: List of YouTube video IDs
            use_cache: Whether to use cached data (default: True)
            force_refresh: Force API fetch even if cached (default: False)

        Returns:
            List of video metadata dictionaries

        Raises:
            QuotaExceededError: If insufficient quota
            YouTubeAPIError: If API call fails
            RateLimitError: If rate limit exceeded

        Example:
            >>> client = YouTubeAPIClient(api_key="...")
            >>> metadata = client.get_video_metadata(["dQw4w9WgXcQ", "..."])
        """
        if not video_ids:
            log.warning("get_video_metadata called with empty video_ids list")
            return []

        log.info(
            "Starting video metadata fetch",
            total_videos=len(video_ids),
            use_cache=use_cache,
            force_refresh=force_refresh
        )

        # Step 1: Check cache if enabled
        cached_metadata = {}
        uncached_ids = video_ids

        if use_cache and not force_refresh:
            cached_metadata = self.metadata_cache.get_many(video_ids)
            uncached_ids = [vid for vid in video_ids if vid not in cached_metadata]

            cache_hits = len(cached_metadata)
            cache_hit_rate = (cache_hits / len(video_ids) * 100) if video_ids else 0

            log.info(
                "Cache lookup complete",
                total_videos=len(video_ids),
                cache_hits=cache_hits,
                cache_misses=len(uncached_ids),
                hit_rate=f"{cache_hit_rate:.1f}%"
            )

        # Step 2: If all cached, return early
        if not uncached_ids:
            log.info("All videos found in cache, skipping API calls")
            return list(cached_metadata.values())

        # Step 3: Check quota availability
        num_batches = (len(uncached_ids) + self.MAX_VIDEOS_PER_REQUEST - 1) // self.MAX_VIDEOS_PER_REQUEST
        total_quota_cost = num_batches * self.QUOTA_COST_VIDEO_LIST

        quota_stats = self.quota_manager.get_stats()
        log.info(
            "Quota check",
            required_quota=total_quota_cost,
            available_quota=quota_stats['remaining'],
            quota_status=quota_stats['status']
        )

        if not self.quota_manager.can_use(total_quota_cost):
            log.error(
                "Insufficient quota for request",
                required=total_quota_cost,
                remaining=quota_stats['remaining']
            )
            raise QuotaExceededError(
                details={
                    "required": total_quota_cost,
                    "remaining": quota_stats['remaining'],
                    "reset_time": quota_stats['reset_time']
                }
            )

        # Step 4: Fetch from API in batches
        fresh_metadata = self._fetch_in_batches(uncached_ids)

        # Step 5: Cache fresh results
        if use_cache and fresh_metadata:
            cached_count = self.metadata_cache.set_many(fresh_metadata)
            log.info("Cached fresh metadata", count=cached_count)

        # Step 6: Combine cached + fresh
        all_metadata = list(cached_metadata.values()) + fresh_metadata

        log.info(
            "Video metadata fetch complete",
            total_returned=len(all_metadata),
            from_cache=len(cached_metadata),
            from_api=len(fresh_metadata),
            quota_used=total_quota_cost
        )

        return all_metadata

    def _fetch_in_batches(self, video_ids: List[str]) -> List[Dict]:
        """
        Fetch video metadata from YouTube API in batches.

        Args:
            video_ids: List of video IDs to fetch

        Returns:
            List of video metadata dictionaries
        """
        all_results = []
        total_batches = (len(video_ids) + self.MAX_VIDEOS_PER_REQUEST - 1) // self.MAX_VIDEOS_PER_REQUEST

        log.info(
            "Fetching from YouTube API",
            video_count=len(video_ids),
            batch_size=self.MAX_VIDEOS_PER_REQUEST,
            total_batches=total_batches
        )

        for batch_num, i in enumerate(range(0, len(video_ids), self.MAX_VIDEOS_PER_REQUEST), 1):
            batch = video_ids[i:i + self.MAX_VIDEOS_PER_REQUEST]

            log.debug(
                "Processing batch",
                batch_num=batch_num,
                total_batches=total_batches,
                batch_size=len(batch)
            )

            try:
                # Make API request
                response = self.youtube.videos().list(
                    part='snippet,statistics,contentDetails',
                    id=','.join(batch),
                    maxResults=self.MAX_VIDEOS_PER_REQUEST
                ).execute()

                # Extract items
                items = response.get('items', [])
                all_results.extend(items)

                # Consume quota
                self.quota_manager.consume(self.QUOTA_COST_VIDEO_LIST)

                log.debug(
                    "Batch completed",
                    batch_num=batch_num,
                    results_count=len(items),
                    quota_used=self.QUOTA_COST_VIDEO_LIST
                )

            except HttpError as e:
                self._handle_http_error(e)

            except Exception as e:
                log.error(
                    "Unexpected error during API call",
                    batch_num=batch_num,
                    error=str(e),
                    exc_info=True
                )
                raise EnrichmentError(f"YouTube API request failed: {str(e)}")

        log.info(
            "API fetch complete",
            total_results=len(all_results),
            total_batches=total_batches
        )

        return all_results

    def _handle_http_error(self, error: HttpError):
        """
        Handle HTTP errors from YouTube API.

        Args:
            error: HttpError from googleapiclient

        Raises:
            QuotaExceededError: If quota exhausted
            RateLimitError: If rate limited
            YouTubeAPIError: For other API errors
        """
        status_code = error.resp.status
        error_content = error.content.decode('utf-8') if error.content else str(error)

        log.error(
            "YouTube API HTTP error",
            status_code=status_code,
            error_content=error_content[:500]  # Limit log size
        )

        # Handle specific error types
        if status_code == 403:
            if 'quotaExceeded' in error_content:
                log.error("YouTube API quota exceeded")
                raise QuotaExceededError()

            elif 'rateLimitExceeded' in error_content:
                retry_after = error.resp.get('Retry-After')
                log.warning("YouTube API rate limit exceeded", retry_after=retry_after)
                raise RateLimitError(retry_after=int(retry_after) if retry_after else None)

            else:
                raise YouTubeAPIError(
                    reason="Forbidden - check API key permissions",
                    status_code=403
                )

        elif status_code == 400:
            raise YouTubeAPIError(
                reason="Bad request - invalid video IDs or parameters",
                status_code=400
            )

        elif status_code >= 500:
            raise YouTubeAPIError(
                reason=f"YouTube API server error ({status_code})",
                status_code=status_code
            )

        else:
            raise YouTubeAPIError(
                reason=f"YouTube API error: {error_content[:200]}",
                status_code=status_code
            )

    def get_video_metadata_safe(
        self,
        video_ids: List[str],
        max_quota: Optional[int] = None
    ) -> List[Dict]:
        """
        Safely fetch video metadata with quota limits.

        If quota is insufficient, fetches as many as possible.

        Args:
            video_ids: List of video IDs
            max_quota: Maximum quota to use (None = no limit)

        Returns:
            List of video metadata (may be partial if quota limited)

        Example:
            >>> client = YouTubeAPIClient(api_key="...")
            >>> # Fetch up to 100 quota units worth
            >>> metadata = client.get_video_metadata_safe(video_ids, max_quota=100)
        """
        # Check available quota
        available_quota = self.quota_manager.get_remaining()

        if max_quota is not None:
            available_quota = min(available_quota, max_quota)

        # Calculate how many batches we can afford
        affordable_batches = available_quota // self.QUOTA_COST_VIDEO_LIST
        affordable_videos = affordable_batches * self.MAX_VIDEOS_PER_REQUEST

        if affordable_videos < len(video_ids):
            log.warning(
                "Insufficient quota for all videos",
                requested=len(video_ids),
                affordable=affordable_videos,
                available_quota=available_quota
            )

            # Prioritize first N videos
            video_ids = video_ids[:affordable_videos]

        return self.get_video_metadata(video_ids)

    def get_quota_stats(self) -> Dict:
        """
        Get current quota usage statistics.

        Returns:
            Dictionary with quota stats

        Example:
            >>> client = YouTubeAPIClient(api_key="...")
            >>> stats = client.get_quota_stats()
            >>> print(f"Quota used: {stats['percent_used']}%")
        """
        return self.quota_manager.get_stats()

    def get_cache_stats(self) -> Dict:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache stats

        Example:
            >>> client = YouTubeAPIClient(api_key="...")
            >>> stats = client.get_cache_stats()
            >>> print(f"Cached videos: {stats['total_cached']}")
        """
        return self.metadata_cache.get_stats()

    def clear_cache(self) -> int:
        """
        Clear all cached metadata.

        Returns:
            Number of items deleted

        Example:
            >>> client = YouTubeAPIClient(api_key="...")
            >>> deleted = client.clear_cache()
        """
        return self.metadata_cache.clear_all()
