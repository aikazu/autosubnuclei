"""
Tool manager for downloading and extracting required security tools
"""

import os
import shutil
import sys
import stat
import subprocess
import logging
import asyncio
from pathlib import Path
from typing import Optional, Dict, List, Tuple
import re

from .helpers import (
    get_platform_info,
    create_requests_session,
    download_file,
    extract_zip,
    validate_file,
    retry_with_backoff
)

logger = logging.getLogger(__name__)

class ToolManager:
    def __init__(self):
        # Use tools directory in the workspace
        self.tools_dir = Path(__file__).parent.parent.parent / "tools"
        self.tools_dir.mkdir(parents=True, exist_ok=True)
        
        # Get system information
        self.system, self.arch = get_platform_info()
        
        self.required_tools = {
            "subfinder": {
                "repo": "projectdiscovery/subfinder",
                "executable": "subfinder.exe" if self.system == "windows" else "subfinder",
                "version_cmd": ["subfinder", "-version"]
            },
            "httpx": {
                "repo": "projectdiscovery/httpx",
                "executable": "httpx.exe" if self.system == "windows" else "httpx",
                "version_cmd": ["httpx", "-version"]
            },
            "nuclei": {
                "repo": "projectdiscovery/nuclei",
                "executable": "nuclei.exe" if self.system == "windows" else "nuclei",
                "version_cmd": ["nuclei", "-version"]
            }
        }
        
        # Apply Windows-specific fixes
        if self.system == "windows":
            self._fix_windows_path_issues()
        
        self._setup_environment()

    def _get_latest_release(self, repo: str) -> Tuple[str, str]:
        """
        Get the latest release version and download URL for a GitHub repository
        with improved error handling and retries.
        """
        def _try_api_request():
            session = create_requests_session()
            release_url = f"https://api.github.com/repos/{repo}/releases/latest"
            response = session.get(release_url)
            response.raise_for_status()
            return response.json()
        
        try:
            # Try with retries
            release_data = retry_with_backoff(
                _try_api_request, 
                max_retries=3
            )
            
            version = release_data['tag_name'].lstrip('v')
            assets = release_data.get('assets', [])
            
            # Find the correct asset for our platform
            for asset in assets:
                asset_name = asset['name'].lower()
                if (self.system in asset_name and 
                    self.arch in asset_name and 
                    asset_name.endswith('.zip')):
                    return version, asset['browser_download_url']
            
            # Fall back to constructing URL if no matching asset found
            return self._construct_download_url(repo, version)
        
        except Exception as e:
            logger.error(f"GitHub API request failed: {str(e)}")
            
            # Try alternative approach - get latest from tags
            try:
                return self._get_latest_from_tags(repo)
            except Exception as nested_e:
                logger.error(f"Failed to get latest release from tags: {str(nested_e)}")
                
                # Last resort - try to construct a URL with a guessed version
                tool_name = repo.split('/')[-1]
                guessed_version = self._guess_latest_version(tool_name)
                if guessed_version:
                    logger.warning(f"Using guessed version {guessed_version} for {tool_name}")
                    return guessed_version, self._construct_download_url(repo, guessed_version)
                
                raise RuntimeError(f"Could not determine download URL for {repo}: {str(e)}")

    def _construct_download_url(self, repo: str, version: str) -> Tuple[str, str]:
        """
        Construct a download URL based on repository and version
        """
        tool_name = repo.split('/')[-1]
        download_url = f"https://github.com/{repo}/releases/download/v{version}/{tool_name}_{version}_{self.system}_{self.arch}.zip"
        logger.info(f"Constructed download URL: {download_url}")
        return version, download_url

    def _get_latest_from_tags(self, repo: str) -> Tuple[str, str]:
        """
        Get the latest version from repository tags as a fallback
        """
        def _try_tags_request():
            session = create_requests_session()
            tags_url = f"https://api.github.com/repos/{repo}/tags"
            response = session.get(tags_url)
            response.raise_for_status()
            return response.json()
        
        # Try with retries
        tags = retry_with_backoff(_try_tags_request, max_retries=3)
        
        if not tags:
            raise ValueError(f"No tags found for repository {repo}")
            
        latest_tag = tags[0]['name'].lstrip('v')
        return self._construct_download_url(repo, latest_tag)

    def _guess_latest_version(self, tool_name: str) -> Optional[str]:
        """
        Guess the latest version of a tool based on common patterns
        """
        # Common version patterns for security tools
        common_versions = ["2.0.0", "1.0.0", "0.9.0", "0.10.0", "0.8.0"]
        
        for version in common_versions:
            logger.debug(f"Trying to guess version {version} for {tool_name}")
            return version
            
        return None

    def _verify_download(self, download_path: Path, expected_min_size: int = 1000) -> bool:
        """
        Verify that a downloaded file is valid.
        
        Args:
            download_path: Path to the downloaded file
            expected_min_size: Minimum expected file size in bytes
            
        Returns:
            bool: True if the file is valid, False otherwise
        """
        if not download_path.exists():
            logger.error(f"Downloaded file does not exist: {download_path}")
            return False
            
        # Check file size
        file_size = download_path.stat().st_size
        if file_size < expected_min_size:
            logger.error(f"Downloaded file too small ({file_size} bytes): {download_path}")
            return False
            
        # Additional checks could be added here (checksum, signature, etc.)
        
        return True

    def _get_download_url(self, tool_name: str) -> Tuple[str, str]:
        """
        Get the latest version and download URL for a tool
        """
        tool_info = self.required_tools[tool_name]
        version, download_url = self._get_latest_release(tool_info["repo"])
        logger.info(f"Found latest version {version} for {tool_name}")
        return version, download_url

    def _setup_environment(self) -> None:
        """
        Setup environment variables and PATH
        """
        # Add tools directory to PATH if not already present
        tools_path = str(self.tools_dir.resolve())
        
        # Check if already in PATH (case-insensitive on Windows)
        path_env = os.environ.get('PATH', '')
        path_separator = ';' if self.system == "windows" else ':'
        path_entries = path_env.split(path_separator)
        
        # On Windows, compare lowercase paths
        if self.system == "windows":
            if tools_path.lower() not in [p.lower() for p in path_entries]:
                os.environ['PATH'] = f"{tools_path}{path_separator}{path_env}"
        else:
            if tools_path not in path_entries:
                os.environ['PATH'] = f"{tools_path}{path_separator}{path_env}"
        
        logger.debug(f"Updated PATH: {os.environ['PATH']}")

    def _validate_windows_path(self, executable_path: Path) -> bool:
        """
        Validate that a Windows executable path is correctly formed and accessible
        
        Args:
            executable_path: Path to the executable
            
        Returns:
            bool: True if valid, False otherwise
        """
        # Skip validation for non-Windows systems
        if self.system != "windows":
            return True
            
        try:
            # Apply validation steps sequentially with early returns
            if not self._validate_file_exists(executable_path):
                return False
                
            if not self._validate_file_extension(executable_path, '.exe'):
                return False
                
            if not self._validate_file_access(executable_path):
                return False
                
            if not self._validate_file_size(executable_path, min_size=100):
                return False
                
            if not self._validate_with_powershell(executable_path):
                return False
                
            return True
        except Exception as e:
            logger.debug(f"Windows path validation failed: {str(e)}")
            return False
            
    def _validate_file_exists(self, file_path: Path) -> bool:
        """Validate that a file exists"""
        return file_path.exists()
        
    def _validate_file_extension(self, file_path: Path, extension: str) -> bool:
        """Validate that a file has the expected extension"""
        return str(file_path).lower().endswith(extension.lower())
        
    def _validate_file_access(self, file_path: Path) -> bool:
        """Validate that a file is accessible for reading"""
        try:
            with open(file_path, 'rb') as f:
                # Just read a small part to verify access
                f.read(10)
            return True
        except Exception:
            return False
            
    def _validate_file_size(self, file_path: Path, min_size: int) -> bool:
        """Validate that a file meets the minimum size requirement"""
        try:
            if file_path.stat().st_size < min_size:
                logger.debug(f"File too small to be a valid executable: {file_path}")
                return False
            return True
        except Exception:
            return False
            
    def _validate_with_powershell(self, file_path: Path) -> bool:
        """Validate file using PowerShell for Windows-specific checks"""
        try:
            # Use PowerShell to check if file is readable
            check_cmd = f'powershell -Command "if (Test-Path -Path \'{str(file_path)}\' -PathType Leaf) {{ $true }} else {{ $false }}"'
            result = subprocess.run(check_cmd, capture_output=True, text=True, shell=True, timeout=5)
            if "True" not in result.stdout:
                logger.debug(f"PowerShell validation failed for {file_path}")
                return False
            return True
        except Exception as e:
            logger.debug(f"PowerShell validation error (non-critical): {str(e)}")
            # Don't fail here as this is an additional check
            return True

    def _fix_windows_path_issues(self) -> None:
        """
        Apply additional fixes for Windows-specific path issues.
        This should be called during initialization on Windows systems.
        """
        if self.system != "windows":
            return
            
        logger.debug("Applying Windows-specific path fixes")
        
        try:
            # 1. Try to expand the PATH variable - important for tools using other tools
            path_env = os.environ.get('PATH', '')
            
            # 2. Check for common Windows path issues and fix them
            # Sometimes Windows PATH entries have quotes or trailing backslashes that cause issues
            path_entries = path_env.split(';')
            fixed_entries = []
            
            for entry in path_entries:
                # Remove quotes
                fixed_entry = entry.strip().strip('"\'')
                
                # Remove trailing backslash
                if fixed_entry.endswith('\\'):
                    fixed_entry = fixed_entry[:-1]
                    
                fixed_entries.append(fixed_entry)
            
            # Rebuild PATH
            fixed_path = ';'.join(fixed_entries)
            if fixed_path != path_env:
                logger.debug(f"Fixed Windows PATH: {path_env} -> {fixed_path}")
                os.environ['PATH'] = fixed_path
                
            # 3. Make sure the tools directory is properly added to PATH
            self._setup_environment()
            
            # 4. Log current PATH for debugging
            logger.debug(f"Current PATH: {os.environ.get('PATH', '')}")
            
        except Exception as e:
            logger.warning(f"Error during Windows path fixes: {str(e)}")

    def _is_tool_installed(self, tool_name: str) -> bool:
        """
        Check if a tool is installed and working, with improved Windows support
        """
        tool_info = self.required_tools[tool_name]
        
        # First check if the tool exists in our tools directory
        tool_path_in_dir = self.tools_dir / tool_info["executable"]
        
        if tool_path_in_dir.exists():
            # For ProjectDiscovery tools, check if file is accessible and has proper size
            try:
                if self.system == "windows" and not self._validate_windows_path(tool_path_in_dir):
                    logger.debug(f"Windows validation failed for {tool_path_in_dir}")
                    return False
                    
                file_size = tool_path_in_dir.stat().st_size
                if file_size > 1000:  # Arbitrary minimum size for a valid executable
                    logger.debug(f"Found valid tool at {tool_path_in_dir} ({file_size} bytes)")
                    return True
            except Exception as e:
                logger.debug(f"Error checking tool: {str(e)}")
        
        # Fall back to checking in PATH - more robust for Windows
        try:
            tool_path = shutil.which(tool_info["executable"])
            if tool_path:
                logger.debug(f"Found tool in PATH at {tool_path}")
                return True
        except Exception as e:
            logger.debug(f"Error checking tool in PATH: {str(e)}")
        
        return False

    def _execute_windows_tool(self, tool_name: str, args: List[str]) -> subprocess.CompletedProcess:
        """
        Execute a tool on Windows with proper path handling.
        
        Args:
            tool_name: Name of the tool to execute
            args: Arguments to pass to the tool
            
        Returns:
            CompletedProcess instance with the command result
        """
        if self.system != "windows":
            raise RuntimeError("This method should only be called on Windows systems")
            
        # Resolve the executable path
        exec_path = self._resolve_windows_tool_path(tool_name)
        
        # Build and execute the command
        return self._execute_windows_command(exec_path, args)
    
    def _resolve_windows_tool_path(self, tool_name: str) -> str:
        """
        Resolve the path to a tool on Windows.
        
        Args:
            tool_name: Name of the tool to find
            
        Returns:
            String containing the quoted path to the tool executable
        """
        tool_info = self.required_tools[tool_name]
        tool_exec = tool_info["executable"]
        
        # Check in our tools directory first
        tool_path_in_dir = self.tools_dir / tool_exec
        
        if tool_path_in_dir.exists():
            # Use absolute path with quotes to handle spaces
            return f'"{str(tool_path_in_dir.resolve())}"'
            
        # Fall back to command in PATH
        tool_in_path = shutil.which(tool_exec)
        if tool_in_path:
            return f'"{tool_in_path}"'
            
        # Last resort: use just the executable name
        return tool_exec
    
    def _execute_windows_command(self, exec_path: str, args: List[str]) -> subprocess.CompletedProcess:
        """
        Execute a command on Windows with the given executable path and arguments.
        
        Args:
            exec_path: Path to the executable (quoted if needed)
            args: Arguments to pass to the executable
            
        Returns:
            CompletedProcess instance with the command result
        """
        # Build command string with arguments
        cmd = f"{exec_path} {' '.join(args)}"
        
        # Set environment with current PATH to ensure tools are found
        env = os.environ.copy()
        
        logger.debug(f"Executing Windows command: {cmd}")
        
        # Always use shell=True on Windows for this type of command
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            shell=True,
            env=env
        )
    
    def test_tool_installation(self, tool_name: str) -> bool:
        """
        Test if a tool is properly installed and executable.
        
        Args:
            tool_name: Name of the tool to test
            
        Returns:
            bool: True if test passed, False otherwise
        """
        if tool_name not in self.required_tools:
            logger.error(f"Unknown tool: {tool_name}")
            return False
            
        if not self._is_tool_installed(tool_name):
            logger.error(f"Tool {tool_name} is not installed")
            return False
            
        tool_info = self.required_tools[tool_name]
        
        try:
            if self.system == "windows":
                result = self._execute_windows_tool(tool_name, ["-h"])
            else:
                tool_path = shutil.which(tool_info["executable"])
                if not tool_path:
                    tool_path = str(self.tools_dir / tool_info["executable"])
                
                result = subprocess.run(
                    [tool_path, "-h"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
            
            if result.returncode == 0 or "usage" in result.stdout.lower() or "usage" in result.stderr.lower():
                logger.info(f"Tool {tool_name} test successful")
                return True
            else:
                logger.error(f"Tool {tool_name} test failed with return code {result.returncode}")
                logger.debug(f"Stdout: {result.stdout}")
                logger.debug(f"Stderr: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Error testing {tool_name}: {str(e)}")
            return False
    
    def _ensure_correct_windows_permissions(self, tool_path: Path) -> bool:
        """
        Ensure the Windows executable has the correct permissions.
        
        Args:
            tool_path: Path to the tool executable
            
        Returns:
            bool: True if permissions are set correctly, False otherwise
        """
        if self.system != "windows":
            return True
            
        try:
            # On Windows, we need to make sure the file is not blocked
            # This often happens with files downloaded from the internet
            if not tool_path.exists():
                return False
                
            # Try to make the file readable and executable
            # This is a no-op on Windows, but included for completeness
            current_mode = os.stat(tool_path).st_mode
            os.chmod(tool_path, current_mode | stat.S_IEXEC | stat.S_IREAD)
            
            # On newer Windows versions, we can use PowerShell to unblock the file
            if os.name == 'nt':
                try:
                    # Use PowerShell to unblock the file
                    unblock_cmd = f'powershell -Command "Unblock-File -Path \'{str(tool_path)}\'"'
                    subprocess.run(unblock_cmd, shell=True, timeout=5)
                    logger.debug(f"Unblocked file {tool_path}")
                except Exception as e:
                    logger.debug(f"Error unblocking file (may be normal): {str(e)}")
            
            return True
        except Exception as e:
            logger.error(f"Error setting Windows permissions: {str(e)}")
            return False
    
    def install_tool(self, tool_name: str) -> bool:
        """
        Install a tool from GitHub releases
        
        Args:
            tool_name: Name of the tool to install
            
        Returns:
            bool: True if the tool was installed successfully, False otherwise
        """
        if tool_name not in self.required_tools:
            logger.error(f"Unknown tool: {tool_name}")
            return False
        
        tool_info = self.required_tools[tool_name]
        executable = tool_info["executable"]
        tool_path = self.tools_dir / executable
        
        # Check if already installed
        if tool_path.exists() and self._is_tool_installed(tool_name):
            logger.info(f"Tool {tool_name} is already installed at {tool_path}")
            return True
        
        try:
            # If we reached here, we need to install or reinstall the tool
            logger.info(f"Installing {tool_name}...")
            
            # We'll try up to 3 different versions if download fails
            versions_to_try = []
            
            try:
                # Try getting the latest release version first
                version, download_url = self._get_latest_release(tool_info["repo"])
                versions_to_try.append((version, download_url))
                
                # Add fallback versions (these might not exist but we'll try)
                # Format common version patterns to try
                tool_repo = tool_info["repo"].split('/')[-1]
                for fallback_version in ["2.0.0", "1.0.1", "1.0.0", "0.10.0"]:
                    fallback_url = f"https://github.com/{tool_info['repo']}/releases/download/v{fallback_version}/{tool_repo}_{fallback_version}_{self.system}_{self.arch}.zip"
                    if (fallback_version, fallback_url) not in versions_to_try:
                        versions_to_try.append((fallback_version, fallback_url))
            except Exception as e:
                logger.error(f"Failed to get download URL for {tool_name}: {str(e)}")
                # Still add fallback versions
                tool_repo = tool_info["repo"].split('/')[-1]
                for fallback_version in ["2.0.0", "1.0.1", "1.0.0", "0.10.0"]:
                    fallback_url = f"https://github.com/{tool_info['repo']}/releases/download/v{fallback_version}/{tool_repo}_{fallback_version}_{self.system}_{self.arch}.zip"
                    versions_to_try.append((fallback_version, fallback_url))
            
            # Try each version until one works
            last_error = None
            for version, download_url in versions_to_try:
                try:
                    # Create a temporary directory for the download
                    import tempfile
                    with tempfile.TemporaryDirectory() as tmp_dir:
                        download_path = Path(tmp_dir) / f"{tool_name}.zip"
                        extract_path = Path(tmp_dir) / "extracted"
                        
                        # Download the tool
                        logger.info(f"Downloading {tool_name} v{version} from {download_url}")
                        retry_with_backoff(
                            lambda: download_file(download_url, download_path),
                            max_retries=3,
                            initial_wait=1,
                            backoff_factor=2
                        )
                        
                        # Verify the download
                        if not self._verify_download(download_path):
                            raise ValueError(f"Downloaded file verification failed for {tool_name}")
                        
                        # Extract the tool
                        logger.info(f"Extracting {tool_name}...")
                        extract_zip(download_path, extract_path)
                        
                        # Find the executable in the extracted files
                        found_executables = list(extract_path.glob(f"**/{executable}"))
                        if not found_executables:
                            raise FileNotFoundError(f"Could not find executable {executable} in extracted files")
                        
                        source_executable = found_executables[0]
                        
                        # Remove existing installation if exists
                        if tool_path.exists():
                            logger.info(f"Removing existing installation of {tool_name}")
                            tool_path.unlink()
                        
                        # Copy the executable to the tools directory
                        logger.info(f"Installing {tool_name} to {tool_path}")
                        shutil.copy2(source_executable, tool_path)
                        
                        # Make the tool executable (Linux/macOS)
                        if self.system != "windows":
                            os.chmod(tool_path, os.stat(tool_path).st_mode | stat.S_IEXEC)
                        else:
                            # On Windows, ensure file is properly "unblocked"
                            self._ensure_correct_windows_permissions(tool_path)
                        
                        # Verify installation
                        if not self.test_tool_installation(tool_name):
                            raise RuntimeError(f"Tool {tool_name} was installed but failed functional testing")
                        
                        # Successfully installed
                        logger.info(f"Successfully installed {tool_name} v{version} at {tool_path}")
                        return True
                        
                except Exception as e:
                    logger.warning(f"Failed to install {tool_name} v{version}: {str(e)}")
                    last_error = e
                    continue  # Try next version
            
            # If we get here, all versions failed
            if last_error:
                logger.error(f"All installation attempts failed for {tool_name}. Last error: {str(last_error)}")
            else:
                logger.error(f"All installation attempts failed for {tool_name} with unknown errors.")
                
            return False
        
        except Exception as e:
            logger.error(f"Failed to install {tool_name}: {str(e)}")
            
            # Try to clean up any partial installations
            if tool_path.exists():
                try:
                    tool_path.unlink()
                    logger.info(f"Cleaned up partial installation at {tool_path}")
                except Exception as cleanup_error:
                    logger.warning(f"Failed to clean up partial installation: {str(cleanup_error)}")
            
            return False

    def update_tool(self, tool_name: str) -> bool:
        """
        Update a specific tool to the latest version
        
        Returns:
            bool: True if update successful, False otherwise
        """
        if tool_name not in self.required_tools:
            raise ValueError(f"Unknown tool: {tool_name}")

        logging.info(f"Updating {tool_name}...")

        # Remove existing installation
        tool_info = self.required_tools[tool_name]
        tool_path = self.tools_dir / tool_info["executable"]
        if tool_path.exists():
            try:
                tool_path.unlink()
            except Exception as e:
                logging.error(f"Failed to remove existing {tool_name}: {str(e)}")
                return False

        # Install latest version
        return self.install_tool(tool_name)

    def get_tool_version(self, tool_name: str) -> Optional[str]:
        """
        Get the version of an installed tool with improved Windows support
        """
        if not self._is_tool_installed(tool_name):
            return None

        tool_info = self.required_tools[tool_name]
        try:
            # Check if the tool exists in our tools directory
            tool_path_in_dir = self.tools_dir / tool_info["executable"]
            
            if tool_path_in_dir.exists():
                # Use absolute path for the command
                exec_path = str(tool_path_in_dir.resolve())
            else:
                # Fall back to using the command from PATH
                exec_path = tool_info["executable"]
            
            # Build command
            if self.system == "windows":
                # On Windows, use string command with quotes around the path
                cmd = f'"{exec_path}" -version'
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=5,
                    shell=True
                )
            else:
                # For non-Windows, use command list without shell
                cmd = [exec_path, "-version"]
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=5,
                    shell=False
                )
            
            if result.returncode == 0:
                # Extract version number from command output
                output = result.stdout.strip()
                
                # ProjectDiscovery tools often show "Current Version: vX.Y.Z"
                pd_version_match = re.search(r'Current Version:\s*v?(\d+\.\d+\.\d+)', output, re.IGNORECASE)
                if pd_version_match:
                    return pd_version_match.group(1)
                
                # Look for version in format: vX.Y.Z or X.Y.Z
                version_match = re.search(r'v?(\d+\.\d+\.\d+)', output)
                if version_match:
                    return version_match.group(1)
                    
                # Look for version in format: version X.Y.Z
                version_match = re.search(r'version\s+v?(\d+\.\d+\.\d+)', output, re.IGNORECASE)
                if version_match:
                    return version_match.group(1)
                
                # If no match found, return a cleaned version of the first line
                first_line = output.split('\n')[0].strip()
                return first_line
                
        except Exception as e:
            logger.debug(f"Failed to get version for {tool_name}: {str(e)}")
        
        return None

    def _add_to_path(self, tool_path: Path) -> None:
        """
        Add tool directory to system PATH
        """
        tool_dir = str(tool_path.parent.resolve())
        
        # Check if already in PATH (case-insensitive on Windows)
        path_env = os.environ.get('PATH', '')
        path_separator = ';' if self.system == "windows" else ':'
        path_entries = path_env.split(path_separator)
        
        # On Windows, compare lowercase paths
        if self.system == "windows":
            if tool_dir.lower() not in [p.lower() for p in path_entries]:
                os.environ['PATH'] = f"{tool_dir}{path_separator}{path_env}"
        else:
            if tool_dir not in path_entries:
                os.environ['PATH'] = f"{tool_dir}{path_separator}{path_env}"
                
        logger.debug(f"Updated PATH with tool directory: {tool_dir}")
        
    async def ensure_tool_exists(self, tool_name: str) -> bool:
        """
        Ensure that a required tool exists and is working properly.
        If the tool is missing, attempt to install it.
        
        Args:
            tool_name: Name of the tool to verify/install
            
        Returns:
            bool: True if the tool exists and is working, False otherwise
        """
        if tool_name not in self.required_tools:
            logger.error(f"Unknown tool: {tool_name}")
            return False
            
        # Check if tool is already installed and working
        if self._is_tool_installed(tool_name) and self.test_tool_installation(tool_name):
            logger.debug(f"Tool {tool_name} is already installed and working")
            return True
            
        # Tool is missing or not working, attempt to install it
        logger.info(f"Installing {tool_name}...")
        
        # Convert to async installation
        loop = asyncio.get_event_loop()
        success = await loop.run_in_executor(None, self.install_tool, tool_name)
        
        if success:
            logger.info(f"Successfully installed {tool_name}")
            return True
        else:
            logger.error(f"Failed to install {tool_name}")
            return False
            
    async def get_tool_path(self, tool_name: str) -> Optional[Path]:
        """
        Get the absolute path to a tool executable.
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            Optional[Path]: Path to the tool executable if found, None otherwise
        """
        if tool_name not in self.required_tools:
            logger.error(f"Unknown tool: {tool_name}")
            return None
            
        # Ensure the tool exists before returning the path
        if not await self.ensure_tool_exists(tool_name):
            logger.error(f"Tool {tool_name} does not exist and could not be installed")
            return None
            
        tool_info = self.required_tools[tool_name]
        tool_path = self.tools_dir / tool_info["executable"]
        
        if tool_path.exists():
            return tool_path
            
        # If tool is not in our tools directory, try to find it in PATH
        try:
            # Use 'where' on Windows, 'which' on other platforms
            if self.system == "windows":
                cmd = f"where {tool_info['executable']}"
                shell = True
            else:
                cmd = ["which", tool_info["executable"]]
                shell = False
                
            result = subprocess.run(cmd, capture_output=True, text=True, shell=shell)
            
            if result.returncode == 0:
                # Get the first match
                path_str = result.stdout.strip().split('\n')[0]
                return Path(path_str)
        except Exception as e:
            logger.debug(f"Error finding tool in PATH: {str(e)}")
            
        return None

    def install_all_tools(self) -> None:
        """
        Install all required tools in the correct order
        """
        # Install tools in the order they are defined in self.required_tools
        for tool_name in self.required_tools:
            try:
                self.install_tool(tool_name)
            except Exception as e:
                logger.error(f"Failed to install {tool_name}: {str(e)}")
                raise

    def verify_all_tools(self) -> Dict[str, bool]:
        """
        Verify all required tools are installed and working
        """
        return {tool: self._is_tool_installed(tool) for tool in self.required_tools} 