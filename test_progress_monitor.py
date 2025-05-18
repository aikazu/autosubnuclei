#!/usr/bin/env python3
"""
Unit tests for the ProgressMonitor class.

This file tests the ProgressMonitor class identified for refactoring in REFACTORING.md.
"""

import unittest
from unittest.mock import MagicMock, patch
import sys
from pathlib import Path
import io

# Add the parent directory to sys.path to allow imports from the autosubnuclei package
sys.path.insert(0, str(Path(__file__).parent))

# Import the ProgressMonitor class
from autosubnuclei import ProgressMonitor


class TestProgressMonitor(unittest.TestCase):
    """Test cases for the ProgressMonitor class."""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        # Create a mock scanner object
        self.mock_scanner = MagicMock()
        self.mock_scanner.scan_state = {}
        
        # Initialize the ProgressMonitor
        self.progress_monitor = ProgressMonitor(self.mock_scanner)
        
        # Mock tqdm to avoid actual progress bar display during tests
        self.tqdm_patcher = patch('autosubnuclei.tqdm')
        self.mock_tqdm = self.tqdm_patcher.start()
        self.mock_progress_bar = MagicMock()
        self.mock_tqdm.return_value = self.mock_progress_bar
        
    def tearDown(self):
        """Tear down test fixtures after each test method."""
        # Stop the tqdm patcher
        self.tqdm_patcher.stop()
        
    def test_update_with_missing_status(self):
        """Test update method when status is missing from scan_state."""
        # Set up scanner state with missing status
        self.mock_scanner.scan_state = {}
        
        # Call update method
        self.progress_monitor.update()
        
        # Verify that no progress bar was created
        self.mock_tqdm.assert_not_called()
        self.assertIsNone(self.progress_monitor.progress_bar)
        
    def test_update_with_new_status_downloading_templates(self):
        """Test update method when status changes to downloading_templates."""
        # Set up scanner state
        self.mock_scanner.scan_state = {"status": "downloading_templates"}
        
        # Call update method
        self.progress_monitor.update()
        
        # Verify that a progress bar was created with correct parameters
        self.mock_tqdm.assert_called_once()
        self.assertEqual(self.progress_monitor.last_status, "downloading_templates")
        self.assertIsNotNone(self.progress_monitor.progress_bar)
        
    def test_update_with_new_status_discovering_subdomains(self):
        """Test update method when status changes to discovering_subdomains."""
        # Set up scanner state
        self.mock_scanner.scan_state = {"status": "discovering_subdomains"}
        
        # Call update method
        self.progress_monitor.update()
        
        # Verify that a progress bar was created with correct parameters
        self.mock_tqdm.assert_called_once()
        self.assertEqual(self.progress_monitor.last_status, "discovering_subdomains")
        self.assertIsNotNone(self.progress_monitor.progress_bar)
        
    def test_update_with_new_status_probing_subdomains(self):
        """Test update method when status changes to probing_subdomains."""
        # Set up scanner state with subdomains
        self.mock_scanner.scan_state = {
            "status": "probing_subdomains",
            "subdomains": 10
        }
        
        # Call update method
        self.progress_monitor.update()
        
        # Verify that a progress bar was created with correct parameters
        self.mock_tqdm.assert_called_once()
        call_kwargs = self.mock_tqdm.call_args[1]
        self.assertEqual(call_kwargs["total"], 10)
        self.assertEqual(self.progress_monitor.last_status, "probing_subdomains")
        self.assertIsNotNone(self.progress_monitor.progress_bar)
        
    def test_update_with_new_status_probing_subdomains_no_count(self):
        """Test update method when status changes to probing_subdomains with no subdomains count."""
        # Set up scanner state without subdomains
        self.mock_scanner.scan_state = {"status": "probing_subdomains"}
        
        # Call update method
        self.progress_monitor.update()
        
        # Verify that a progress bar was created with indeterminate progress
        self.mock_tqdm.assert_called_once()
        call_kwargs = self.mock_tqdm.call_args[1]
        self.assertNotIn("total", call_kwargs)
        self.assertEqual(self.progress_monitor.last_status, "probing_subdomains")
        self.assertIsNotNone(self.progress_monitor.progress_bar)
        
    def test_update_with_new_status_scanning_vulnerabilities(self):
        """Test update method when status changes to scanning_vulnerabilities."""
        # Set up scanner state with alive_subdomains
        self.mock_scanner.scan_state = {
            "status": "scanning_vulnerabilities",
            "alive_subdomains": 5
        }
        
        # Call update method
        self.progress_monitor.update()
        
        # Verify that a progress bar was created with correct parameters
        self.mock_tqdm.assert_called_once()
        call_kwargs = self.mock_tqdm.call_args[1]
        self.assertEqual(call_kwargs["total"], 5)
        self.assertEqual(self.progress_monitor.last_status, "scanning_vulnerabilities")
        self.assertIsNotNone(self.progress_monitor.progress_bar)
        
    def test_update_with_new_status_scanning_vulnerabilities_no_count(self):
        """Test update method when status changes to scanning_vulnerabilities with no alive_subdomains count."""
        # Set up scanner state without alive_subdomains
        self.mock_scanner.scan_state = {"status": "scanning_vulnerabilities"}
        
        # Call update method
        self.progress_monitor.update()
        
        # Verify that a progress bar was created with indeterminate progress
        self.mock_tqdm.assert_called_once()
        call_kwargs = self.mock_tqdm.call_args[1]
        self.assertNotIn("total", call_kwargs)
        self.assertEqual(self.progress_monitor.last_status, "scanning_vulnerabilities")
        self.assertIsNotNone(self.progress_monitor.progress_bar)
        
    def test_update_with_new_status_completed(self):
        """Test update method when status changes to completed."""
        # Set up scanner state with completed status and duration/vulns info
        self.mock_scanner.scan_state = {
            "status": "completed",
            "duration": 60.5,
            "vulnerabilities": 3
        }
        
        # Capture stdout to verify the completion message
        captured_output = io.StringIO()
        sys.stdout = captured_output
        
        # Call update method
        self.progress_monitor.update()
        
        # Reset stdout
        sys.stdout = sys.__stdout__
        
        # Verify that completion message was printed and progress bar was closed
        self.assertIn("Scan completed", captured_output.getvalue())
        self.assertIn("60.5s", captured_output.getvalue())
        self.assertIn("3 potential vulnerabilities", captured_output.getvalue())
        self.assertEqual(self.progress_monitor.last_status, "completed")
        self.assertIsNone(self.progress_monitor.progress_bar)
        
    def test_update_with_new_status_error(self):
        """Test update method when status changes to error."""
        # Set up scanner state with error status and message
        self.mock_scanner.scan_state = {
            "status": "error",
            "error": "Connection timeout"
        }
        
        # Capture stdout to verify the error message
        captured_output = io.StringIO()
        sys.stdout = captured_output
        
        # Call update method
        self.progress_monitor.update()
        
        # Reset stdout
        sys.stdout = sys.__stdout__
        
        # Verify that error message was printed and progress bar was closed
        self.assertIn("Scan failed", captured_output.getvalue())
        self.assertIn("Connection timeout", captured_output.getvalue())
        self.assertEqual(self.progress_monitor.last_status, "error")
        self.assertIsNone(self.progress_monitor.progress_bar)
        
    def test_update_with_same_status_downloading_templates(self):
        """Test update method when status remains downloading_templates."""
        # Set up scanner state and initialize progress bar
        self.mock_scanner.scan_state = {"status": "downloading_templates"}
        self.progress_monitor.last_status = "downloading_templates"
        self.progress_monitor.progress_bar = self.mock_progress_bar
        
        # Call update method
        self.progress_monitor.update()
        
        # Verify that the progress bar was updated (pulsed)
        self.mock_progress_bar.refresh.assert_called_once()
        
    def test_update_with_same_status_discovering_subdomains(self):
        """Test update method when status remains discovering_subdomains and subdomain count increases."""
        # Set up scanner state and initialize progress bar
        self.mock_scanner.scan_state = {
            "status": "discovering_subdomains",
            "subdomains": 15
        }
        self.progress_monitor.last_status = "discovering_subdomains"
        self.progress_monitor.progress_bar = self.mock_progress_bar
        self.mock_progress_bar.n = 10  # Previously discovered 10 subdomains
        
        # Call update method
        self.progress_monitor.update()
        
        # Verify that the progress bar was updated with 5 more subdomains
        self.mock_progress_bar.update.assert_called_once_with(5)
        
    def test_update_with_same_status_probing_subdomains(self):
        """Test update method when status remains probing_subdomains and alive count increases."""
        # Set up scanner state and initialize progress bar
        self.mock_scanner.scan_state = {
            "status": "probing_subdomains",
            "alive_subdomains": 8
        }
        self.progress_monitor.last_status = "probing_subdomains"
        self.progress_monitor.progress_bar = self.mock_progress_bar
        self.mock_progress_bar.n = 5  # Previously found 5 alive subdomains
        
        # Call update method
        self.progress_monitor.update()
        
        # Verify that the progress bar was updated with 3 more alive subdomains
        self.mock_progress_bar.update.assert_called_once_with(3)
        
    def test_update_with_same_status_scanning_vulnerabilities(self):
        """Test update method when status remains scanning_vulnerabilities."""
        # Set up scanner state and initialize progress bar
        self.mock_scanner.scan_state = {"status": "scanning_vulnerabilities"}
        self.progress_monitor.last_status = "scanning_vulnerabilities"
        self.progress_monitor.progress_bar = self.mock_progress_bar
        self.mock_progress_bar.n = 2
        self.mock_progress_bar.total = 5
        
        # Call update method
        self.progress_monitor.update()
        
        # Verify that the progress bar was updated with an incremental step
        self.mock_progress_bar.update.assert_called_once()
        
    def test_update_with_exception(self):
        """Test update method handles exceptions gracefully."""
        # Set up scanner state to cause exception
        self.mock_scanner.scan_state = {"status": "probing_subdomains"}
        self.progress_monitor.last_status = "probing_subdomains"
        self.progress_monitor.progress_bar = self.mock_progress_bar
        
        # Make progress bar update raise an exception
        self.mock_progress_bar.update.side_effect = Exception("Test exception")
        
        # Capture stdout to verify the error message
        captured_output = io.StringIO()
        sys.stdout = captured_output
        
        # Call update method
        self.progress_monitor.update()
        
        # Reset stdout
        sys.stdout = sys.__stdout__
        
        # Verify that the exception was caught and progress bar was closed
        self.assertIn("Progress monitoring error", captured_output.getvalue())
        self.assertIsNone(self.progress_monitor.progress_bar)
        
    def test_close_progress_bar(self):
        """Test _close_progress_bar method."""
        # Set up progress bar
        self.progress_monitor.progress_bar = self.mock_progress_bar
        
        # Call _close_progress_bar method
        self.progress_monitor._close_progress_bar()
        
        # Verify that the progress bar was closed
        self.mock_progress_bar.close.assert_called_once()
        self.assertIsNone(self.progress_monitor.progress_bar)
        
    def test_close_progress_bar_with_exception(self):
        """Test _close_progress_bar method handles exceptions gracefully."""
        # Set up progress bar that raises exception when closed
        self.progress_monitor.progress_bar = self.mock_progress_bar
        self.mock_progress_bar.close.side_effect = Exception("Test exception")
        
        # Call _close_progress_bar method
        self.progress_monitor._close_progress_bar()
        
        # Verify that the exception was caught and progress bar was set to None
        self.assertIsNone(self.progress_monitor.progress_bar)


if __name__ == '__main__':
    unittest.main() 