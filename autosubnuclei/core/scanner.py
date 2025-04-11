"""
Security scanner implementation
"""

import logging
import subprocess
import shutil
from pathlib import Path
from typing import List, Optional, Set

from autosubnuclei.utils.tool_manager import ToolManager

logger = logging.getLogger(__name__)

class SecurityScanner:
    def __init__(self, domain: str, output_dir: Path, templates_path: Path):
        self.domain = domain
        self.output_dir = output_dir
        self.templates_path = templates_path
        self.tool_manager = ToolManager()
        self._setup_tools()

    def _setup_tools(self) -> None:
        """
        Setup and verify required tools
        """
        # Verify if tools are installed
        tool_status = self.tool_manager.verify_all_tools()
        
        # Install missing tools
        for tool_name, is_installed in tool_status.items():
            if not is_installed:
                logger.info(f"Installing {tool_name}...")
                self.tool_manager.install_tool(tool_name)

        # Verify installation again
        tool_status = self.tool_manager.verify_all_tools()
        if not all(tool_status.values()):
            missing_tools = [tool for tool, installed in tool_status.items() if not installed]
            raise RuntimeError(f"Failed to install required tools: {', '.join(missing_tools)}")

    def _run_subfinder(self) -> Set[str]:
        """
        Run subfinder to discover subdomains
        """
        subdomains_file = self.output_dir / "subdomains.txt"
        
        cmd = [
            "subfinder",
            "-d", self.domain,
            "-o", str(subdomains_file)
        ]

        logger.info(f"Running subfinder for {self.domain}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.error(f"Subfinder failed: {result.stderr}")
            raise RuntimeError(f"Subfinder failed: {result.stderr}")

        # Read discovered subdomains
        with open(subdomains_file, 'r') as f:
            subdomains = {line.strip() for line in f if line.strip()}

        logger.info(f"Found {len(subdomains)} subdomains")
        return subdomains

    def _run_httpx(self, subdomains: Set[str]) -> Set[str]:
        """
        Run httpx to find alive subdomains
        """
        alive_file = self.output_dir / "alive.txt"
        subdomains_file = self.output_dir / "subdomains.txt"
        
        # Write subdomains to temporary file
        with open(subdomains_file, 'w') as f:
            f.write('\n'.join(subdomains))

        cmd = [
            "httpx",
            "-l", str(subdomains_file),
            "-o", str(alive_file),
            "-silent"
        ]

        logger.info("Running httpx to find alive subdomains")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.error(f"httpx failed: {result.stderr}")
            raise RuntimeError(f"httpx failed: {result.stderr}")

        # Read alive subdomains
        with open(alive_file, 'r') as f:
            alive_subdomains = {line.strip() for line in f if line.strip()}

        logger.info(f"Found {len(alive_subdomains)} alive subdomains")
        return alive_subdomains

    def _run_nuclei(self, subdomains: Set[str], severities: List[str]) -> None:
        """
        Run nuclei scan on subdomains
        """
        results_file = self.output_dir / "results.txt"
        subdomains_file = self.output_dir / "alive.txt"
        
        # Write subdomains to temporary file
        with open(subdomains_file, 'w') as f:
            f.write('\n'.join(subdomains))

        cmd = [
            "nuclei",
            "-l", str(subdomains_file),
            "-t", str(self.templates_path),
            "-severity", ",".join(severities),
            "-o", str(results_file)
        ]

        logger.info("Running nuclei scan")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.error(f"Nuclei scan failed: {result.stderr}")
            raise RuntimeError(f"Nuclei scan failed: {result.stderr}")

        logger.info("Nuclei scan completed successfully")

    def scan(self, severities: List[str], notify: bool = True) -> None:
        """
        Run the complete security scan pipeline
        """
        try:
            # Step 1: Discover subdomains
            subdomains = self._run_subfinder()
            
            if not subdomains:
                logger.warning("No subdomains found")
                return

            # Step 2: Find alive subdomains
            alive_subdomains = self._run_httpx(subdomains)
            
            if not alive_subdomains:
                logger.warning("No alive subdomains found")
                return

            # Step 3: Run nuclei scan
            self._run_nuclei(alive_subdomains, severities)
            
            if notify:
                self._send_notification()

        except Exception as e:
            logger.error(f"Error during scan: {str(e)}")
            raise

    def _send_notification(self) -> None:
        """
        Send notification about scan completion
        """
        # TODO: Implement notification system
        logger.info("Notification would be sent here") 