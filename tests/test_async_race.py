"""
Async Race Condition Flaky Tests - Medium Difficulty

These tests fail due to race conditions in concurrent async operations
and improper synchronization.

Root Cause: Missing locks, non-atomic operations, and uncontrolled concurrency.
Expected Fix: Add proper synchronization (asyncio.Lock), use atomic operations,
              or redesign to avoid shared mutable state.

Failure Rate: ~35% depending on async scheduling
"""

import pytest
import asyncio
import sys
import os
import random

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from api_client import AsyncAPIClient, APIStatus


@pytest.fixture
def async_client():
    """Create a fresh async client for each test."""
    return AsyncAPIClient()


class TestAsyncUserFetch:
    """Tests for async user fetching."""
    
    @pytest.mark.asyncio
    async def test_single_async_fetch(self, async_client):
        """Test single async fetch works."""
        response = await async_client.fetch_user(1)
        
        # 8% timeout chance
        assert response.status in [APIStatus.SUCCESS, APIStatus.TIMEOUT], \
            f"Unexpected status: {response.status}"
    
    @pytest.mark.asyncio
    async def test_all_fetches_succeed(self, async_client):
        """
        FLAKY: Each request has 8% timeout chance.
        10 requests = ~56% chance all succeed.
        """
        responses = []
        for i in range(10):
            response = await async_client.fetch_user(i)
            responses.append(response)
        
        success_count = sum(1 for r in responses if r.status == APIStatus.SUCCESS)
        assert success_count == 10, \
            f"Expected all 10 to succeed, got {success_count}"


class TestConcurrentFetch:
    """Tests for concurrent async operations."""
    
    @pytest.mark.asyncio
    async def test_concurrent_fetch_same_user(self, async_client):
        """
        FLAKY: Race condition when multiple coroutines fetch same user.
        Cache check and cache write are not atomic.
        """
        # Fetch same user concurrently
        tasks = [async_client.fetch_user(1) for _ in range(10)]
        responses = await asyncio.gather(*tasks)
        
        # All should succeed and return same data
        success_responses = [r for r in responses if r.status == APIStatus.SUCCESS]
        
        if len(success_responses) >= 2:
            # Check all successful responses have same data
            first_data = success_responses[0].data
            for r in success_responses[1:]:
                assert r.data == first_data, "Data mismatch in concurrent fetch"
    
    @pytest.mark.asyncio
    async def test_concurrent_different_users(self, async_client):
        """
        FLAKY: Request count is not thread-safe.
        """
        # Fetch different users concurrently
        responses = await async_client.fetch_users_concurrent([1, 2, 3, 4, 5])
        
        # Due to non-atomic increment, count might be wrong
        # Each fetch increments _request_count += 1 which is not atomic
        expected_count = len(responses)
        actual_count = async_client.request_count
        
        assert actual_count == expected_count, \
            f"Request count mismatch: expected {expected_count}, got {actual_count}"
    
    @pytest.mark.asyncio
    async def test_cache_consistency(self, async_client):
        """
        FLAKY: Cache updates have race conditions.
        """
        # Clear cache first
        async_client.clear_cache()
        
        # Concurrent fetches for different users
        user_ids = list(range(20))
        responses = await async_client.fetch_users_concurrent(user_ids)
        
        # Check cache has all successful fetches
        successful_ids = [
            r.data["id"] for r in responses 
            if r.status == APIStatus.SUCCESS and r.data
        ]
        
        cached_ids = list(async_client._cache.keys())
        
        # Due to race conditions, some might be missing from cache
        for uid in successful_ids:
            assert uid in cached_ids, \
                f"User {uid} missing from cache despite successful fetch"


