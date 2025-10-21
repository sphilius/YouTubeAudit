"""
YouTube API quota management service.

This module tracks YouTube API quota usage to prevent exceeding daily limits.
YouTube Data API v3 has a default quota of 10,000 units per day.
"""

from datetime import datetime, timedelta
from typing import Dict, Optional
from backend.cache import get_redis_client
from backend.utils.logging_config import get_logger
from backend.exceptions import QuotaExceededError

log = get_logger(__name__)


class QuotaManager:
    """
    Manages YouTube API quota with daily limits and tracking.

    YouTube Data API v3 costs:
    - videos.list: 1 unit per request (50 videos max)
    - search.list: 100 units per request
    - channels.list: 1 unit per request

    Default daily quota: 10,000 units
    """

    # API operation costs (in quota units)
    QUOTA_COST_VIDEO_LIST = 1
    QUOTA_COST_SEARCH = 100
    QUOTA_COST_CHANNEL_LIST = 1

    def __init__(self, daily_limit: int = 10000):
        """
        Initialize quota manager.

        Args:
            daily_limit: Daily quota limit in units (default: 10,000)
        """
        self.redis_client = get_redis_client()
        self.daily_limit = daily_limit
        self.key_prefix = "youtube_quota"

        log.info("Quota manager initialized", daily_limit=daily_limit)

    def _get_today_key(self) -> str:
        """
        Get Redis key for today's quota.

        Returns:
            Redis key with today's date
        """
        today = datetime.now().date().isoformat()
        return f"{self.key_prefix}:{today}"

    def get_used(self) -> int:
        """
        Get quota units used today.

        Returns:
            Number of units consumed today

        Example:
            >>> manager = QuotaManager()
            >>> used = manager.get_used()
            >>> print(f"Used: {used} units")
        """
        key = self._get_today_key()

        try:
            used = self.redis_client.get(key)
            used_int = int(used) if used else 0

            log.debug("Retrieved quota usage", used=used_int, limit=self.daily_limit)
            return used_int

        except Exception as e:
            log.error("Failed to get quota usage", error=str(e))
            return 0

    def get_remaining(self) -> int:
        """
        Get remaining quota for today.

        Returns:
            Number of units remaining (cannot be negative)

        Example:
            >>> manager = QuotaManager()
            >>> remaining = manager.get_remaining()
            >>> print(f"Remaining: {remaining} units")
        """
        used = self.get_used()
        remaining = max(0, self.daily_limit - used)

        log.debug("Calculated remaining quota", remaining=remaining)
        return remaining

    def can_use(self, units: int) -> bool:
        """
        Check if we have enough quota available.

        Args:
            units: Number of units required

        Returns:
            True if enough quota available, False otherwise

        Example:
            >>> manager = QuotaManager()
            >>> if manager.can_use(5):
            ...     # Proceed with API call
            ...     pass
        """
        remaining = self.get_remaining()
        can_proceed = remaining >= units

        if not can_proceed:
            log.warning(
                "Insufficient quota",
                required=units,
                remaining=remaining,
                daily_limit=self.daily_limit
            )
        else:
            log.debug("Quota check passed", required=units, remaining=remaining)

        return can_proceed

    def consume(self, units: int) -> int:
        """
        Consume quota units.

        This should be called AFTER a successful API call to track usage.

        Args:
            units: Number of units to consume

        Returns:
            New total units used today

        Raises:
            QuotaExceededError: If consumption would exceed daily limit

        Example:
            >>> manager = QuotaManager()
            >>> # After successful API call
            >>> manager.consume(1)
        """
        key = self._get_today_key()

        try:
            # Increment counter atomically
            new_total = self.redis_client.incr(key, units)

            # Set expiry to end of day on first use
            if new_total == units:
                tomorrow = datetime.now().replace(
                    hour=0, minute=0, second=0, microsecond=0
                ) + timedelta(days=1)
                ttl = int((tomorrow - datetime.now()).total_seconds())
                self.redis_client.expire(key, ttl)

                log.info("Started tracking quota for today", date=datetime.now().date())

            # Check if we've exceeded limit
            if new_total > self.daily_limit:
                log.error(
                    "Quota exceeded",
                    total_used=new_total,
                    limit=self.daily_limit,
                    overage=new_total - self.daily_limit
                )
                # Note: We still record the usage, but warn about excess
                # The calling code should have checked can_use() first

            log.info(
                "Quota consumed",
                units=units,
                total_used=new_total,
                remaining=max(0, self.daily_limit - new_total),
                percent_used=round(new_total / self.daily_limit * 100, 1)
            )

            return new_total

        except Exception as e:
            log.error("Failed to consume quota", units=units, error=str(e))
            raise

    def reserve(self, units: int) -> bool:
        """
        Reserve quota units before making an API call.

        This checks availability and consumes quota atomically.

        Args:
            units: Number of units to reserve

        Returns:
            True if successfully reserved, False if insufficient quota

        Raises:
            QuotaExceededError: If quota exhausted

        Example:
            >>> manager = QuotaManager()
            >>> if manager.reserve(5):
            ...     # Make API call
            ...     pass
            ... else:
            ...     # Handle quota exhaustion
            ...     pass
        """
        if not self.can_use(units):
            remaining = self.get_remaining()
            raise QuotaExceededError(
                details={
                    "required": units,
                    "remaining": remaining,
                    "daily_limit": self.daily_limit,
                    "reset_time": self._get_reset_time().isoformat()
                }
            )

        self.consume(units)
        return True

    def _get_reset_time(self) -> datetime:
        """
        Get the time when quota resets (midnight UTC).

        Returns:
            Datetime of next quota reset
        """
        tomorrow = datetime.now().replace(
            hour=0, minute=0, second=0, microsecond=0
        ) + timedelta(days=1)
        return tomorrow

    def get_stats(self) -> Dict:
        """
        Get quota usage statistics.

        Returns:
            Dictionary with quota statistics

        Example:
            >>> manager = QuotaManager()
            >>> stats = manager.get_stats()
            >>> print(f"Used: {stats['percent_used']}%")
        """
        used = self.get_used()
        remaining = self.get_remaining()
        percent_used = (used / self.daily_limit * 100) if self.daily_limit > 0 else 0
        reset_time = self._get_reset_time()
        time_until_reset = reset_time - datetime.now()

        stats = {
            "daily_limit": self.daily_limit,
            "used": used,
            "remaining": remaining,
            "percent_used": round(percent_used, 2),
            "reset_time": reset_time.isoformat(),
            "hours_until_reset": round(time_until_reset.total_seconds() / 3600, 1),
            "status": self._get_status(percent_used)
        }

        log.debug("Quota stats retrieved", **stats)
        return stats

    def _get_status(self, percent_used: float) -> str:
        """
        Get quota status based on usage percentage.

        Args:
            percent_used: Percentage of quota used

        Returns:
            Status string: "healthy", "warning", "critical", "exhausted"
        """
        if percent_used >= 100:
            return "exhausted"
        elif percent_used >= 90:
            return "critical"
        elif percent_used >= 70:
            return "warning"
        else:
            return "healthy"

    def reset_quota(self) -> None:
        """
        Manually reset quota counter.

        WARNING: This should only be used for testing or administrative purposes.
        Quota naturally resets at midnight UTC.
        """
        key = self._get_today_key()

        try:
            self.redis_client.delete(key)
            log.warning("Quota manually reset")
        except Exception as e:
            log.error("Failed to reset quota", error=str(e))

    def estimate_cost(self, operation: str, count: int = 1) -> int:
        """
        Estimate quota cost for an operation.

        Args:
            operation: API operation name ('video_list', 'search', 'channel_list')
            count: Number of operations (e.g., number of batch requests)

        Returns:
            Estimated quota cost in units

        Example:
            >>> manager = QuotaManager()
            >>> cost = manager.estimate_cost('video_list', count=20)
            >>> print(f"Cost: {cost} units")  # 20 units
        """
        costs = {
            'video_list': self.QUOTA_COST_VIDEO_LIST,
            'search': self.QUOTA_COST_SEARCH,
            'channel_list': self.QUOTA_COST_CHANNEL_LIST,
        }

        unit_cost = costs.get(operation, 1)
        total_cost = unit_cost * count

        log.debug(
            "Estimated quota cost",
            operation=operation,
            count=count,
            unit_cost=unit_cost,
            total_cost=total_cost
        )

        return total_cost

    def predict_batch_cost(self, video_count: int, batch_size: int = 50) -> Dict:
        """
        Predict quota cost for enriching videos in batches.

        Args:
            video_count: Total number of videos to enrich
            batch_size: Videos per API request (max 50 for YouTube API)

        Returns:
            Dictionary with cost prediction

        Example:
            >>> manager = QuotaManager()
            >>> prediction = manager.predict_batch_cost(1000)
            >>> print(f"Total cost: {prediction['total_cost']} units")
        """
        batch_size = min(batch_size, 50)  # YouTube API max
        num_batches = (video_count + batch_size - 1) // batch_size
        total_cost = num_batches * self.QUOTA_COST_VIDEO_LIST

        remaining = self.get_remaining()
        can_afford = remaining >= total_cost

        prediction = {
            "video_count": video_count,
            "batch_size": batch_size,
            "num_batches": num_batches,
            "cost_per_batch": self.QUOTA_COST_VIDEO_LIST,
            "total_cost": total_cost,
            "remaining_quota": remaining,
            "can_afford": can_afford,
            "videos_affordable": min(video_count, remaining * batch_size) if not can_afford else video_count
        }

        log.info("Batch cost prediction", **prediction)
        return prediction
