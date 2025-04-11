"""
Security scanner implementation
"""

import logging
import subprocess
import shutil
import os
import sys
import re
from pathlib import Path
from typing import List, Optional, Set
import signal

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

    def _strip_ansi_codes(self, text: str) -> str:
        """
        Strip ANSI color codes from text
        """
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        return ansi_escape.sub('', text)

    def _run_command(self, command: List[str], shell: bool = False) -> subprocess.CompletedProcess:
        """
        Run a command with proper environment setup
        """
        try:
            return subprocess.run(
                command,
                capture_output=True,
                text=True,
                shell=shell,
                check=True
            )
        except subprocess.CalledProcessError as e:
            logger.error(f"Command failed: {e.stderr}")
            raise

    def _run_subfinder(self) -> Set[str]:
        """
        Run subfinder to discover subdomains
        """
        logger.info(f"Running subfinder for {self.domain}")
        result = self._run_command(["subfinder", "-d", self.domain, "-silent"])
        subdomains = set(result.stdout.strip().split('\n'))
        logger.info(f"Found {len(subdomains)} subdomains")
        self.notifier.send_subdomains_found(self.domain, list(subdomains))
        return subdomains

    def _run_httpx(self, subdomains: Set[str]) -> Set[str]:
        """
        Run httpx to find alive subdomains
        """
        logger.info("Running httpx to find alive subdomains")
        # Write subdomains to temporary file
        temp_file = self.output_dir / "subdomains.txt"
        with open(temp_file, 'w') as f:
            f.write('\n'.join(subdomains))
        
        result = self._run_command([
            "httpx",
            "-l", str(temp_file),
            "-silent",
            "-status-code",
            "-title",
            "-tech-detect"
        ])
        
        # Clean up temp file
        temp_file.unlink()
        
        # Strip ANSI codes from output
        clean_output = self._strip_ansi_codes(result.stdout)
        alive_subdomains = set(clean_output.strip().split('\n'))
        
        logger.info(f"Found {len(alive_subdomains)} alive subdomains")
        self.notifier.send_alive_subdomains(self.domain, list(alive_subdomains))
        return alive_subdomains

    def _run_nuclei(self, alive_subdomains: Set[str]) -> None:
        """
        Run nuclei scan on alive subdomains
        """
        logger.info("Running nuclei scan")
        # Write alive subdomains to temporary file
        temp_file = self.output_dir / "alive.txt"
        with open(temp_file, 'w') as f:
            f.write('\n'.join(alive_subdomains))
        
        result = self._run_command([
            "nuclei",
            "-l", str(temp_file),
            "-t", str(self.templates_path),
            "-severity", "critical,high,medium,low",
            "-o", str(self.output_dir / "results.txt")
        ])
        
        # Clean up temp file
        temp_file.unlink()

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
            self._run_nuclei(alive_subdomains)
            
            # Send completion notification
            if notify and self.config_manager.is_notifications_enabled():
                self.notifier.send_scan_complete(self.domain)

        except Exception as e:
            logger.error(f"Error during scan: {str(e)}")
            raise 