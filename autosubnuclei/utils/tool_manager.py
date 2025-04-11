"""
Tool manager for downloading and extracting required security tools
"""

import os
import shutil
import sys
import zipfile
import requests
import logging
import platform
import stat
import subprocess
from pathlib import Path
from typing import Optional, Dict, List
from tqdm import tqdm

logger = logging.getLogger(__name__)

class ToolManager:
    def __init__(self):
        self.tools_dir = Path.home() / ".autosubnuclei" / "tools"
        self.tools_dir.mkdir(parents=True, exist_ok=True)
        self.required_tools = {
            "subfinder": {
                "url": "https://github.com/projectdiscovery/subfinder/releases/download/v2.6.3/subfinder_2.6.3_windows_amd64.zip",
                "executable": "subfinder.exe" if sys.platform == "win32" else "subfinder",
                "version_cmd": ["subfinder", "-version"]
            },
            "httpx": {
                "url": "https://github.com/projectdiscovery/httpx/releases/download/v1.3.7/httpx_1.3.7_windows_amd64.zip",
                "executable": "httpx.exe" if sys.platform == "win32" else "httpx",
                "version_cmd": ["httpx", "-version"]
            },
            "nuclei": {
                "url": "https://github.com/projectdiscovery/nuclei/releases/download/v3.1.7/nuclei_3.1.7_windows_amd64.zip",
                "executable": "nuclei.exe" if sys.platform == "win32" else "nuclei",
                "version_cmd": ["nuclei", "-version"]
            }
        }
        self._setup_environment()

    def _setup_environment(self) -> None:
        """
        Setup environment variables and PATH
        """
        # Add tools directory to PATH if not already present
        tools_path = str(self.tools_dir)
        if tools_path not in os.environ['PATH']:
            path_separator = ';' if sys.platform == 'win32' else ':'
            os.environ['PATH'] = f"{tools_path}{path_separator}{os.environ['PATH']}"

    def _is_tool_installed(self, tool_name: str) -> bool:
        """
        Check if a tool is installed and working
        """
        tool_info = self.required_tools[tool_name]
        tool_path = shutil.which(tool_info["executable"])
        
        if not tool_path:
            return False
            
        try:
            # Check if tool is executable and returns version
            result = subprocess.run(
                tool_info["version_cmd"],
                capture_output=True,
                text=True,
                timeout=5,
                shell=True if sys.platform == "win32" else False
            )
            return result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError):
            return False

    def install_tool(self, tool_name: str) -> None:
        """
        Install a specific tool
        """
        if tool_name not in self.required_tools:
            raise ValueError(f"Unknown tool: {tool_name}")

        # Check if tool is already installed and working
        if self._is_tool_installed(tool_name):
            logger.info(f"{tool_name} is already installed and working")
            return

        tool_info = self.required_tools[tool_name]

        # Download and extract tool
        logger.info(f"Downloading {tool_name}...")
        response = requests.get(tool_info["url"], stream=True)
        response.raise_for_status()

        # Save to temporary file
        temp_zip = self.tools_dir / f"{tool_name}.zip"
        with open(temp_zip, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        # Extract and make executable
        logger.info(f"Installing {tool_name}...")
        with zipfile.ZipFile(temp_zip, 'r') as zip_ref:
            zip_ref.extractall(self.tools_dir)

        # Clean up
        temp_zip.unlink()

        # Find the actual executable in the extracted files
        executable_path = None
        for root, _, files in os.walk(self.tools_dir):
            for file in files:
                if file.lower() == tool_info["executable"].lower():
                    executable_path = Path(root) / file
                    break
            if executable_path:
                break

        if not executable_path:
            raise RuntimeError(f"Could not find {tool_info['executable']} in extracted files")

        # Make executable if needed
        if sys.platform != "win32":
            current_permissions = os.stat(executable_path).st_mode
            os.chmod(executable_path, current_permissions | stat.S_IEXEC)

        # Add to PATH
        self._add_to_path(executable_path)

        logger.info(f"{tool_name} installed successfully")

    def update_tool(self, tool_name: str) -> None:
        """
        Update a specific tool to the latest version
        """
        if tool_name not in self.required_tools:
            raise ValueError(f"Unknown tool: {tool_name}")

        # Remove existing installation
        tool_info = self.required_tools[tool_name]
        tool_path = self.tools_dir / tool_info["executable"]
        if tool_path.exists():
            tool_path.unlink()

        # Install latest version
        self.install_tool(tool_name)

    def get_tool_version(self, tool_name: str) -> Optional[str]:
        """
        Get the version of an installed tool
        """
        if not self._is_tool_installed(tool_name):
            return None

        tool_info = self.required_tools[tool_name]
        try:
            result = subprocess.run(
                tool_info["version_cmd"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception as e:
            logger.debug(f"Failed to get version for {tool_name}: {str(e)}")
        return None

    def _get_platform(self) -> str:
        """
        Get the current platform in a format matching our tool configurations
        """
        system = platform.system().lower()
        if system == "windows":
            return "windows"
        elif system == "linux":
            return "linux"
        elif system == "darwin":
            return "darwin"
        else:
            raise ValueError(f"Unsupported operating system: {system}")

    def _download_file(self, url: str, output_path: Path) -> None:
        """
        Download a file with progress bar
        """
        response = requests.get(url, stream=True)
        total_size = int(response.headers.get('content-length', 0))
        
        with open(output_path, 'wb') as f, tqdm(
            desc=output_path.name,
            total=total_size,
            unit='iB',
            unit_scale=True,
            unit_divisor=1024,
        ) as bar:
            for data in response.iter_content(chunk_size=1024):
                size = f.write(data)
                bar.update(size)

    def _extract_zip(self, zip_path: Path, extract_to: Path) -> None:
        """
        Extract a zip file
        """
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_to)

    def _make_executable(self, path: Path) -> None:
        """
        Make a file executable
        """
        if not os.name == 'nt':  # Not Windows
            current_permissions = os.stat(path).st_mode
            os.chmod(path, current_permissions | stat.S_IEXEC)

    def _add_to_path(self, tool_path: Path) -> None:
        """
        Add tool directory to system PATH
        """
        tool_dir = str(tool_path.parent)
        if tool_dir not in os.environ['PATH']:
            path_separator = ';' if sys.platform == 'win32' else ':'
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