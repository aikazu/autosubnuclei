#!/usr/bin/env python3
"""
Unit tests for the SecurityScanner class.

These tests focus on the methods marked for refactoring in the REFACTORING.md document:
1. _run_httpx
2. _run_nuclei_in_batches 
"""

import os
import sys
import unittest
import tempfile
from pathlib import Path
import asyncio
import json
import logging
from unittest.mock import patch, MagicMock, AsyncMock, mock_open

# Mock fcntl module which is not available on Windows
sys.modules['fcntl'] = MagicMock()

# Add the parent directory to sys.path to allow imports from the autosubnuclei package
sys.path.insert(0, str(Path(__file__).parent))

from autosubnuclei.core.scanner import SecurityScanner

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('test_security_scanner')

class TestSecurityScanner(unittest.TestCase):
    """Test cases for the SecurityScanner class."""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        # Create temporary directories for testing
        self.temp_dir = tempfile.mkdtemp(prefix="scanner_test_")
        self.output_dir = Path(self.temp_dir) / "output"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.templates_dir = Path(self.temp_dir) / "templates"
        self.templates_dir.mkdir(parents=True, exist_ok=True)
        
        # Create a sample templates file
        sample_template = self.templates_dir / "sample.yaml"
        with open(sample_template, 'w') as f:
            f.write("id: test-template\ninfo:\n  name: Test Template")
        
        # Initialize mocks
        self.mock_tool_manager = MagicMock()
        self.mock_config_manager = MagicMock()
        self.mock_notifier = MagicMock()
        self.mock_checkpoint_manager = MagicMock()
        
        # Set up mock checkpoint data
        self.mock_checkpoint_data = {
            "scan_id": "test_123",
            "domain": "example.com",
            "start_time": 1620000000,
            "last_update": 1620000100,
            "status": "in_progress",
            "phases": {
                "subdomain_enum": {"status": "completed", "progress": 100, "results_count": 5},
                "alive_check": {"status": "in_progress", "progress": 50, "results_count": 3}
            },
            "statistics": {
                "subdomains_found": 5,
                "alive_subdomains": 3,
                "vulnerabilities_found": 0
            },
            "environment": {
                "tool_versions": {
                    "subfinder": "2.5.3",
                    "httpx": "1.2.5",
                    "nuclei": "2.9.3"
                }
            }
        }
    
    def tearDown(self):
        """Tear down test fixtures after each test method."""
        # Clean up temporary directory
        import shutil
        shutil.rmtree(self.temp_dir)
    
    async def _create_scanner_with_mocks(self, resuming=False):
        """Helper to create a scanner with mocked dependencies."""
        # Set up the domain and checkpoint path
        domain = "example.com"
        checkpoint_path = self.output_dir / "checkpoints" / "scan_state.json" if resuming else None
        
        # Set up scanner with mocked dependencies
        with patch('autosubnuclei.core.scanner.ToolManager', return_value=self.mock_tool_manager), \
             patch('autosubnuclei.core.scanner.ConfigManager', return_value=self.mock_config_manager), \
             patch('autosubnuclei.core.scanner.Notifier', return_value=self.mock_notifier), \
             patch('autosubnuclei.core.scanner.CheckpointManager', return_value=self.mock_checkpoint_manager):
            
            # Configure mock checkpoint manager behavior
            if resuming:
                self.mock_checkpoint_manager.load_checkpoint.return_value = True
                self.mock_checkpoint_manager.get_scan_summary.return_value = self.mock_checkpoint_data
                self.mock_checkpoint_manager.validate_environment.return_value = (True, {})
            
            scanner = SecurityScanner(domain, self.output_dir, self.templates_dir, checkpoint_path)
            
            # Replace CheckpointManager with our mock
            scanner.checkpoint_manager = self.mock_checkpoint_manager
            
            return scanner
            
    @patch('tempfile.NamedTemporaryFile')
    async def test_run_httpx_new_scan(self, mock_temp_file):
        """Test _run_httpx method with a new scan (not resuming)."""
        # Setup
        scanner = await self._create_scanner_with_mocks(resuming=False)
        scanner._run_httpx_batch = AsyncMock(return_value=["alive1.example.com", "alive2.example.com"])
        
        # Mock the temp file
        mock_file = MagicMock()
        mock_file.name = str(self.output_dir / "temp_subdomains.txt")
        mock_temp_file.return_value = mock_file
        
        # Create the mock file
        with open(mock_file.name, 'w') as f:
            f.write("test")
        
        # Setup mock for tool existence check
        scanner.tool_manager.ensure_tool_exists = AsyncMock(return_value=True)
        
        # Test data
        subdomains = [
            "sub1.example.com",
            "sub2.example.com",
            "sub3.example.com",
            "sub4.example.com",
            "sub5.example.com"
        ]
        
        # Execute
        result = await scanner._run_httpx(subdomains)
        
        # Verify
        self.assertEqual(scanner._run_httpx_batch.call_count, 1)
        self.mock_checkpoint_manager.update_phase_status.assert_called()
        self.mock_checkpoint_manager.save_checkpoint.assert_called()
        self.assertEqual(result, "alive1.example.com\nalive2.example.com")
        self.assertEqual(scanner.scan_state["alive_subdomains"], 2)
        
    @patch('os.unlink')
    async def test_run_httpx_resume_completed_phase(self, mock_unlink):
        """Test _run_httpx method when resuming with completed alive_check phase."""
        # Setup
        scanner = await self._create_scanner_with_mocks(resuming=True)
        
        # Mock the _run_httpx_batch method
        scanner._run_httpx_batch = AsyncMock()
        
        # Setup checkpoint manager to indicate completed phase
        self.mock_checkpoint_manager.get_phase_status.return_value = "completed"
        
        # Create a mock alive.txt file
        alive_file = self.output_dir / "alive.txt"
        alive_content = "alive1.example.com\nalive2.example.com\nalive3.example.com"
        
        with open(alive_file, 'w') as f:
            f.write(alive_content)
        
        # Execute
        result = await scanner._run_httpx(["sub1.example.com", "sub2.example.com"])
        
        # Verify
        self.assertEqual(result, alive_content)
        self.assertEqual(scanner.scan_state["alive_subdomains"], 3)
        self.mock_checkpoint_manager.update_phase_status.assert_not_called()
        scanner._run_httpx_batch.assert_not_called()
        
    @patch('tempfile.NamedTemporaryFile')
    async def test_run_httpx_resume_in_progress(self, mock_temp_file):
        """Test _run_httpx method when resuming with in-progress alive_check phase."""
        # Setup
        scanner = await self._create_scanner_with_mocks(resuming=True)
        scanner._run_httpx_batch = AsyncMock(return_value=["alive3.example.com", "alive4.example.com"])
        
        # Mock the temp file
        mock_file = MagicMock()
        mock_file.name = str(self.output_dir / "temp_subdomains.txt")
        mock_temp_file.return_value = mock_file
        
        # Create the mock file
        with open(mock_file.name, 'w') as f:
            f.write("test")
        
        # Setup checkpoint manager to indicate in-progress phase with checkpoint data
        self.mock_checkpoint_manager.get_phase_status.return_value = "in_progress"
        self.mock_checkpoint_manager.get_phase_data.return_value = {
            "checkpoint": {
                "batch_index": 1,  # Already processed first batch
                "batch_size": 2
            }
        }
        
        # Setup mock for tool existence check
        scanner.tool_manager.ensure_tool_exists = AsyncMock(return_value=True)
        
        # Test data - 4 subdomains, with batch size 2, first batch should be skipped
        subdomains = [
            "sub1.example.com",  # Batch 1 (already processed)
            "sub2.example.com",  # Batch 1 (already processed)
            "sub3.example.com",  # Batch 2 (should be processed)
            "sub4.example.com"   # Batch 2 (should be processed)
        ]
        
        # Execute
        result = await scanner._run_httpx(subdomains)
        
        # Verify
        self.assertEqual(scanner._run_httpx_batch.call_count, 1)  # Only second batch should be processed
        self.mock_checkpoint_manager.update_phase_status.assert_called()
        self.mock_checkpoint_manager.save_checkpoint.assert_called()
        self.assertEqual(result, "alive3.example.com\nalive4.example.com")
        
    @patch('tempfile.NamedTemporaryFile')
    async def test_run_httpx_tool_not_available(self, mock_temp_file):
        """Test _run_httpx when httpx tool is not available."""
        # Setup
        scanner = await self._create_scanner_with_mocks(resuming=False)
        
        # Mock the temp file
        mock_file = MagicMock()
        mock_file.name = str(self.output_dir / "temp_subdomains.txt")
        mock_temp_file.return_value = mock_file
        
        # Create the mock file
        with open(mock_file.name, 'w') as f:
            f.write("test")
        
        # Setup mock for tool existence check to fail
        scanner.tool_manager.ensure_tool_exists = AsyncMock(return_value=False)
        
        # Execute and check for exception
        with self.assertRaises(RuntimeError):
            await scanner._run_httpx(["sub1.example.com"])
            
    @patch('tempfile.NamedTemporaryFile')
    @patch('os.unlink')
    async def test_run_httpx_cleanup_on_exception(self, mock_unlink, mock_temp_file):
        """Test _run_httpx properly cleans up temporary files even when exceptions occur."""
        # Setup
        scanner = await self._create_scanner_with_mocks(resuming=False)
        
        # Mock the temp file
        mock_file = MagicMock()
        mock_file.name = str(self.output_dir / "temp_subdomains.txt")
        mock_temp_file.return_value = mock_file
        
        # Create the mock file
        with open(mock_file.name, 'w') as f:
            f.write("test")
        
        # Setup mock for tool existence check to succeed but httpx_batch to fail
        scanner.tool_manager.ensure_tool_exists = AsyncMock(return_value=True)
        scanner._run_httpx_batch = AsyncMock(side_effect=Exception("Test exception"))
        
        # Execute and check for exception
        with self.assertRaises(Exception):
            await scanner._run_httpx(["sub1.example.com"])
            
        # Verify cleanup was attempted
        mock_unlink.assert_called_once_with(Path(mock_file.name))
        
    @patch('tempfile.NamedTemporaryFile')
    async def test_run_httpx_large_subdomain_list(self, mock_temp_file):
        """Test _run_httpx with a large list of subdomains to ensure batch processing works correctly."""
        # Setup
        scanner = await self._create_scanner_with_mocks(resuming=False)
        scanner._adaptive_batch_size = MagicMock(return_value=5)  # Force small batch size
        scanner._run_httpx_batch = AsyncMock(side_effect=[
            ["alive1.example.com", "alive2.example.com"],  # Batch 1
            ["alive3.example.com"],                       # Batch 2
            []                                            # Batch 3
        ])
        
        # Mock the temp file
        mock_file = MagicMock()
        mock_file.name = str(self.output_dir / "temp_subdomains.txt")
        mock_temp_file.return_value = mock_file
        
        # Create the mock file
        with open(mock_file.name, 'w') as f:
            f.write("test")
        
        # Setup mock for tool existence check
        scanner.tool_manager.ensure_tool_exists = AsyncMock(return_value=True)
        
        # Generate a larger test data set
        subdomains = [f"sub{i}.example.com" for i in range(1, 14)]  # 13 subdomains
        
        # Execute
        result = await scanner._run_httpx(subdomains)
        
        # Verify
        self.assertEqual(scanner._run_httpx_batch.call_count, 3)  # Should be processed in 3 batches
        self.assertEqual(scanner.scan_state["alive_subdomains"], 3)  # 3 alive domains found
        self.assertEqual(result, "alive1.example.com\nalive2.example.com\nalive3.example.com")

def run_async_test(coro):
    """Helper function to run async test methods."""
    return asyncio.run(coro)

# Patch the TestCase to handle async tests
def async_test(test_case):
    """Decorator for async test methods."""
    def wrapper(*args, **kwargs):
        return run_async_test(test_case(*args, **kwargs))
    return wrapper

# Apply the decorator to all async test methods
for method_name in dir(TestSecurityScanner):
    if method_name.startswith('test_'):
        method = getattr(TestSecurityScanner, method_name)
        if asyncio.iscoroutinefunction(method):
            setattr(TestSecurityScanner, method_name, async_test(method))

if __name__ == '__main__':
    unittest.main() 