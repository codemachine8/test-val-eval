# Flaky Test Evaluation Repository

A purpose-built repository for evaluating AI-powered flaky test detection and fix generation systems like [UnfoldCI](https://unfoldci.com).

## Overview

This repository contains intentionally flaky tests across four categories, each with known root causes and expected fix patterns. It's designed to evaluate:

1. **Detection accuracy** - Can the system identify which tests are flaky?
2. **Root cause analysis** - Can the system identify WHY tests are flaky?
3. **Fix quality** - Are the generated fixes correct and comprehensive?

## Test Categories

| Category | File | Failure Rate | Fix Difficulty | Expected AI Success |
|----------|------|--------------|----------------|---------------------|
| Order-Dependent | `test_order_dependent.py` | ~30% | Easy | 79% |
| Timing Issues | `test_timing_issues.py` | ~25% | Easy-Medium | 70% |
| Async Race Conditions | `test_async_race.py` | ~35% | Medium | 58% |
| Resource Cleanup | `test_resource_cleanup.py` | ~20% | Medium | 60% |

## Flaky Patterns & Expected Fixes

### 1. Order-Dependent Tests (Easy)

**Root Cause:** Tests share state through the `Database` singleton without proper isolation.

**Symptoms:**
- Tests pass when run individually but fail in certain orders
- Database contains unexpected data from previous tests
- Transaction counts don't match expectations

**Expected Fix:**
```python
@pytest.fixture(autouse=True)
def cleanup_database():
    from database import Database
    db = Database()
    db.clear_all()
    db.disconnect()
    yield
    db.clear_all()
    db.disconnect()
```

### 2. Timing Issues (Easy-Medium)

**Root Cause:** Hardcoded timeouts and timing assertions that don't account for system load variation.

**Symptoms:**
- Tests fail intermittently with "timeout" or "too slow" errors
- Assertions on response time fail during CI load spikes
- Fixed sleep durations cause race conditions

**Expected Fixes:**
- Replace fixed sleeps with polling/retry patterns
- Increase timeout margins (e.g., 100ms → 500ms)
- Use `wait_for_condition` with appropriate timeouts

### 3. Async Race Conditions (Medium)

**Root Cause:** Missing locks, non-atomic operations, and uncontrolled concurrency in async code.

**Symptoms:**
- Request count doesn't match expected value
- Cache inconsistencies in concurrent access
- Results arrive in unexpected order

**Expected Fixes:**
```python
# Add asyncio.Lock for shared state
self._cache_lock = asyncio.Lock()

async def fetch_user(self, user_id: int):
    async with self._cache_lock:
        if user_id in self._cache:
            return self._cache[user_id]
```

### 4. Resource Cleanup (Medium)

**Root Cause:** Missing teardown, class-level state pollution, improper file/lock handling.

**Symptoms:**
- Open file count accumulates across tests
- Temp files not cleaned up
- Lock files left behind

**Expected Fixes:**
- Add proper fixtures with cleanup
- Use context managers
- Clear class-level state in teardown

## Running Tests

### Local Execution

```bash
# Install dependencies
pip install -r requirements.txt

# Run all tests (some will fail - that's expected!)
pytest tests/ -v

# Run with random order to expose flakiness
pytest tests/ -p pytest_randomly -v

# Run multiple times to catch flaky failures
for i in {1..10}; do pytest tests/ -p pytest_randomly --randomly-seed=$i; done

# Run with JUnit output for UnfoldCI
pytest tests/ --junitxml=test-results/junit-results.xml
```

### CI/CD

The repository includes a GitHub Actions workflow that:
1. Runs tests 10 times in parallel with different random seeds
2. Generates JUnit XML reports
3. Uploads results to UnfoldCI for analysis

## Evaluating Fix Quality

When evaluating AI-generated fixes, check:

1. **Correctness** - Does the fix actually prevent the flaky behavior?
2. **Completeness** - Does it fix all instances of the pattern?
3. **Minimal Impact** - Does it avoid changing unrelated code?
4. **Best Practices** - Does it follow Python/pytest conventions?

### Scoring Rubric

| Score | Criteria |
|-------|----------|
| 5 | Perfect fix, follows best practices |
| 4 | Correct fix, minor style issues |
| 3 | Partially correct, fixes main issue |
| 2 | Incorrect but reasonable attempt |
| 1 | Wrong approach entirely |

## Project Structure

```
flaky-test-eval/
├── src/
│   ├── __init__.py
│   ├── database.py       # Simulated database with singleton issues
│   ├── api_client.py     # API client with timing/async issues
│   └── file_handler.py   # File operations with cleanup issues
├── tests/
│   ├── __init__.py
│   ├── conftest.py       # Pytest fixtures (intentionally minimal)
│   ├── test_order_dependent.py    # Order-dependent tests
│   ├── test_timing_issues.py      # Timing-related tests
│   ├── test_async_race.py         # Async race condition tests
│   └── test_resource_cleanup.py   # Resource cleanup tests
├── .github/
│   └── workflows/
│       └── unfoldci-test.yml      # CI workflow
├── pytest.ini
├── requirements.txt
└── README.md
```

## Contributing

This repository is designed for evaluation purposes. If you find additional flaky patterns that would be valuable to test, please open an issue or PR.

## License

MIT License - Feel free to use this for your own testing tool evaluations.
