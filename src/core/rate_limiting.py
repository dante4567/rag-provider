"""
Simple Rate Limiting Middleware

Provides basic rate limiting without external dependencies using:
- Token bucket algorithm
- In-memory storage (Redis can be added later)
- Per-IP and per-API-key limits
"""

import time
from collections import defaultdict
from typing import Dict, Tuple
import threading


class TokenBucket:
    """
    Token bucket rate limiter

    Implements the token bucket algorithm for smooth rate limiting
    """

    def __init__(self, capacity: int, refill_rate: float):
        """
        Initialize token bucket

        Args:
            capacity: Maximum number of tokens (burst size)
            refill_rate: Tokens added per second
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = capacity
        self.last_refill = time.time()
        self.lock = threading.Lock()

    def consume(self, tokens: int = 1) -> bool:
        """
        Try to consume tokens

        Args:
            tokens: Number of tokens to consume

        Returns:
            True if tokens were consumed, False if rate limit exceeded
        """
        with self.lock:
            now = time.time()

            # Refill tokens based on time passed
            time_passed = now - self.last_refill
            new_tokens = time_passed * self.refill_rate
            self.tokens = min(self.capacity, self.tokens + new_tokens)
            self.last_refill = now

            # Try to consume
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True

            return False

    def get_wait_time(self, tokens: int = 1) -> float:
        """
        Get time to wait until tokens are available

        Args:
            tokens: Number of tokens needed

        Returns:
            Seconds to wait
        """
        with self.lock:
            if self.tokens >= tokens:
                return 0.0

            tokens_needed = tokens - self.tokens
            return tokens_needed / self.refill_rate


class RateLimiter:
    """
    Rate limiter with multiple limits and automatic cleanup
    """

    def __init__(
        self,
        requests_per_minute: int = 60,
        requests_per_hour: int = 1000,
        burst_size: int = 10
    ):
        """
        Initialize rate limiter

        Args:
            requests_per_minute: Max requests per minute
            requests_per_hour: Max requests per hour
            burst_size: Max burst size
        """
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.burst_size = burst_size

        # Storage for buckets per identifier (IP or API key)
        self.minute_buckets: Dict[str, TokenBucket] = {}
        self.hour_buckets: Dict[str, TokenBucket] = {}

        # Cleanup thread
        self.last_cleanup = time.time()
        self.cleanup_interval = 300  # 5 minutes

    def check_rate_limit(self, identifier: str) -> Tuple[bool, str, float]:
        """
        Check if request is allowed under rate limits

        Args:
            identifier: Unique identifier (IP address or API key)

        Returns:
            Tuple of (allowed, limit_type, retry_after)
        """
        # Cleanup old buckets periodically
        self._maybe_cleanup()

        # Create buckets if they don't exist
        if identifier not in self.minute_buckets:
            self.minute_buckets[identifier] = TokenBucket(
                capacity=self.burst_size,
                refill_rate=self.requests_per_minute / 60.0
            )

        if identifier not in self.hour_buckets:
            self.hour_buckets[identifier] = TokenBucket(
                capacity=self.requests_per_hour,
                refill_rate=self.requests_per_hour / 3600.0
            )

        # Check minute limit
        minute_bucket = self.minute_buckets[identifier]
        if not minute_bucket.consume():
            retry_after = minute_bucket.get_wait_time()
            return False, "per_minute", retry_after

        # Check hour limit
        hour_bucket = self.hour_buckets[identifier]
        if not hour_bucket.consume():
            # Return token to minute bucket since hour limit failed
            minute_bucket.tokens = min(minute_bucket.capacity, minute_bucket.tokens + 1)
            retry_after = hour_bucket.get_wait_time()
            return False, "per_hour", retry_after

        return True, "", 0.0

    def _maybe_cleanup(self):
        """Clean up old buckets to prevent memory leak"""
        now = time.time()
        if now - self.last_cleanup < self.cleanup_interval:
            return

        self.last_cleanup = now

        # Remove buckets that haven't been used recently (>1 hour)
        cutoff = now - 3600

        self.minute_buckets = {
            k: v for k, v in self.minute_buckets.items()
            if v.last_refill > cutoff
        }

        self.hour_buckets = {
            k: v for k, v in self.hour_buckets.items()
            if v.last_refill > cutoff
        }

    def get_stats(self) -> Dict:
        """Get rate limiter statistics"""
        return {
            "active_minute_buckets": len(self.minute_buckets),
            "active_hour_buckets": len(self.hour_buckets),
            "requests_per_minute_limit": self.requests_per_minute,
            "requests_per_hour_limit": self.requests_per_hour,
            "burst_size": self.burst_size
        }


# Global rate limiters
_default_limiter: RateLimiter = None
_api_key_limiter: RateLimiter = None


def get_default_limiter() -> RateLimiter:
    """Get default rate limiter (for unauthenticated requests)"""
    global _default_limiter
    if _default_limiter is None:
        _default_limiter = RateLimiter(
            requests_per_minute=30,  # Conservative for public
            requests_per_hour=500,
            burst_size=5
        )
    return _default_limiter


def get_api_key_limiter() -> RateLimiter:
    """Get rate limiter for authenticated requests (more generous)"""
    global _api_key_limiter
    if _api_key_limiter is None:
        _api_key_limiter = RateLimiter(
            requests_per_minute=60,  # More generous for authenticated
            requests_per_hour=2000,
            burst_size=10
        )
    return _api_key_limiter
