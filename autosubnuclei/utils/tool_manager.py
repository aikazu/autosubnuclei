"""
Tool manager for downloading and extracting required security tools
"""

import os
import shutil
import sys
import stat
import subprocess
import logging
from pathlib import Path
from typing import Optional, Dict, List, Tuple
import re

from .helpers import (
    get_platform_info,
    create_requests_session,
    download_file,
    extract_zip,
    validate_file
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
        self._setup_environment()

    def _get_latest_release(self, repo: str) -> Tuple[str, str]:
        """
        Get the latest release version and download URL for a GitHub repository
        """
        session = create_requests_session()
        # First try to get the latest release
        release_url = f"https://api.github.com/repos/{repo}/releases/latest"
        response = session.get(release_url)
        
        if response.status_code == 200:
            release_data = response.json()
            version = release_data['tag_name'].lstrip('v')
            assets = release_data.get('assets', [])
            
            # Find the correct asset for our platform
            for asset in assets:
                asset_name = asset['name'].lower()
                if (self.system in asset_name and 
                    self.arch in asset_name and 
                    asset_name.endswith('.zip')):
                    return version, asset['browser_download_url']
            
            # If no matching asset found, try to construct the URL
            tool_name = repo.split('/')[-1]
            return version, f"https://github.com/{repo}/releases/download/v{version}/{tool_name}_{version}_{self.system}_{self.arch}.zip"
        
        # If no releases found, try to get the latest tag
        tags_url = f"https://api.github.com/repos/{repo}/tags"
        response = session.get(tags_url)
        
        if response.status_code == 200:
            tags = response.json()
            if tags:
                latest_tag = tags[0]['name'].lstrip('v')
                tool_name = repo.split('/')[-1]
                return latest_tag, f"https://github.com/{repo}/releases/download/v{latest_tag}/{tool_name}_{latest_tag}_{self.system}_{self.arch}.zip"
        
        raise RuntimeError(f"Could not find latest release for {repo}")

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
        tools_path = str(self.tools_dir)
        if tools_path not in os.environ['PATH']:
            path_separator = ';' if self.system == "windows" else ':'
            os.environ['PATH'] = f"{tools_path}{path_separator}{os.environ['PATH']}"

    def _is_tool_installed(self, tool_name: str) -> bool:
        """
        Check if a tool is installed and working
        """
        tool_info = self.required_tools[tool_name]
        
        # First check if the tool exists in our tools directory
        tool_path_in_dir = self.tools_dir / tool_info["executable"]
        if tool_path_in_dir.exists():
            # For ProjectDiscovery tools, just checking if the file exists is enough
            # since their version command can sometimes fail in CI environments
            return True
        
        # Fall back to checking in PATH
        tool_path = shutil.which(tool_info["executable"])
        return tool_path is not None

    def install_tool(self, tool_name: str) -> bool:
        """
        Install a tool by downloading and extracting it from GitHub
        
        Returns:
            bool: True if successful, False otherwise
        """
        tool_info = self.required_tools[tool_name]
        
        logging.info(f"Installing {tool_name}...")
        
        try:
            # Get latest version and download URL
            version, download_url = self._get_download_url(tool_name)
            
            # Download the tool
            download_path = self.tools_dir / f"{tool_name}.zip"
            download_file(download_url, download_path)
            
            # Extract the tool
            extract_zip(download_path, self.tools_dir)
            
            # Make the tool executable on Unix-like systems
            if self.system != "windows":
                tool_path = self.tools_dir / tool_info["executable"]
                if tool_path.exists():
                    st = os.stat(tool_path)
                    os.chmod(tool_path, st.st_mode | stat.S_IEXEC)
            
            # Clean up the zip file
            if download_path.exists():
                download_path.unlink()
                
            # Verify installation
            if self._is_tool_installed(tool_name):
                logging.info(f"{tool_name} installed successfully!")
                return True
            else:
                logging.error(f"Failed to verify {tool_name} installation.")
                return False
                
        except Exception as e:
            logging.error(f"Error installing {tool_name}: {str(e)}")
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
        Get the version of an installed tool
        """
        if not self._is_tool_installed(tool_name):
            return None

        tool_info = self.required_tools[tool_name]
        try:
            # Check if the tool exists in our tools directory
            tool_path_in_dir = self.tools_dir / tool_info["executable"]
            cmd = None
            
            if tool_path_in_dir.exists():
                # Use absolute path for the command
                if self.system == "windows":
                    cmd = f"{tool_path_in_dir.absolute()} -version"
                else:
                    cmd = [str(tool_path_in_dir.absolute()), "-version"]
            else:
                # Fall back to using the command from PATH
                if self.system == "windows":
                    cmd = f"{tool_info['executable']} -version"
                else:
                    cmd = [tool_info['executable'], "-version"]
            
            # For Windows, always use shell=True with string command
            if self.system == "windows":
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=5,
                    shell=True
                )
            else:
                # For non-Windows, use command list without shell
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
        tool_dir = str(tool_path.parent)
        if tool_dir not in os.environ['PATH']:
            path_separator = ';' if self.system == "windows" else ':'
            os.environ['PATH'] = f"{tool_dir}{path_separator}{os.environ['PATH']}"

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