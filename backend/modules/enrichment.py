from typing import List, Dict, Any, Optional
from backend.utils.logging_config import get_logger
from backend.exceptions import EnrichmentError, QuotaExceededError
from backend.services.youtube_api import YouTubeAPIClient
from backend.config import get_config

log = get_logger(__name__)
config = get_config()


def enrich_video_metadata(
    video_ids: List[str],
    api_key: Optional[str] = None,
    use_cache: bool = True
) -> List[Dict[str, Any]]:
    """
    Enriches a list of video IDs with metadata from the YouTube API.

    This function uses the YouTube Data API v3 to fetch comprehensive metadata
    including titles, descriptions, statistics, and content details.

    Features:
    - Automatic caching (7-day TTL)
    - Quota management
    - Batch optimization (50 videos per request)
    - Graceful error handling

    Args:
        video_ids: A list of YouTube video IDs.
        api_key: Google API key (uses config if None)
        use_cache: Whether to use cached data (default: True)

    Returns:
        A list of dictionaries, where each dictionary contains metadata for a video.
        Each video dict contains:
        - id: Video ID
        - snippet: Title, description, channel info, tags
        - statistics: Views, likes, comments
        - contentDetails: Duration, definition, etc.

    Raises:
        EnrichmentError: If metadata enrichment fails
        QuotaExceededError: If YouTube API quota is exhausted

    Example:
        >>> metadata = enrich_video_metadata(["dQw4w9WgXcQ", "jNQXAC9IVRw"])
        >>> print(metadata[0]['snippet']['title'])
    """
    if not video_ids:
        log.warning("enrich_video_metadata called with empty video_ids list")
        return []

    log.info(
        "Starting video metadata enrichment",
        video_count=len(video_ids),
        use_cache=use_cache
    )

    try:
        # Get API key from config if not provided
        if api_key is None:
            api_key = config.google_api_key
            if not api_key:
                log.error("No Google API key available")
                raise EnrichmentError(
                    "No Google API key configured. Please set GOOGLE_API_KEY environment variable."
                )

        # Initialize YouTube API client
        log.debug("Initializing YouTube API client")
        youtube_client = YouTubeAPIClient(api_key=api_key)

        # Log quota status before enrichment
        quota_stats = youtube_client.get_quota_stats()
        log.info(
            "Pre-enrichment quota status",
            remaining=quota_stats['remaining'],
            percent_used=quota_stats['percent_used'],
            status=quota_stats['status']
        )

        # Check if we have enough quota
        prediction = youtube_client.quota_manager.predict_batch_cost(len(video_ids))
        if not prediction['can_afford']:
            log.warning(
                "Insufficient quota for all videos",
                requested=len(video_ids),
                affordable=prediction['videos_affordable'],
                required_quota=prediction['total_cost'],
                available_quota=prediction['remaining_quota']
            )

            # Option 1: Fetch what we can afford
            affordable_count = prediction['videos_affordable']
            if affordable_count > 0:
                log.info(f"Fetching first {affordable_count} videos within quota limits")
                video_ids = video_ids[:affordable_count]
            else:
                # No quota available
                raise QuotaExceededError(
                    details={
                        "required": prediction['total_cost'],
                        "remaining": prediction['remaining_quota'],
                        "reset_time": quota_stats['reset_time']
                    }
                )

        # Fetch metadata using YouTube API client
        enriched_data = youtube_client.get_video_metadata(
            video_ids=video_ids,
            use_cache=use_cache
        )

        # Log quota status after enrichment
        quota_stats_after = youtube_client.get_quota_stats()
        log.info(
            "Post-enrichment quota status",
            remaining=quota_stats_after['remaining'],
            percent_used=quota_stats_after['percent_used'],
            quota_consumed=quota_stats['remaining'] - quota_stats_after['remaining']
        )

        # Log cache statistics
        cache_stats = youtube_client.get_cache_stats()
        log.info(
            "Cache statistics",
            total_cached=cache_stats['total_cached'],
            cache_size_mb=cache_stats['estimated_memory_mb']
        )

        log.info(
            "Metadata enrichment complete",
            enriched_count=len(enriched_data),
            requested_count=len(video_ids)
        )

        return enriched_data

    except QuotaExceededError:
        # Re-raise quota errors (already logged in YouTube client)
        raise

    except EnrichmentError:
        # Re-raise enrichment errors (already logged)
        raise

    except Exception as e:
        log.error(
            "Unexpected error during metadata enrichment",
            error=str(e),
            video_count=len(video_ids),
            exc_info=True
        )
        raise EnrichmentError(f"Failed to enrich video metadata: {str(e)}")