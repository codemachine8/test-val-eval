"""
Timing-Related Flaky Tests - Easy to Medium Difficulty

These tests fail due to hardcoded timeouts and timing assumptions
that don't account for system load variation.

Root Cause: Fixed sleep durations and tight timing assertions.
Expected Fix: Use polling/retry patterns instead of fixed sleeps,
              or increase timeouts with appropriate margins.

Failure Rate: ~25% depending on system load
"""

import pytest
import sys
import os
import time
import random

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from api_client import APIClient, APIStatus, wait_for_condition


class TestAPILatency:
    """Tests with hardcoded timing expectations."""
    
    def test_api_response_under_100ms(self):
        """
        FLAKY: Assumes API always responds under 100ms.
        The simulated API can have latency spikes up to 300ms.
        """
        client = APIClient()
        
        response = client.fetch_user(1)
        
        # This fails during latency spikes (10% chance)
        assert response.latency_ms < 100, \
            f"Expected response under 100ms, got {response.latency_ms:.1f}ms"
    
    def test_batch_fetch_timing(self):
        """
        FLAKY: Batch timing is even more variable.
        """
        client = APIClient()
        
        start = time.time()
        responses = client.fetch_users_batch([1, 2, 3, 4, 5])
        elapsed = (time.time() - start) * 1000
        
        # Very tight timing - each request can take 10-100ms
        # 5 requests sequentially = 50-500ms minimum
        assert elapsed < 300, f"Batch fetch too slow: {elapsed:.1f}ms"
    
    def test_api_success_rate(self):
        """
        FLAKY: API has 5% random failure rate.
        Running 10 requests, probability of all succeeding is ~60%.
        """
        client = APIClient()
        
        successes = 0
        for i in range(10):
            response = client.fetch_user(i)
            if response.status == APIStatus.SUCCESS:
                successes += 1
        
        # Expects 100% success but API has 5% failure rate
        assert successes == 10, f"Expected all successes, got {successes}/10"


class TestWaitConditions:
    """Tests using wait_for_condition with tight timeouts."""
    
    def test_wait_for_fast_condition(self):
        """
        Test waiting for a condition that should be fast.
        """
        counter = {"value": 0}
        
        def increment_slowly():
            time.sleep(0.05)  # Simulated work
            counter["value"] += 1
        
        # Start incrementing in background... but we're not using threads
        # So this is actually testing synchronous behavior
        result = wait_for_condition(
            lambda: counter["value"] > 0,
            timeout_seconds=0.5,
            poll_interval=0.1
        )
        
        # This always fails because nothing is incrementing the counter
        assert result, "Condition should have been met"
    
    def test_wait_with_variable_delay(self):
        """
        FLAKY: Delay is random, timeout is fixed.
        """
        ready_time = time.time() + random.uniform(0.1, 0.6)
        
        result = wait_for_condition(
            lambda: time.time() >= ready_time,
            timeout_seconds=0.5,
            poll_interval=0.1
        )
        
        # Fails ~20% of the time when random delay > 0.5s
        assert result, "Should have become ready in time"


class TestRateLimiting:
    """Tests for rate limiting behavior."""
    
    def test_rate_limit_not_exceeded(self):
        """
        FLAKY: Sends exactly at rate limit boundary.
        """
        client = APIClient()
        
        # Send 10 requests (at the limit)
        responses = []
        for i in range(10):
            responses.append(client.fetch_user(i))
        
        # Check none were rate limited
        rate_limited = sum(1 for r in responses if r.status == APIStatus.RATE_LIMITED)
        assert rate_limited == 0, f"{rate_limited} requests were rate limited"
    
    def test_rate_limit_recovery(self):
        """
        FLAKY: Timing of rate limit window recovery.
        """
        client = APIClient()
        
        # Exceed rate limit
        for i in range(15):
            client.fetch_user(i)
        
        # Wait for window to reset (1 second)
        time.sleep(1.0)  # Bug: Should be slightly more than window
        
        # Try again - should work
        response = client.fetch_user(100)
        assert response.status != APIStatus.RATE_LIMITED, \
            "Rate limit should have reset"


class TestTimeSensitiveOperations:
    """Tests with time-sensitive logic."""
    
    def test_operation_completes_quickly(self):
        """
        FLAKY: Asserts operation time without accounting for system load.
        """
        start = time.time()
        
        # Simulate some work with variable duration
        work_time = random.uniform(0.05, 0.15)
        time.sleep(work_time)
        
        elapsed = time.time() - start
        
        # Tight assertion - fails when work_time > 0.1
        assert elapsed < 0.1, f"Operation took {elapsed:.3f}s, expected < 0.1s"
    
    def test_multiple_operations_timing(self):
        """
        FLAKY: Cumulative timing variations.
        """
        total_time = 0
        
        for i in range(5):
            start = time.time()
            # Each operation takes 10-30ms
            time.sleep(random.uniform(0.01, 0.03))
            total_time += time.time() - start
        
        # Expects average case but can get worst case
        # Best case: 5 * 10ms = 50ms
        # Worst case: 5 * 30ms = 150ms
        assert total_time < 0.1, f"Operations took {total_time:.3f}s total"
    
def test_timeout_handling(self):
    """
    Test that operations timeout correctly.
    FLAKY: Sleep duration affects whether timeout triggers.
    """
    operation_time = random.uniform(0.08, 0.12)
    timeout = 0.15  # Increased timeout to ensure it covers the max operation time
    
    start = time.time()
    time.sleep(operation_time)
    elapsed = time.time() - start
    
    # Check if we "timed out"
    timed_out = elapsed >= timeout
    
    # This test doesn't make sense as written - 
    # it's checking random behavior deterministically
    assert not timed_out, f"Operation timed out after {elapsed:.3f}s"


class TestRequestCounting:
    """Tests that count requests with timing dependencies."""
    
    def test_request_count_after_operations(self):
        """
        Test that request count is accurate.
        FLAKY: If rate limited, count might not match expected.
        """
        client = APIClient()
        
        # Make some requests
        for i in range(5):
            client.fetch_user(i)
        
        # Request count should be 5
        # But rate limiting or errors might affect this
        assert client.request_count == 5, \
            f"Expected 5 requests, counted {client.request_count}"
    
    def test_request_count_resets(self):
        """
        FLAKY: Request count doesn't actually reset between tests.
        """
        client = APIClient()
        
        initial_count = client.request_count
        client.fetch_user(1)
        
        # Assumes initial count is 0, but singleton state persists
        assert client.request_count == 1, \
            f"Expected 1 request, got {client.request_count}"
