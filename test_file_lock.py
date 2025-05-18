#!/usr/bin/env python3
"""
Unit tests for the FileLock class.

This file tests the FileLock class identified for refactoring in REFACTORING.md.
"""

import unittest
from unittest.mock import patch, MagicMock, mock_open
import sys
import tempfile
import shutil
import os
import errno
from pathlib import Path

# Add the parent directory to sys.path to allow imports from the autosubnuclei package
sys.path.insert(0, str(Path(__file__).parent))

# Mock fcntl module which is not available on Windows
sys.modules['fcntl'] = MagicMock()

# Import the FileLock class
from autosubnuclei.core.checkpoint_manager import FileLock


class TestFileLock(unittest.TestCase):
    """Test cases for the FileLock class."""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        # Create temporary directory for testing
        self.temp_dir = tempfile.mkdtemp(prefix="filelock_test_")
        self.lock_file = Path(self.temp_dir) / "test.lock"
        
        # Create a FileLock instance
        self.file_lock = FileLock(self.lock_file)
        
    def tearDown(self):
        """Tear down test fixtures after each test method."""
        # Clean up temporary directory
        shutil.rmtree(self.temp_dir)
        
    @patch('os.name', 'posix')  # Simulate Unix environment
    def test_acquire_unix(self):
        """Test acquire method on Unix platform."""
        # Mock open function
        with patch('builtins.open', mock_open()) as mock_file, \
             patch('fcntl.flock') as mock_flock:
            # Call acquire method
            result = self.file_lock.acquire()
            
            # Verify file was opened
            mock_file.assert_called_once_with(str(self.lock_file), 'w')
            
            # Verify flock was called with exclusive lock
            mock_flock.assert_called_once()
            import fcntl
            self.assertEqual(mock_flock.call_args[0][1], fcntl.LOCK_EX | fcntl.LOCK_NB)
            
            # Verify acquisition was successful
            self.assertTrue(result)
            
    @patch('os.name', 'posix')  # Simulate Unix environment
    def test_release_unix(self):
        """Test release method on Unix platform."""
        # Set up mock file handle
        mock_handle = MagicMock()
        self.file_lock.lock_handle = mock_handle
        
        # Mock fcntl.flock
        with patch('fcntl.flock') as mock_flock:
            # Call release method
            result = self.file_lock.release()
            
            # Verify flock was called with unlock
            mock_flock.assert_called_once()
            import fcntl
            self.assertEqual(mock_flock.call_args[0][1], fcntl.LOCK_UN)
            
            # Verify file was closed
            mock_handle.close.assert_called_once()
            
            # Verify release was successful
            self.assertTrue(result)
            
    @patch('os.name', 'nt')  # Simulate Windows environment
    def test_acquire_windows(self):
        """Test acquire method on Windows platform."""
        # Mock open function
        with patch('builtins.open', mock_open()) as mock_file:
            # Call acquire method
            result = self.file_lock.acquire()
            
            # Verify file was opened
            mock_file.assert_called_once_with(str(self.lock_file), 'w')
            
            # Verify acquisition was successful
            self.assertTrue(result)
            
    @patch('os.name', 'nt')  # Simulate Windows environment
    def test_release_windows(self):
        """Test release method on Windows platform."""
        # Set up mock file handle
        mock_handle = MagicMock()
        self.file_lock.lock_handle = mock_handle
        
        # Mock Path.exists and Path.unlink
        with patch.object(Path, 'exists', return_value=True), \
             patch.object(Path, 'unlink') as mock_unlink:
            # Call release method
            result = self.file_lock.release()
            
            # Verify file was closed
            mock_handle.close.assert_called_once()
            
            # Verify lock file was unlinked
            mock_unlink.assert_called_once()
            
            # Verify release was successful
            self.assertTrue(result)
            
    def test_acquire_directory_creation(self):
        """Test acquire method creates parent directory if it doesn't exist."""
        # Use a subdirectory that doesn't exist
        lock_file = Path(self.temp_dir) / "subdir" / "test.lock"
        file_lock = FileLock(lock_file)
        
        # Mock open to avoid actual file operations
        with patch('builtins.open', mock_open()) as mock_file, \
             patch('os.name', 'nt'):  # Use Windows to avoid fcntl
            # Call acquire method
            result = file_lock.acquire()
            
            # Verify parent directory exists
            self.assertTrue(lock_file.parent.exists())
            
            # Verify acquisition was successful
            self.assertTrue(result)
            
    @patch('os.name', 'posix')  # Simulate Unix environment
    def test_acquire_timeout(self):
        """Test acquire method times out when lock cannot be acquired."""
        # Mock open function
        with patch('builtins.open', mock_open()) as mock_file, \
             patch('fcntl.flock', side_effect=IOError(errno.EAGAIN, "Resource temporarily unavailable")), \
             patch('time.time', side_effect=[0, 11]):  # Simulate timeout after 11 seconds
            # Call acquire method with shorter timeout
            result = self.file_lock.acquire(timeout=10)
            
            # Verify acquisition failed due to timeout
            self.assertFalse(result)
            
    @patch('os.name', 'posix')  # Simulate Unix environment
    def test_acquire_error(self):
        """Test acquire method handles other errors gracefully."""
        # Mock open function to raise a different error
        with patch('builtins.open', side_effect=IOError(errno.EACCES, "Permission denied")):
            # Call acquire method
            result = self.file_lock.acquire()
            
            # Verify acquisition failed
            self.assertFalse(result)
            
    def test_release_no_handle(self):
        """Test release method when no lock handle exists."""
        # Ensure no lock handle
        self.file_lock.lock_handle = None
        
        # Call release method
        result = self.file_lock.release()
        
        # Verify release reported failure
        self.assertFalse(result)
        
    @patch('os.name', 'posix')  # Simulate Unix environment
    def test_release_error(self):
        """Test release method handles errors gracefully."""
        # Set up mock file handle that raises exception on close
        mock_handle = MagicMock()
        mock_handle.close.side_effect = Exception("Test exception")
        self.file_lock.lock_handle = mock_handle
        
        # Call release method
        result = self.file_lock.release()
        
        # Verify release reported failure
        self.assertFalse(result)
        
    def test_context_manager(self):
        """Test FileLock as a context manager."""
        # Mock acquire and release methods
        with patch.object(self.file_lock, 'acquire', return_value=True) as mock_acquire, \
             patch.object(self.file_lock, 'release') as mock_release:
            # Use as context manager
            with self.file_lock:
                pass
                
            # Verify acquire and release were called
            mock_acquire.assert_called_once()
            mock_release.assert_called_once()


if __name__ == '__main__':
    unittest.main() 