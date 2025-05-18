#!/usr/bin/env python3
"""
Unit tests for the CheckpointManager class.

This file tests the CheckpointManager.repair_checkpoint method
identified for refactoring in REFACTORING.md.
"""

import unittest
from unittest.mock import patch, MagicMock, mock_open
import sys
import json
import tempfile
import shutil
from pathlib import Path
import datetime

# Add the parent directory to sys.path to allow imports from the autosubnuclei package
sys.path.insert(0, str(Path(__file__).parent))

# Mock fcntl module which is not available on Windows
sys.modules['fcntl'] = MagicMock()

# Import the CheckpointManager class
from autosubnuclei.core.checkpoint_manager import CheckpointManager, FileLock


class TestCheckpointManager(unittest.TestCase):
    """Test cases for the CheckpointManager class."""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        # Create temporary directories for testing
        self.temp_dir = tempfile.mkdtemp(prefix="checkpoint_test_")
        self.output_dir = Path(self.temp_dir) / "output"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize the test domain
        self.test_domain = "example.com"
        
        # Create CheckpointManager instance
        self.checkpoint_manager = CheckpointManager(
            domain=self.test_domain,
            output_dir=self.output_dir
        )
        
        # Initialize checkpoint data with valid structure
        self.valid_checkpoint_data = {
            "scan_id": "example.com-12345678-abcd",
            "domain": "example.com",
            "start_time": datetime.datetime.now().isoformat(),
            "last_update": datetime.datetime.now().isoformat(),
            "status": "in_progress",
            "phases": {
                "subdomain_enumeration": {
                    "status": "completed",
                    "progress_percentage": 100,
                    "results_count": 10
                },
                "alive_check": {
                    "status": "in_progress",
                    "progress_percentage": 50,
                    "results_count": 5
                },
                "vulnerability_scan": {
                    "status": "pending",
                    "progress_percentage": 0,
                    "results_count": 0
                }
            },
            "statistics": {
                "subdomains_found": 10,
                "alive_subdomains": 5,
                "vulnerabilities_found": 0
            },
            "environment": {
                "tool_versions": {
                    "subfinder": "2.5.3",
                    "httpx": "1.2.5",
                    "nuclei": "2.9.3"
                },
                "templates_hash": "abcdef1234567890"
            }
        }
        
    def tearDown(self):
        """Tear down test fixtures after each test method."""
        # Clean up temporary directory
        shutil.rmtree(self.temp_dir)
        
    def test_repair_checkpoint_missing_scan_id(self):
        """Test repair_checkpoint with missing scan_id field."""
        # Create a checkpoint with missing scan_id
        checkpoint_data = self.valid_checkpoint_data.copy()
        del checkpoint_data["scan_id"]
        
        # Set as current checkpoint data
        self.checkpoint_manager.checkpoint_data = checkpoint_data
        
        # Mock the _write_checkpoint method
        with patch.object(self.checkpoint_manager, '_write_checkpoint', return_value=True):
            # Call repair_checkpoint
            result = self.checkpoint_manager.repair_checkpoint()
            
            # Verify repair was successful
            self.assertTrue(result)
            self.assertIn("scan_id", self.checkpoint_manager.checkpoint_data)
            # Verify a new scan_id was generated
            self.assertIsNotNone(self.checkpoint_manager.checkpoint_data["scan_id"])
            
    def test_repair_checkpoint_missing_domain(self):
        """Test repair_checkpoint with missing domain field."""
        # Create a checkpoint with missing domain
        checkpoint_data = self.valid_checkpoint_data.copy()
        del checkpoint_data["domain"]
        
        # Set as current checkpoint data
        self.checkpoint_manager.checkpoint_data = checkpoint_data
        
        # Mock the _write_checkpoint method
        with patch.object(self.checkpoint_manager, '_write_checkpoint', return_value=True):
            # Call repair_checkpoint
            result = self.checkpoint_manager.repair_checkpoint()
            
            # Verify repair was successful
            self.assertTrue(result)
            self.assertIn("domain", self.checkpoint_manager.checkpoint_data)
            # Verify domain was set correctly
            self.assertEqual(self.checkpoint_manager.checkpoint_data["domain"], self.test_domain)
            
    def test_repair_checkpoint_missing_timestamps(self):
        """Test repair_checkpoint with missing timestamp fields."""
        # Create a checkpoint with missing timestamps
        checkpoint_data = self.valid_checkpoint_data.copy()
        del checkpoint_data["start_time"]
        del checkpoint_data["last_update"]
        
        # Set as current checkpoint data
        self.checkpoint_manager.checkpoint_data = checkpoint_data
        
        # Mock the _write_checkpoint method
        with patch.object(self.checkpoint_manager, '_write_checkpoint', return_value=True):
            # Call repair_checkpoint
            result = self.checkpoint_manager.repair_checkpoint()
            
            # Verify repair was successful
            self.assertTrue(result)
            self.assertIn("start_time", self.checkpoint_manager.checkpoint_data)
            self.assertIn("last_update", self.checkpoint_manager.checkpoint_data)
            
    def test_repair_checkpoint_missing_status(self):
        """Test repair_checkpoint with missing status field."""
        # Create a checkpoint with missing status
        checkpoint_data = self.valid_checkpoint_data.copy()
        del checkpoint_data["status"]
        
        # Set as current checkpoint data
        self.checkpoint_manager.checkpoint_data = checkpoint_data
        
        # Mock the _write_checkpoint method
        with patch.object(self.checkpoint_manager, '_write_checkpoint', return_value=True):
            # Call repair_checkpoint
            result = self.checkpoint_manager.repair_checkpoint()
            
            # Verify repair was successful
            self.assertTrue(result)
            self.assertIn("status", self.checkpoint_manager.checkpoint_data)
            # Verify status was set to in_progress
            self.assertEqual(self.checkpoint_manager.checkpoint_data["status"], "in_progress")
            
    def test_repair_checkpoint_missing_phases(self):
        """Test repair_checkpoint with missing phases field."""
        # Create a checkpoint with missing phases
        checkpoint_data = self.valid_checkpoint_data.copy()
        del checkpoint_data["phases"]
        
        # Set as current checkpoint data
        self.checkpoint_manager.checkpoint_data = checkpoint_data
        
        # Mock the _write_checkpoint method
        with patch.object(self.checkpoint_manager, '_write_checkpoint', return_value=True):
            # Call repair_checkpoint
            result = self.checkpoint_manager.repair_checkpoint()
            
            # Verify repair was successful
            self.assertTrue(result)
            self.assertIn("phases", self.checkpoint_manager.checkpoint_data)
            # Verify all required phases were created
            self.assertIn("subdomain_enumeration", self.checkpoint_manager.checkpoint_data["phases"])
            self.assertIn("alive_check", self.checkpoint_manager.checkpoint_data["phases"])
            self.assertIn("vulnerability_scan", self.checkpoint_manager.checkpoint_data["phases"])
            
    def test_repair_checkpoint_missing_statistics(self):
        """Test repair_checkpoint with missing statistics field."""
        # Create a checkpoint with missing statistics
        checkpoint_data = self.valid_checkpoint_data.copy()
        del checkpoint_data["statistics"]
        
        # Set as current checkpoint data
        self.checkpoint_manager.checkpoint_data = checkpoint_data
        
        # Mock the _write_checkpoint method
        with patch.object(self.checkpoint_manager, '_write_checkpoint', return_value=True):
            # Call repair_checkpoint
            result = self.checkpoint_manager.repair_checkpoint()
            
            # Verify repair was successful
            self.assertTrue(result)
            self.assertIn("statistics", self.checkpoint_manager.checkpoint_data)
            # Verify statistics fields were created
            self.assertIn("subdomains_found", self.checkpoint_manager.checkpoint_data["statistics"])
            self.assertIn("alive_subdomains", self.checkpoint_manager.checkpoint_data["statistics"])
            self.assertIn("vulnerabilities_found", self.checkpoint_manager.checkpoint_data["statistics"])
            
    def test_repair_checkpoint_missing_environment(self):
        """Test repair_checkpoint with missing environment field."""
        # Create a checkpoint with missing environment
        checkpoint_data = self.valid_checkpoint_data.copy()
        del checkpoint_data["environment"]
        
        # Set as current checkpoint data
        self.checkpoint_manager.checkpoint_data = checkpoint_data
        
        # Mock the _write_checkpoint method
        with patch.object(self.checkpoint_manager, '_write_checkpoint', return_value=True):
            # Call repair_checkpoint
            result = self.checkpoint_manager.repair_checkpoint()
            
            # Verify repair was successful
            self.assertTrue(result)
            self.assertIn("environment", self.checkpoint_manager.checkpoint_data)
            # Verify environment fields were created
            self.assertIn("tool_versions", self.checkpoint_manager.checkpoint_data["environment"])
            self.assertIn("templates_hash", self.checkpoint_manager.checkpoint_data["environment"])
            
    def test_repair_checkpoint_missing_phase(self):
        """Test repair_checkpoint with a missing phase."""
        # Create a checkpoint with missing phase
        checkpoint_data = self.valid_checkpoint_data.copy()
        del checkpoint_data["phases"]["vulnerability_scan"]
        
        # Set as current checkpoint data
        self.checkpoint_manager.checkpoint_data = checkpoint_data
        
        # Mock the _write_checkpoint method
        with patch.object(self.checkpoint_manager, '_write_checkpoint', return_value=True):
            # Call repair_checkpoint
            result = self.checkpoint_manager.repair_checkpoint()
            
            # Verify repair was successful
            self.assertTrue(result)
            self.assertIn("vulnerability_scan", self.checkpoint_manager.checkpoint_data["phases"])
            
    def test_repair_checkpoint_uninitialized(self):
        """Test repair_checkpoint with uninitialized checkpoint."""
        # Set checkpoint data to None
        self.checkpoint_manager.checkpoint_data = None
        
        # Call repair_checkpoint
        result = self.checkpoint_manager.repair_checkpoint()
        
        # Verify repair failed
        self.assertFalse(result)
        
    def test_repair_checkpoint_exception(self):
        """Test repair_checkpoint handles exceptions gracefully."""
        # Create a checkpoint with valid data
        self.checkpoint_manager.checkpoint_data = self.valid_checkpoint_data.copy()
        
        # Mock _write_checkpoint to raise an exception
        with patch.object(self.checkpoint_manager, '_write_checkpoint', side_effect=Exception("Test exception")):
            # Call repair_checkpoint
            result = self.checkpoint_manager.repair_checkpoint()
            
            # Verify repair failed
            self.assertFalse(result)
            
    def test_repair_checkpoint_multiple_issues(self):
        """Test repair_checkpoint with multiple missing fields."""
        # Create a checkpoint with multiple missing fields
        checkpoint_data = {
            "domain": self.test_domain,
            "status": "in_progress",
            "phases": {
                "subdomain_enumeration": {
                    "status": "completed",
                    "progress_percentage": 100,
                    "results_count": 10
                }
            }
        }
        
        # Set as current checkpoint data
        self.checkpoint_manager.checkpoint_data = checkpoint_data
        
        # Mock the _write_checkpoint method
        with patch.object(self.checkpoint_manager, '_write_checkpoint', return_value=True):
            # Call repair_checkpoint
            result = self.checkpoint_manager.repair_checkpoint()
            
            # Verify repair was successful
            self.assertTrue(result)
            # Check all missing fields were added
            self.assertIn("scan_id", self.checkpoint_manager.checkpoint_data)
            self.assertIn("start_time", self.checkpoint_manager.checkpoint_data)
            self.assertIn("last_update", self.checkpoint_manager.checkpoint_data)
            self.assertIn("statistics", self.checkpoint_manager.checkpoint_data)
            self.assertIn("environment", self.checkpoint_manager.checkpoint_data)
            self.assertIn("alive_check", self.checkpoint_manager.checkpoint_data["phases"])
            self.assertIn("vulnerability_scan", self.checkpoint_manager.checkpoint_data["phases"])


if __name__ == '__main__':
    unittest.main() 