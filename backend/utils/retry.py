"""
Retry utilities with exponential backoff for resilient external API calls.

This module provides decorators and functions for implementing retry logic
with exponential backoff, jitter, and circuit breaker patterns.
"""

import time
import random
from typing import Callable, TypeVar, Optional, Type, Tuple
from functools import wraps
from backend.utils.logging_config import get_logger
from backend.exceptions import ExternalServiceError, TimeoutError as CustomTimeoutError

log = get_logger(__name__)

T = TypeVar('T')


def exponential_backoff(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retry_on: Optional[Tuple[Type[Exception], ...]] = None
) -> Callable:
    """
    Decorator to retry a function with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Base for exponential calculation
        jitter: Whether to add random jitter to delay
        retry_on: Tuple of exception types to retry on (None = all exceptions)

    Returns:
        Decorated function with retry logic

    Example:
        >>> @exponential_backoff(max_retries=3, initial_delay=1.0)
        ... def fetch_data():
        ...     return api.get('/data')
    """
    if retry_on is None:
        retry_on = (Exception,)

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            attempt = 0
            last_exception = None

            while attempt <= max_retries:
                try:
                    if attempt > 0:
                        log.info(
                            "Retrying function",
                            function=func.__name__,
                            attempt=attempt,
                            max_retries=max_retries
                        )

                    result = func(*args, **kwargs)

                    if attempt > 0:
                        log.info(
                            "Function succeeded after retry",
                            function=func.__name__,
                            attempt=attempt
                        )

                    return result

                except retry_on as e:
                    last_exception = e
                    attempt += 1

                    if attempt > max_retries:
                        log.error(
                            "Function failed after all retries",
                            function=func.__name__,
                            attempts=attempt,
                            error=str(e)
                        )
                        raise

                    # Calculate delay with exponential backoff
                    delay = min(
                        initial_delay * (exponential_base ** (attempt - 1)),
                        max_delay
                    )

                    # Add jitter if enabled
                    if jitter:
                        delay = delay * (0.5 + random.random())

                    log.warning(
                        "Function failed, will retry",
                        function=func.__name__,
                        attempt=attempt,
                        max_retries=max_retries,
                        error_type=type(e).__name__,
                        error=str(e),
                        retry_delay_seconds=round(delay, 2)
                    )

                    time.sleep(delay)

            # This should never be reached, but just in case
            if last_exception:
                raise last_exception
            raise RuntimeError("Retry logic failed unexpectedly")

        return wrapper
    return decorator


def retry_with_timeout(
    max_retries: int = 3,
    timeout_seconds: float = 30.0,
    initial_delay: float = 1.0,
    retry_on: Optional[Tuple[Type[Exception], ...]] = None
) -> Callable:
    """
    Decorator combining retry logic with timeout.

    Args:
        max_retries: Maximum number of retry attempts
        timeout_seconds: Timeout for each attempt in seconds
        initial_delay: Initial retry delay in seconds
        retry_on: Tuple of exception types to retry on

    Returns:
        Decorated function with retry and timeout logic

    Example:
        >>> @retry_with_timeout(max_retries=3, timeout_seconds=30)
        ... def slow_api_call():
        ...     return api.get('/slow-endpoint')
    """
    import signal
    from contextlib import contextmanager

    @contextmanager
    def timeout_context(seconds: float):
        """Context manager for timeout."""
        def timeout_handler(signum, frame):
            raise CustomTimeoutError(service="function", timeout_seconds=int(seconds))

        # Set the signal handler and alarm
        old_handler = signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(int(seconds))
        try:
            yield
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        # First apply exponential backoff
        retrying_func = exponential_backoff(
            max_retries=max_retries,
            initial_delay=initial_delay,
            retry_on=retry_on
        )(func)

        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            with timeout_context(timeout_seconds):
                return retrying_func(*args, **kwargs)

        return wrapper
    return decorator


class CircuitBreaker:
    """
    Circuit breaker pattern to prevent cascading failures.

    The circuit breaker has three states:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Circuit is open, requests fail immediately
    - HALF_OPEN: Testing if service has recovered

    Example:
        >>> breaker = CircuitBreaker(failure_threshold=5, timeout=60)
        >>> @breaker.protected
        ... def call_external_api():
        ...     return api.get('/data')
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        timeout: float = 60.0,
        expected_exception: Type[Exception] = Exception
    ):
        """
        Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit
            timeout: Seconds to wait before attempting recovery (HALF_OPEN)
            expected_exception: Exception type to track for failures
        """
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.expected_exception = expected_exception

        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"

        log.info(
            "Circuit breaker initialized",
            failure_threshold=failure_threshold,
            timeout=timeout
        )

    def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """
        Execute function with circuit breaker protection.

        Args:
            func: Function to execute
            *args: Positional arguments for function
            **kwargs: Keyword arguments for function

        Returns:
            Result of function call

        Raises:
            ExternalServiceError: If circuit is OPEN
        """
        if self.state == "OPEN":
            # Check if timeout has elapsed
            if time.time() - self.last_failure_time >= self.timeout:
                log.info("Circuit breaker entering HALF_OPEN state")
                self.state = "HALF_OPEN"
            else:
                log.warning("Circuit breaker is OPEN, rejecting request")
                raise ExternalServiceError(
                    service=func.__name__,
                    reason="Circuit breaker is OPEN"
                )

        try:
            result = func(*args, **kwargs)

            # Success - reset if in HALF_OPEN or maintain CLOSED
            if self.state == "HALF_OPEN":
                log.info("Circuit breaker recovered, entering CLOSED state")
                self.state = "CLOSED"
                self.failure_count = 0

            return result

        except self.expected_exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()

            log.warning(
                "Circuit breaker recorded failure",
                failure_count=self.failure_count,
                threshold=self.failure_threshold,
                state=self.state,
                error=str(e)
            )

            if self.failure_count >= self.failure_threshold:
                log.error("Circuit breaker threshold reached, entering OPEN state")
                self.state = "OPEN"

            raise

    def protected(self, func: Callable[..., T]) -> Callable[..., T]:
        """
        Decorator to protect a function with circuit breaker.

        Args:
            func: Function to protect

        Returns:
            Protected function

        Example:
            >>> breaker = CircuitBreaker(failure_threshold=5)
            >>> @breaker.protected
            ... def risky_operation():
            ...     pass
        """
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            return self.call(func, *args, **kwargs)
        return wrapper

    def reset(self) -> None:
        """Manually reset the circuit breaker to CLOSED state."""
        log.info("Circuit breaker manually reset")
        self.state = "CLOSED"
        self.failure_count = 0
        self.last_failure_time = None


# Pre-configured retry decorators for common use cases
youtube_api_retry = exponential_backoff(
    max_retries=3,
    initial_delay=2.0,
    max_delay=30.0,
    retry_on=(ExternalServiceError, CustomTimeoutError, ConnectionError)
)

network_retry = exponential_backoff(
    max_retries=4,
    initial_delay=1.0,
    max_delay=16.0,
    retry_on=(ConnectionError, OSError)
)
