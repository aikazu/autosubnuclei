#!/usr/bin/env python3
"""
Unit tests for the ToolManager class.

These tests focus on the methods marked for refactoring in the REFACTORING.md document:
1. _validate_windows_path 
2. _execute_windows_tool
3. Other complex methods with deep nesting
"""

import os
import sys
import unittest
from pathlib import Path
import tempfile
import logging
import platform
import shutil
import subprocess
from unittest.mock import patch, MagicMock

# Add the parent directory to sys.path to allow imports from the autosubnuclei package
sys.path.insert(0, str(Path(__file__).parent))

from autosubnuclei.utils.tool_manager import ToolManager

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('test_tool_manager')

class TestToolManager(unittest.TestCase):
    """Test cases for the ToolManager class."""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.temp_dir = tempfile.mkdtemp(prefix="tool_manager_test_")
        self.tool_manager = ToolManager()
        
        # Create a dummy executable file for testing
        self.dummy_exe_path = Path(self.temp_dir) / "dummy.exe"
        with open(self.dummy_exe_path, 'wb') as f:
            f.write(b'MZ' + b'\0' * 100)  # Simple MZ header for Windows exe
            
        # Create a non-executable file
        self.non_exe_path = Path(self.temp_dir) / "dummy.txt"
        with open(self.non_exe_path, 'w') as f:
            f.write("This is not an executable")
            
        # Create a non-existent path for testing
        self.nonexistent_path = Path(self.temp_dir) / "does_not_exist.exe"
        
        # Create test tools directory structure
        self.tools_dir = Path(self.temp_dir) / "tools"
        self.tools_dir.mkdir(parents=True, exist_ok=True)
        
    def tearDown(self):
        """Tear down test fixtures after each test method."""
        # Clean up temporary directory
        shutil.rmtree(self.temp_dir)
            
    def test_validate_windows_path_non_windows(self):
        """Test _validate_windows_path when not on Windows."""
        with patch.object(self.tool_manager, 'system', 'linux'):
            # Should always return True when not on Windows
            self.assertTrue(self.tool_manager._validate_windows_path(self.dummy_exe_path))
            self.assertTrue(self.tool_manager._validate_windows_path(self.non_exe_path))
            self.assertTrue(self.tool_manager._validate_windows_path(self.nonexistent_path))
            
    @unittest.skipIf(platform.system().lower() != 'windows', "Windows-specific test")
    def test_validate_windows_path_exists(self):
        """Test _validate_windows_path with existing executable on Windows."""
        with patch.object(self.tool_manager, 'system', 'windows'):
            # Should return True for valid executable
            self.assertTrue(self.tool_manager._validate_windows_path(self.dummy_exe_path))
            
    @unittest.skipIf(platform.system().lower() != 'windows', "Windows-specific test")
    def test_validate_windows_path_non_exe(self):
        """Test _validate_windows_path with non-executable file on Windows."""
        with patch.object(self.tool_manager, 'system', 'windows'):
            # Should return False for non-executable file
            self.assertFalse(self.tool_manager._validate_windows_path(self.non_exe_path))
            
    @unittest.skipIf(platform.system().lower() != 'windows', "Windows-specific test")
    def test_validate_windows_path_nonexistent(self):
        """Test _validate_windows_path with non-existent file on Windows."""
        with patch.object(self.tool_manager, 'system', 'windows'):
            # Should return False for non-existent file
            self.assertFalse(self.tool_manager._validate_windows_path(self.nonexistent_path))
    
    @unittest.skipIf(platform.system().lower() != 'windows', "Windows-specific test")
    def test_validate_windows_path_powershell_error(self):
        """Test _validate_windows_path when PowerShell validation fails."""
        with patch.object(self.tool_manager, 'system', 'windows'):
            with patch('subprocess.run') as mock_run:
                # Simulate PowerShell validation failure
                mock_run.return_value = MagicMock(stdout="False", stderr="", returncode=0)
                self.assertFalse(self.tool_manager._validate_windows_path(self.dummy_exe_path))
    
    @unittest.skipIf(platform.system().lower() != 'windows', "Windows-specific test")
    def test_validate_windows_path_powershell_exception(self):
        """Test _validate_windows_path when PowerShell validation raises exception."""
        with patch.object(self.tool_manager, 'system', 'windows'):
            with patch('subprocess.run') as mock_run:
                # Simulate PowerShell validation exception
                mock_run.side_effect = subprocess.SubprocessError("Command failed")
                # Should continue and return True as PowerShell validation is non-critical
                self.assertTrue(self.tool_manager._validate_windows_path(self.dummy_exe_path))
    
    @unittest.skipIf(platform.system().lower() != 'windows', "Windows-specific test")
    def test_validate_windows_path_file_too_small(self):
        """Test _validate_windows_path with a file that's too small to be valid executable."""
        with patch.object(self.tool_manager, 'system', 'windows'):
            # Create a very small file
            tiny_exe_path = Path(self.temp_dir) / "tiny.exe"
            with open(tiny_exe_path, 'wb') as f:
                f.write(b'MZ')  # Only 2 bytes
                
            # Should return False for file that's too small
            self.assertFalse(self.tool_manager._validate_windows_path(tiny_exe_path))
    
    @unittest.skipIf(platform.system().lower() != 'windows', "Windows-specific test")
    def test_validate_windows_path_with_exception(self):
        """Test _validate_windows_path with an exception during validation."""
        with patch.object(self.tool_manager, 'system', 'windows'):
            with patch.object(Path, 'exists') as mock_exists:
                # Simulate exception during validation
                mock_exists.side_effect = Exception("Test exception")
                self.assertFalse(self.tool_manager._validate_windows_path(self.dummy_exe_path))
                
    # Tests for _execute_windows_tool method
    @unittest.skipIf(platform.system().lower() != 'windows', "Windows-specific test")
    def test_execute_windows_tool_non_windows(self):
        """Test _execute_windows_tool on non-Windows system should raise RuntimeError."""
        with patch.object(self.tool_manager, 'system', 'linux'):
            with self.assertRaises(RuntimeError):
                self.tool_manager._execute_windows_tool("subfinder", ["-h"])
                
    @unittest.skipIf(platform.system().lower() != 'windows', "Windows-specific test")
    def test_execute_windows_tool_with_tools_dir(self):
        """Test _execute_windows_tool using tool from tools directory."""
        with patch.object(self.tool_manager, 'system', 'windows'):
            # Create a mock tool in the tools directory
            mock_tool_name = "subfinder"
            mock_tool_exe = f"{mock_tool_name}.exe"
            mock_tool_path = self.tools_dir / mock_tool_exe
            
            # Create a dummy executable
            with open(mock_tool_path, 'wb') as f:
                f.write(b'MZ' + b'\0' * 100)
                
            with patch.object(self.tool_manager, 'tools_dir', self.tools_dir):
                with patch('subprocess.run') as mock_run:
                    mock_run.return_value = MagicMock(
                        stdout="Test output", 
                        stderr="", 
                        returncode=0
                    )
                    
                    # Run the method
                    result = self.tool_manager._execute_windows_tool(mock_tool_name, ["-h"])
                    
                    # Verify subprocess.run was called with the right arguments
                    mock_run.assert_called_once()
                    # The command should include the full path to the tool in double quotes
                    call_args = mock_run.call_args[0][0]
                    self.assertIn(f'"{str(mock_tool_path.resolve())}"', call_args)
                    self.assertIn("-h", call_args)
                    
                    # Check that shell=True and proper environment was used
                    kwargs = mock_run.call_args[1]
                    self.assertTrue(kwargs['shell'])
                    self.assertEqual(kwargs['env'], os.environ.copy())
    
    @unittest.skipIf(platform.system().lower() != 'windows', "Windows-specific test")
    def test_execute_windows_tool_from_path(self):
        """Test _execute_windows_tool using tool from PATH."""
        with patch.object(self.tool_manager, 'system', 'windows'):
            mock_tool_name = "subfinder"
            mock_tool_exe = f"{mock_tool_name}.exe"
            
            # Setup: Tool not in tools directory but in PATH
            with patch.object(self.tool_manager, 'tools_dir', self.tools_dir):
                with patch('shutil.which') as mock_which:
                    mock_path = str(Path(self.temp_dir) / mock_tool_exe)
                    mock_which.return_value = mock_path
                    
                    with patch('subprocess.run') as mock_run:
                        mock_run.return_value = MagicMock(
                            stdout="Test output", 
                            stderr="", 
                            returncode=0
                        )
                        
                        # Run the method
                        result = self.tool_manager._execute_windows_tool(mock_tool_name, ["-h"])
                        
                        # Verify subprocess.run was called with the right arguments
                        mock_run.assert_called_once()
                        # The command should include the full path to the tool in double quotes from PATH
                        call_args = mock_run.call_args[0][0]
                        self.assertIn(f'"{mock_path}"', call_args)
                        self.assertIn("-h", call_args)
    
    @unittest.skipIf(platform.system().lower() != 'windows', "Windows-specific test")
    def test_execute_windows_tool_fallback(self):
        """Test _execute_windows_tool falling back to just the executable name."""
        with patch.object(self.tool_manager, 'system', 'windows'):
            mock_tool_name = "subfinder"
            
            # Setup: Tool not in tools directory and not in PATH
            with patch.object(self.tool_manager, 'tools_dir', self.tools_dir):
                with patch('shutil.which') as mock_which:
                    mock_which.return_value = None  # Tool not in PATH
                    
                    with patch('subprocess.run') as mock_run:
                        mock_run.return_value = MagicMock(
                            stdout="Test output", 
                            stderr="", 
                            returncode=0
                        )
                        
                        # Run the method
                        result = self.tool_manager._execute_windows_tool(mock_tool_name, ["-h"])
                        
                        # Verify subprocess.run was called with the right arguments
                        mock_run.assert_called_once()
                        # The command should fall back to just using the executable name
                        call_args = mock_run.call_args[0][0]
                        self.assertIn(f"{mock_tool_name}.exe", call_args)
                        self.assertIn("-h", call_args)
    
    @unittest.skipIf(platform.system().lower() != 'windows', "Windows-specific test")
    def test_execute_windows_tool_with_spaces(self):
        """Test _execute_windows_tool with path containing spaces."""
        with patch.object(self.tool_manager, 'system', 'windows'):
            # Create a directory with spaces
            space_dir = Path(self.temp_dir) / "path with spaces"
            space_dir.mkdir(exist_ok=True)
            
            # Create a mock tool in that directory
            mock_tool_name = "subfinder"
            mock_tool_exe = f"{mock_tool_name}.exe"
            mock_tool_path = space_dir / mock_tool_exe
            
            # Create a dummy executable
            with open(mock_tool_path, 'wb') as f:
                f.write(b'MZ' + b'\0' * 100)
                
            # Setup: Tool in directory with spaces
            with patch.object(self.tool_manager, 'tools_dir', space_dir):
                with patch('subprocess.run') as mock_run:
                    mock_run.return_value = MagicMock(
                        stdout="Test output", 
                        stderr="", 
                        returncode=0
                    )
                    
                    # Run the method
                    result = self.tool_manager._execute_windows_tool(mock_tool_name, ["-h"])
                    
                    # Verify subprocess.run was called with the right arguments
                    mock_run.assert_called_once()
                    # The command should properly quote the path with spaces
                    call_args = mock_run.call_args[0][0]
                    self.assertIn(f'"{str(mock_tool_path.resolve())}"', call_args)
                    
    @unittest.skipIf(platform.system().lower() != 'windows', "Windows-specific test")
    def test_execute_windows_tool_complex_args(self):
        """Test _execute_windows_tool with complex command line arguments."""
        with patch.object(self.tool_manager, 'system', 'windows'):
            mock_tool_name = "subfinder"
            
            with patch.object(self.tool_manager, 'tools_dir', self.tools_dir):
                with patch('subprocess.run') as mock_run:
                    mock_run.return_value = MagicMock(
                        stdout="Test output", 
                        stderr="", 
                        returncode=0
                    )
                    
                    # Complex arguments
                    complex_args = [
                        "-d", "example.com",
                        "-o", "results.txt",
                        "-timeout", "60",
                        "-v"
                    ]
                    
                    # Run the method
                    result = self.tool_manager._execute_windows_tool(mock_tool_name, complex_args)
                    
                    # Verify subprocess.run was called with the right arguments
                    mock_run.assert_called_once()
                    # Check that all arguments are included
                    call_args = mock_run.call_args[0][0]
                    for arg in complex_args:
                        self.assertIn(arg, call_args)

if __name__ == '__main__':
    unittest.main() 