"""
Simulated API client with timing issues.
This module has patterns that cause timing-related test flakiness.
"""

import asyncio
import random
import time
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum


class APIStatus(Enum):
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"


@dataclass
class APIResponse:
    status: APIStatus
    data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    latency_ms: float = 0.0


class APIClient:
    """Simulated API client with realistic latency and failure patterns."""
    
    def __init__(self, base_url: str = "https://api.example.com"):
        self.base_url = base_url
        self._request_count = 0
        self._last_request_time: Optional[float] = None
        self._rate_limit_window = 1.0  # seconds
        self._rate_limit_max = 10  # requests per window
        self._window_requests = 0
        self._window_start: Optional[float] = None
    
    def _simulate_latency(self) -> float:
        """Simulate network latency (10-100ms with occasional spikes)."""
        base_latency = random.uniform(0.01, 0.05)
        # 10% chance of latency spike
        if random.random() < 0.10:
            base_latency += random.uniform(0.1, 0.3)
        return base_latency
    
    def _check_rate_limit(self) -> bool:
        """Check if we're rate limited."""
        now = time.time()
        if self._window_start is None or now - self._window_start > self._rate_limit_window:
            self._window_start = now
            self._window_requests = 0
        
        self._window_requests += 1
        return self._window_requests > self._rate_limit_max
    
    def fetch_user(self, user_id: int) -> APIResponse:
        """Fetch user data from API."""
        start = time.time()
        
        # Check rate limiting
        if self._check_rate_limit():
            return APIResponse(
                status=APIStatus.RATE_LIMITED,
                error_message="Rate limit exceeded",
                latency_ms=(time.time() - start) * 1000
            )
        
        # Simulate network latency
        latency = self._simulate_latency()
        time.sleep(latency)
        
        self._request_count += 1
        self._last_request_time = time.time()
        
        # 5% chance of random failure
        if random.random() < 0.05:
            return APIResponse(
                status=APIStatus.ERROR,
                error_message="Internal server error",
                latency_ms=(time.time() - start) * 1000
            )
        
        return APIResponse(
            status=APIStatus.SUCCESS,
            data={"id": user_id, "name": f"User {user_id}", "email": f"user{user_id}@example.com"},
            latency_ms=(time.time() - start) * 1000
        )
    
    def fetch_users_batch(self, user_ids: List[int]) -> List[APIResponse]:
        """Fetch multiple users."""
        return [self.fetch_user(uid) for uid in user_ids]
    
    @property
    def request_count(self) -> int:
        return self._request_count


class AsyncAPIClient:
    """Async version of the API client with race condition potential."""
    
    def __init__(self, base_url: str = "https://api.example.com"):
        self.base_url = base_url
        self._request_count = 0
        self._cache: Dict[int, dict] = {}
        self._cache_lock = None  # Bug: Lock not initialized
    
    async def _simulate_latency(self) -> float:
        """Simulate async network latency."""
        latency = random.uniform(0.01, 0.08)
        # Higher chance of variation in async context
        if random.random() < 0.15:
            latency += random.uniform(0.05, 0.2)
        await asyncio.sleep(latency)
        return latency
    
    async def fetch_user(self, user_id: int) -> APIResponse:
        """Fetch user data asynchronously."""
        start = time.time()
        
        # Check cache first (race condition here without proper locking)
        if user_id in self._cache:
            return APIResponse(
                status=APIStatus.SUCCESS,
                data=self._cache[user_id],
                latency_ms=(time.time() - start) * 1000
            )
        
        latency = await self._simulate_latency()
        
        # Bug: non-atomic increment
        self._request_count += 1
        
        # 8% chance of timeout in async context
        if random.random() < 0.08:
            return APIResponse(
                status=APIStatus.TIMEOUT,
                error_message="Request timed out",
                latency_ms=(time.time() - start) * 1000
            )
        
        data = {"id": user_id, "name": f"User {user_id}", "email": f"user{user_id}@example.com"}
        
        # Cache the result (race condition without lock)
        self._cache[user_id] = data
        
        return APIResponse(
            status=APIStatus.SUCCESS,
            data=data,
            latency_ms=(time.time() - start) * 1000
        )
    
    async def fetch_users_concurrent(self, user_ids: List[int]) -> List[APIResponse]:
        """Fetch multiple users concurrently."""
        tasks = [self.fetch_user(uid) for uid in user_ids]
        return await asyncio.gather(*tasks)
    
    async def fetch_with_retry(self, user_id: int, max_retries: int = 3) -> APIResponse:
        """Fetch with retry logic."""
        last_response = None
        for attempt in range(max_retries):
            response = await self.fetch_user(user_id)
            if response.status == APIStatus.SUCCESS:
                return response
            last_response = response
            # Bug: Fixed delay instead of exponential backoff
            await asyncio.sleep(0.1)
        return last_response
    
    def clear_cache(self) -> None:
        """Clear the cache."""
        self._cache = {}
    
    @property
    def request_count(self) -> int:
        return self._request_count


def wait_for_condition(condition_fn, timeout_seconds: float = 5.0, poll_interval: float = 0.1) -> bool:
    """
    Wait for a condition to become true.
    
    Bug: Uses fixed poll interval instead of adaptive waiting.
    This causes flaky tests when the condition takes variable time.
    """
    start = time.time()
    while time.time() - start < timeout_seconds:
        if condition_fn():
            return True
        time.sleep(poll_interval)
    return False
