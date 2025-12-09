"""
Resource Cleanup Flaky Tests - Medium Difficulty

These tests fail due to improper resource cleanup, leaving
files, locks, and state that affects subsequent tests.

Root Cause: Missing teardown, improper context manager usage,
            and class-level state pollution.
Expected Fix: Add proper fixtures with cleanup, use context managers,
              reset class-level state.

Failure Rate: ~20% depending on test order
"""

import pytest
import sys
import os
import tempfile
import time
import threading

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from file_handler import (
    FileProcessor, 
    TempFileManager, 
    FileLock, 
    BackgroundWriter
)


class TestFileProcessor:
    """Tests for FileProcessor with cleanup issues."""
    
    def test_open_and_read_file(self, tmp_path):
        """Test basic file reading."""
        # Create a test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello, World!")
        
        processor = FileProcessor(str(test_file))
        assert processor.open("r")
        
        content = processor.read()
        assert content == "Hello, World!"
        
        # Bug: Not closing the file
        # processor.close()  # This is commented out intentionally
    
    def test_open_file_count(self, tmp_path):
        """
        FLAKY: Depends on previous tests closing files properly.
        """
        # Check how many files are tracked as open
        initial_count = FileProcessor.get_open_file_count()
        
        # Should be 0 if previous tests cleaned up
        assert initial_count == 0, \
            f"Expected 0 open files, found {initial_count} - previous test didn't clean up"
        
        # Open a new file
        test_file = tmp_path / "count_test.txt"
        test_file.write_text("test")
        
        processor = FileProcessor(str(test_file))
        processor.open("r")
        
        assert FileProcessor.get_open_file_count() == 1
        
        processor.close()
        # Bug: close() doesn't remove from _open_files
    
    def test_write_file(self, tmp_path):
        """Test file writing."""
        test_file = tmp_path / "write_test.txt"
        
        processor = FileProcessor(str(test_file))
        processor.open("w")
        processor.write("New content")
        processor.close()
        
        # Verify content
        assert test_file.read_text() == "New content"


class TestTempFileManager:
    """Tests for TempFileManager with cleanup issues."""
    
    def test_create_temp_file(self):
        """Test creating temporary files."""
        manager = TempFileManager(prefix="test_")
        
        filepath = manager.create_temp_file("data.txt", "test content")
        
        assert os.path.exists(filepath)
        with open(filepath) as f:
            assert f.read() == "test content"
        
        # Bug: Not calling cleanup
        # manager.cleanup()
    
    def test_class_level_temp_files_empty(self):
        """
        FLAKY: FileProcessor._temp_files is class-level and not cleaned.
        """
        # This should be empty if no temp files created in this session
        # But TempFileManager adds to FileProcessor._temp_files
        assert len(FileProcessor._temp_files) == 0, \
            f"Expected no temp files tracked, found {len(FileProcessor._temp_files)}"
    
    def test_multiple_temp_files(self):
        """Test creating multiple temp files."""
        manager = TempFileManager(prefix="multi_")
        
        files = []
        for i in range(3):
            filepath = manager.create_temp_file(f"file_{i}.txt", f"content {i}")
            files.append(filepath)
        
        for filepath in files:
            assert os.path.exists(filepath)
        
        # Cleanup
        manager.cleanup()
        
        # Bug: cleanup doesn't remove temp directory
        assert manager.get_temp_dir() is None or not os.path.exists(manager.get_temp_dir()), \
            "Temp directory should be removed after cleanup"


class TestFileLock:
    """Tests for file-based locking."""
    
    def test_acquire_and_release(self, tmp_path):
        """Test basic lock acquire and release."""
        lock_file = tmp_path / "test.lock"
        
        lock = FileLock(str(lock_file))
        
        assert lock.acquire(timeout=1.0)
        assert os.path.exists(lock_file)
        
        assert lock.release()
        assert not os.path.exists(lock_file)
    
    def test_lock_prevents_double_acquisition(self, tmp_path):
        """Test that lock prevents double acquisition."""
        lock_file = tmp_path / "double.lock"
        
        lock1 = FileLock(str(lock_file))
        lock2 = FileLock(str(lock_file))
        
        assert lock1.acquire(timeout=1.0)
        
        # Second lock should fail quickly
        assert not lock2.acquire(timeout=0.5)
        
        lock1.release()
        
        # Now second lock should succeed
        assert lock2.acquire(timeout=1.0)
        lock2.release()
    
    def test_stale_lock_file(self, tmp_path):
        """
        FLAKY: If a previous test left a lock file, this test fails.
        """
        lock_file = tmp_path / "stale.lock"
        
        # This assumes no lock file exists
        assert not os.path.exists(lock_file), \
            "Lock file should not exist before test"
        
        lock = FileLock(str(lock_file))
        # Bug: Don't release in teardown


