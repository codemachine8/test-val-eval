"""
File handling module with resource cleanup issues.
This module has patterns that cause resource leaks and cleanup-related flakiness.
"""

import os
import tempfile
import time
import threading
from typing import Optional, List, Dict
from pathlib import Path


class FileProcessor:
    """File processor with resource management issues."""
    
    # Class-level tracking of open files - causes cross-test pollution
    _open_files: Dict[str, 'FileProcessor'] = {}
    _temp_files: List[str] = []
    
    def __init__(self, filepath: str):
        self.filepath = filepath
        self._handle: Optional[object] = None
        self._is_open = False
        self._lock_file: Optional[str] = None
    
    def open(self, mode: str = "r") -> bool:
        """Open the file."""
        try:
            self._handle = open(self.filepath, mode)
            self._is_open = True
            FileProcessor._open_files[self.filepath] = self
            return True
        except IOError:
            return False
    
    def close(self) -> bool:
        """Close the file - but doesn't clean up class-level tracking."""
        if self._handle:
            self._handle.close()
            self._is_open = False
            # Bug: Doesn't remove from _open_files tracking
            return True
        return False
    
    def read(self) -> Optional[str]:
        """Read file contents."""
        if not self._is_open or not self._handle:
            raise IOError("File not open")
        return self._handle.read()
    
    def write(self, content: str) -> int:
        """Write to file."""
        if not self._is_open or not self._handle:
            raise IOError("File not open")
        return self._handle.write(content)
    
    @classmethod
    def get_open_file_count(cls) -> int:
        """Get count of tracked open files."""
        return len(cls._open_files)
    
    @classmethod
    def cleanup_tracking(cls) -> None:
        """Clean up the class-level tracking."""
        cls._open_files = {}


class TempFileManager:
    """Temporary file manager with cleanup issues."""
    
    def __init__(self, prefix: str = "test_"):
        self.prefix = prefix
        self._temp_dir: Optional[str] = None
        self._created_files: List[str] = []
        self._is_initialized = False
    
    def initialize(self) -> str:
        """Create a temp directory."""
        self._temp_dir = tempfile.mkdtemp(prefix=self.prefix)
        self._is_initialized = True
        return self._temp_dir
    
    def create_temp_file(self, name: str, content: str = "") -> str:
        """Create a temporary file."""
        if not self._is_initialized:
            self.initialize()
        
        filepath = os.path.join(self._temp_dir, name)
        with open(filepath, "w") as f:
            f.write(content)
        
        self._created_files.append(filepath)
        FileProcessor._temp_files.append(filepath)  # Bug: adds to class-level list
        return filepath
    
    def cleanup(self) -> None:
        """
        Clean up temp files.
        Bug: Doesn't handle files that are still open.
        Bug: Doesn't clean up the temp directory itself.
        """
        for filepath in self._created_files:
            try:
                os.remove(filepath)
            except (OSError, PermissionError):
                pass  # Silently ignore - bad practice
        self._created_files = []
    
    def get_temp_dir(self) -> Optional[str]:
        """Get the temp directory path."""
        return self._temp_dir


class FileLock:
    """File-based locking mechanism with race conditions."""
    
    def __init__(self, lock_path: str):
        self.lock_path = lock_path
        self._acquired = False
    
    def acquire(self, timeout: float = 5.0) -> bool:
        """
        Acquire the lock.
        Bug: Race condition between checking and creating lock file.
        """
        start = time.time()
        while time.time() - start < timeout:
            if not os.path.exists(self.lock_path):
                # Race condition: another process could create file here
                try:
                    with open(self.lock_path, "x") as f:  # Create exclusively
                        f.write(str(os.getpid()))
                    self._acquired = True
                    return True
                except FileExistsError:
                    pass
            time.sleep(0.01)  # Fixed sleep - not ideal
        return False
    
    def release(self) -> bool:
        """Release the lock."""
        if self._acquired and os.path.exists(self.lock_path):
            try:
                os.remove(self.lock_path)
                self._acquired = False
                return True
            except OSError:
                return False
        return False
    
    def __enter__(self):
        self.acquire()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
        return False


class BackgroundWriter:
    """Background file writer with threading issues."""
    
    def __init__(self, filepath: str):
        self.filepath = filepath
        self._buffer: List[str] = []
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._write_interval = 0.1
    
    def start(self) -> None:
        """Start the background writer."""
        self._running = True
        self._thread = threading.Thread(target=self._write_loop, daemon=True)
        self._thread.start()
    
    def stop(self) -> None:
        """
        Stop the background writer.
        Bug: Doesn't wait for thread to finish or flush buffer.
        """
        self._running = False
    
    def _write_loop(self) -> None:
        """Background write loop."""
        while self._running:
            if self._buffer:
                # Bug: Not thread-safe access to buffer
                to_write = self._buffer.copy()
                self._buffer = []
                
                with open(self.filepath, "a") as f:
                    for line in to_write:
                        f.write(line + "\n")
            
            time.sleep(self._write_interval)
    
    def queue_write(self, content: str) -> None:
        """Queue content for writing."""
        self._buffer.append(content)
    
    def flush(self) -> None:
        """
        Flush the buffer immediately.
        Bug: Race condition with background thread.
        """
        if self._buffer:
            with open(self.filepath, "a") as f:
                for line in self._buffer:
                    f.write(line + "\n")
            self._buffer = []