class TestRetryLogic:
    """Tests for retry behavior."""
    
    @pytest.mark.asyncio
    async def test_retry_eventually_succeeds(self, async_client):
        """
        FLAKY: Retry uses fixed delay, not exponential backoff.
        With 8% failure rate and 3 retries, ~99% should eventually succeed.
        But the implementation might not handle all edge cases.
        """
        response = await async_client.fetch_with_retry(1, max_retries=3)
        
        assert response.status == APIStatus.SUCCESS, \
            f"Expected success after retries, got {response.status}"
    
    @pytest.mark.asyncio
    async def test_multiple_retries_concurrent(self, async_client):
        """
        FLAKY: Multiple concurrent retry operations can interfere.
        """
        tasks = [
            async_client.fetch_with_retry(i, max_retries=3)
            for i in range(5)
        ]
        responses = await asyncio.gather(*tasks)
        
        # All should eventually succeed
        success_count = sum(1 for r in responses if r.status == APIStatus.SUCCESS)
        assert success_count == 5, \
            f"Expected 5 successes after retries, got {success_count}"


class TestAsyncResourceManagement:
    """Tests for async resource management."""
    
    @pytest.mark.asyncio
    async def test_rapid_cache_clear(self, async_client):
        """
        FLAKY: Race between fetch and cache clear.
        """
        async def fetch_and_check():
            response = await async_client.fetch_user(1)
            return response.status == APIStatus.SUCCESS
        
        async def clear_cache():
            await asyncio.sleep(random.uniform(0.01, 0.05))
            async_client.clear_cache()
        
        # Run both concurrently
        fetch_task = asyncio.create_task(fetch_and_check())
        clear_task = asyncio.create_task(clear_cache())
        
        await asyncio.gather(fetch_task, clear_task)
        
        # Result depends on which task completes first
        result = fetch_task.result()
        assert result, "Fetch should have succeeded"
    
    @pytest.mark.asyncio
    async def test_request_count_under_load(self, async_client):
        """
        FLAKY: High concurrency exposes race condition in counter.
        """
        # Create many concurrent requests
        num_requests = 50
        tasks = [async_client.fetch_user(i % 10) for i in range(num_requests)]
        
        responses = await asyncio.gather(*tasks)
        
        # Count how many actually made requests (some might use cache)
        # The counter should equal responses that didn't timeout
        successful = sum(1 for r in responses if r.status != APIStatus.TIMEOUT)
        
        # Due to race condition in _request_count += 1, this might be wrong
        # The non-atomic increment can lose counts under high concurrency
        assert async_client.request_count >= successful * 0.9, \
            f"Request count {async_client.request_count} is too low for {successful} responses"


class TestAsyncTimingIssues:
    """Tests with async-specific timing problems."""
    
    @pytest.mark.asyncio
    async def test_operation_ordering(self, async_client):
        """
        FLAKY: Async operations don't guarantee order.
        """
        results = []
        
        async def fetch_and_record(user_id):
            response = await async_client.fetch_user(user_id)
            results.append(user_id)
            return response
        
        # Start fetches in order 1, 2, 3
        tasks = [fetch_and_record(i) for i in [1, 2, 3]]
        await asyncio.gather(*tasks)
        
        # This incorrectly assumes results will be in order
        assert results == [1, 2, 3], \
            f"Expected ordered results, got {results}"
    
    @pytest.mark.asyncio
    async def test_timeout_behavior(self, async_client):
        """
        FLAKY: Async timeout behavior depends on scheduling.
        """
        async def slow_operation():
            await asyncio.sleep(random.uniform(0.05, 0.09))
            return "completed"
        
        try:
            result = await asyncio.wait_for(slow_operation(), timeout=0.1)
            assert result == "completed"
        except asyncio.TimeoutError:
            pytest.fail("Operation timed out unexpectedly")
    
    @pytest.mark.asyncio
    async def test_gather_exception_handling(self, async_client):
        """
        FLAKY: One failing task might affect others in gather.
        """
        async def maybe_fail(should_fail: bool):
            await asyncio.sleep(0.01)
            if should_fail:
                raise ValueError("Intentional failure")
            return "success"
        
        tasks = [
            maybe_fail(False),
            maybe_fail(random.random() < 0.3),  # 30% chance to fail
            maybe_fail(False),
        ]
        
        try:
            results = await asyncio.gather(*tasks)
            assert len(results) == 3
        except ValueError:
            pytest.fail("One task failure should not fail the entire gather")