class TestBackgroundWriter:
    """Tests for background file writer."""
    
    def test_background_write(self, tmp_path):
        """Test background writing."""
        output_file = tmp_path / "background.txt"
        
        writer = BackgroundWriter(str(output_file))
        writer.start()
        
        # Queue some writes
        writer.queue_write("Line 1")
        writer.queue_write("Line 2")
        
        # Wait for writes to happen
        time.sleep(0.3)
        
        # Stop the writer
        writer.stop()
        
        # Bug: stop() doesn't wait for thread or flush buffer
        # Need to wait a bit more
        time.sleep(0.2)
        
        # Check content
        if output_file.exists():
            content = output_file.read_text()
            assert "Line 1" in content
            assert "Line 2" in content
        else:
            pytest.fail("Output file was not created")
    
    def test_background_write_flush(self, tmp_path):
        """
        FLAKY: Race condition between flush and background thread.
        """
        output_file = tmp_path / "flush.txt"
        
        writer = BackgroundWriter(str(output_file))
        writer.start()
        
        writer.queue_write("Immediate 1")
        writer.queue_write("Immediate 2")
        
        # Flush immediately (race condition with background thread)
        writer.flush()
        
        writer.stop()
        
        # Check content immediately (might not be written yet)
        content = output_file.read_text() if output_file.exists() else ""
        
        # This can fail due to race condition
        assert "Immediate 1" in content, \
            f"Expected 'Immediate 1' in content, got: {content}"
    
    def test_writer_without_stop(self, tmp_path):
        """
        FLAKY: Not stopping writer leaves daemon thread running.
        """
        output_file = tmp_path / "nostop.txt"
        
        writer = BackgroundWriter(str(output_file))
        writer.start()
        writer.queue_write("Data")
        
        # Bug: Not calling writer.stop()
        # Daemon thread continues running
        
        # Give time for write
        time.sleep(0.2)
        
        assert output_file.exists(), "File should exist after write"


class TestCleanupFixtures:
    """Tests that demonstrate proper vs improper cleanup patterns."""
    
    def test_with_manual_cleanup(self, tmp_path):
        """Test with manual cleanup (can fail if exception before cleanup)."""
        test_file = tmp_path / "manual.txt"
        
        processor = FileProcessor(str(test_file))
        test_file.write_text("test")
        
        try:
            processor.open("r")
            content = processor.read()
            assert content == "test"
        finally:
            # Manual cleanup - can be forgotten
            processor.close()
    
    def test_depends_on_cleanup(self):
        """
        FLAKY: This test depends on previous tests having cleaned up.
        """
        # Check that class-level state is clean
        open_count = FileProcessor.get_open_file_count()
        temp_count = len(FileProcessor._temp_files)
        
        assert open_count == 0, \
            f"Found {open_count} tracked open files from previous tests"
        assert temp_count == 0, \
            f"Found {temp_count} tracked temp files from previous tests"
    
    def test_context_manager_cleanup(self, tmp_path):
        """
        Test using context manager for cleanup.
        Note: FileLock has context manager, but FileProcessor doesn't.
        """
        lock_file = tmp_path / "context.lock"
        
        with FileLock(str(lock_file)) as lock:
            assert os.path.exists(lock_file)
        
        # Lock should be released
        assert not os.path.exists(lock_file)


class TestCrossTestPollution:
    """Tests that demonstrate cross-test state pollution."""
    
    def test_first_modifies_state(self):
        """First test that modifies class-level state."""
        # Simulate file operations that add to class tracking
        FileProcessor._open_files["fake_file_1"] = None
        FileProcessor._open_files["fake_file_2"] = None
        
        assert FileProcessor.get_open_file_count() >= 2
    
    def test_second_expects_clean_state(self):
        """
        FLAKY: Depends on test_first_modifies_state not running before this.
        """
        # Expects clean state
        assert FileProcessor.get_open_file_count() == 0, \
            "Expected no open files - previous test polluted state"
    
    def test_third_cleans_up(self):
        """Test that attempts to clean up."""
        FileProcessor.cleanup_tracking()
        assert FileProcessor.get_open_file_count() == 0
