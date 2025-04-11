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
    def __init__(self, tools_dir: Optional[Path] = None):
        self.tools_dir = tools_dir or Path("tools")
        self.tools_dir.mkdir(parents=True, exist_ok=True)
        
        # Tool configurations in order of installation
        self.tools = {
            "subfinder": {
                "windows": {
                    "url": "https://github.com/projectdiscovery/subfinder/releases/download/v2.6.3/subfinder_2.6.3_windows_amd64.zip",
                    "executable": "subfinder.exe",
                    "version_cmd": ["subfinder", "-version"]
                },
                "linux": {
                    "url": "https://github.com/projectdiscovery/subfinder/releases/download/v2.6.3/subfinder_2.6.3_linux_amd64.zip",
                    "executable": "subfinder",
                    "version_cmd": ["subfinder", "-version"]
                },
                "darwin": {
                    "url": "https://github.com/projectdiscovery/subfinder/releases/download/v2.6.3/subfinder_2.6.3_darwin_amd64.zip",
                    "executable": "subfinder",
                    "version_cmd": ["subfinder", "-version"]
                }
            },
            "httpx": {
                "windows": {
                    "url": "https://github.com/projectdiscovery/httpx/releases/download/v1.3.7/httpx_1.3.7_windows_amd64.zip",
                    "executable": "httpx.exe",
                    "version_cmd": ["httpx", "-version"]
                },
                "linux": {
                    "url": "https://github.com/projectdiscovery/httpx/releases/download/v1.3.7/httpx_1.3.7_linux_amd64.zip",
                    "executable": "httpx",
                    "version_cmd": ["httpx", "-version"]
                },
                "darwin": {
                    "url": "https://github.com/projectdiscovery/httpx/releases/download/v1.3.7/httpx_1.3.7_darwin_amd64.zip",
                    "executable": "httpx",
                    "version_cmd": ["httpx", "-version"]
                }
            },
            "nuclei": {
                "windows": {
                    "url": "https://github.com/projectdiscovery/nuclei/releases/download/v2.9.7/nuclei_2.9.7_windows_amd64.zip",
                    "executable": "nuclei.exe",
                    "version_cmd": ["nuclei", "-version"]
                },
                "linux": {
                    "url": "https://github.com/projectdiscovery/nuclei/releases/download/v2.9.7/nuclei_2.9.7_linux_amd64.zip",
                    "executable": "nuclei",
                    "version_cmd": ["nuclei", "-version"]
                },
                "darwin": {
                    "url": "https://github.com/projectdiscovery/nuclei/releases/download/v2.9.7/nuclei_2.9.7_darwin_amd64.zip",
                    "executable": "nuclei",
                    "version_cmd": ["nuclei", "-version"]
                }
            }
        }

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
            os.environ['PATH'] = f"{tool_dir};{os.environ['PATH']}"

    def install_tool(self, tool_name: str) -> None:
        """
        Install a specific tool
        """
        if tool_name not in self.tools:
            raise ValueError(f"Unknown tool: {tool_name}")

        current_platform = self._get_platform()
        tool_config = self.tools[tool_name]
        platform_config = tool_config.get(current_platform)
        
        if not platform_config:
            raise ValueError(f"Tool {tool_name} not supported on {current_platform}")

        tool_dir = self.tools_dir / tool_name
        tool_dir.mkdir(exist_ok=True)

        # Download the tool
        zip_path = tool_dir / f"{tool_name}.zip"
        logger.info(f"Downloading {tool_name} for {current_platform}...")
        self._download_file(platform_config["url"], zip_path)

        # Extract the tool
        logger.info(f"Extracting {tool_name}...")
        self._extract_zip(zip_path, tool_dir)

        # Find the executable in the extracted files
        executable_path = None
        for root, _, files in os.walk(tool_dir):
            for file in files:
                if file == platform_config["executable"]:
                    executable_path = Path(root) / file
                    break
            if executable_path:
                break

        if not executable_path:
            raise FileNotFoundError(f"Could not find {platform_config['executable']} in extracted files")

        # Make executable if needed
        self._make_executable(executable_path)

        # Add to PATH
        self._add_to_path(executable_path)

        # Clean up zip file
        zip_path.unlink()

        logger.info(f"{tool_name} installed successfully at {executable_path}")

    def install_all_tools(self) -> None:
        """
        Install all required tools in the correct order
        """
        # Install tools in the order they are defined in self.tools
        for tool_name in self.tools:
            try:
                self.install_tool(tool_name)
            except Exception as e:
                logger.error(f"Failed to install {tool_name}: {str(e)}")
                raise

    def verify_tool_installation(self, tool_name: str) -> bool:
        """
        Verify if a tool is properly installed
        """
        if tool_name not in self.tools:
            return False

        current_platform = self._get_platform()
        tool_config = self.tools[tool_name]
        platform_config = tool_config.get(current_platform)
        
        if not platform_config:
            return False

        try:
            # First check if the executable exists in our tools directory
            tool_dir = self.tools_dir / tool_name
            executable_path = None
            for root, _, files in os.walk(tool_dir):
                for file in files:
                    if file == platform_config["executable"]:
                        executable_path = Path(root) / file
                        break
                if executable_path:
                    break

            if not executable_path:
                return False

            # Then try to run the version command
            result = subprocess.run(
                platform_config["version_cmd"],
                capture_output=True,
                text=True,
                shell=True if current_platform == "windows" else False
            )
            return result.returncode == 0
        except Exception as e:
            logger.debug(f"Verification failed: {str(e)}")
            return False

    def verify_all_tools(self) -> Dict[str, bool]:
        """
        Verify installation of all tools
        """
        return {
            tool_name: self.verify_tool_installation(tool_name)
            for tool_name in self.tools
        } 