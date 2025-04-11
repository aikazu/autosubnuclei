"""
Security scanner implementation
"""

import logging
import subprocess
import shutil
from pathlib import Path
from typing import List, Optional, Set
import signal
import sys

from autosubnuclei.utils.tool_manager import ToolManager
from autosubnuclei.config.config_manager import ConfigManager
from autosubnuclei.utils.notifier import Notifier

logger = logging.getLogger(__name__)

class SecurityScanner:
    def __init__(self, domain: str, output_dir: Path, templates_path: Path):
        self.domain = domain
        self.output_dir = output_dir
        self.templates_path = templates_path
        self.tool_manager = ToolManager()
        self.config_manager = ConfigManager()
        self.notifier = Notifier(self.config_manager)
        self._setup_tools()
        self._setup_signal_handlers()

    def _setup_signal_handlers(self) -> None:
        """
        Setup signal handlers for graceful shutdown
        """
        signal.signal(signal.SIGINT, self._handle_interrupt)
        signal.signal(signal.SIGTERM, self._handle_interrupt)

    def _handle_interrupt(self, signum, frame) -> None:
        """
        Handle interrupt signals
        """
        logger.info("Received interrupt signal, cleaning up...")
        self.notifier.send_cancellation_notification(self.domain)
        sys.exit(1)

    def _setup_tools(self) -> None:
        """
        Setup and verify required tools
        """
        # Verify if tools are installed
        tool_status = self.tool_manager.verify_all_tools()
        
        # Only install missing tools
        missing_tools = [tool for tool, installed in tool_status.items() if not installed]
        if missing_tools:
            logger.info(f"Installing missing tools: {', '.join(missing_tools)}")
            for tool_name in missing_tools:
                self.tool_manager.install_tool(tool_name)

            # Verify installation again
            tool_status = self.tool_manager.verify_all_tools()
            if not all(tool_status.values()):
                still_missing = [tool for tool, installed in tool_status.items() if not installed]
                self.notifier.send_cancellation_notification(self.domain, f"Failed to install tools: {', '.join(still_missing)}")
                raise RuntimeError(f"Failed to install required tools: {', '.join(still_missing)}")
        else:
            logger.info("All required tools are already installed")

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
        self.notifier.send_subdomains_found(self.domain, list(subdomains))
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
        self.notifier.send_alive_subdomains(self.domain, list(alive_subdomains))
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
        self.notifier.send_scan_results(self.domain, results_file)

    def scan(self, severities: List[str], notify: bool = True) -> None:
        """
        Run the complete security scan pipeline
        """
        try:
            # Send start notification
            if notify and self.config_manager.is_notifications_enabled():
                self.notifier.send_scan_start(self.domain)

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
            
            # Send completion notification
            if notify and self.config_manager.is_notifications_enabled():
                self.notifier.send_scan_complete(self.domain)

        except Exception as e:
            logger.error(f"Error during scan: {str(e)}")
            raise 