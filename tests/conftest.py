"""
Pytest configuration and fixtures.

Note: This conftest intentionally does NOT include global cleanup fixtures
to demonstrate how missing cleanup causes flaky tests.
"""

import pytest
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line(
        "markers", "flaky: mark test as known to be flaky"
    )


# Note: We intentionally do NOT provide a fixture that cleans up
# the Database singleton or FileProcessor class-level state.
# This makes the flaky behavior more pronounced.

# If you want to see how proper cleanup would fix the tests,
# uncomment the fixtures below:

# @pytest.fixture(autouse=True)
# def cleanup_database():
#     """Clean up database state before each test."""
#     from database import Database
#     db = Database()
#     db.clear_all()
#     db.disconnect()
#     yield
#     db.clear_all()
#     db.disconnect()

# @pytest.fixture(autouse=True)
# def cleanup_file_processor():
#     """Clean up FileProcessor class-level state."""
#     from file_handler import FileProcessor
#     FileProcessor.cleanup_tracking()
#     FileProcessor._temp_files = []
#     yield
#     FileProcessor.cleanup_tracking()
#     FileProcessor._temp_files = []
