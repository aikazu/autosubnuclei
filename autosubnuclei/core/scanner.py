"""
Security scanner implementation with async support and optimized performance.
"""

import asyncio
import logging
import subprocess
import re
import time
import os
import sys
import signal
from pathlib import Path
from typing import List, Optional, Set, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
import tempfile
import hashlib
import json
import shutil

from autosubnuclei.utils.tool_manager import ToolManager
from autosubnuclei.config.config_manager import ConfigManager
from autosubnuclei.utils.notifier import Notifier
from autosubnuclei.utils.helpers import create_requests_session, download_file

logger = logging.getLogger(__name__)

class SecurityScanner:
    def __init__(self, domain: str, output_dir: Path, templates_path: Path):
        self.domain = domain
        self.output_dir = output_dir
        self.templates_path = templates_path.resolve()  # Ensure absolute path
        self.tool_manager = ToolManager()
        self.config_manager = ConfigManager()
        self.notifier = Notifier(self.config_manager)
        
        # Create cache directory
        self.cache_dir = self.output_dir / ".cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Store scan state
        self.scan_state = {
            "start_time": time.time(),
            "status": "initializing",
            "subdomains": 0,
            "alive_subdomains": 0,
            "vulnerabilities": 0
        }
        
        # Max concurrent tasks
        self.max_workers = os.cpu_count() or 4
        
        self._setup_tools()
        self._setup_signal_handlers()
        self._ensure_templates_exist()

    def _setup_signal_handlers(self) -> None:
        """
        Setup signal handlers for graceful shutdown
        """
        signal.signal(signal.SIGINT, self._handle_interrupt)
        signal.signal(signal.SIGTERM, self._handle_interrupt)

    def _handle_interrupt(self, signum, frame) -> None:
        """
        Handle interrupt signals with proper cleanup
        """
        logger.info("Received interrupt signal, cleaning up...")
        self.scan_state["status"] = "cancelled"
        self.notifier.send_cancellation_notification(self.domain)
        
        # Save scan state before exiting
        self._save_scan_state()
        sys.exit(1)

    def _save_scan_state(self) -> None:
        """
        Save current scan state to a JSON file
        """
        state_file = self.output_dir / "scan_state.json"
        self.scan_state["duration"] = time.time() - self.scan_state["start_time"]
        
        with open(state_file, 'w') as f:
            json.dump(self.scan_state, f, indent=2)

    def _ensure_templates_exist(self) -> None:
        """
        Ensure nuclei templates exist, download if not
        """
        if not self.templates_path.exists():
            logger.info(f"Nuclei templates not found at {self.templates_path}. Downloading...")
            self.scan_state["status"] = "downloading_templates"
            
            # Create the parent directory if it doesn't exist
            self.templates_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Always download templates to the specified templates_path
            self._download_nuclei_templates()
                
            if not self.templates_path.exists():
                raise FileNotFoundError(f"Failed to create or download templates to {self.templates_path}")
            
            logger.info(f"Successfully set up templates at {self.templates_path}")

    def _download_nuclei_templates(self) -> None:
        """
        Download nuclei templates from the official repository
        """
        try:
            logger.info("Downloading nuclei templates...")
            # Use our manual download method to ensure templates go to our specified location
            self._manual_download_templates()
        except Exception as e:
            logger.error(f"Failed to download templates: {str(e)}")
            raise

    def _manual_download_templates(self) -> None:
        """
        Manually download and extract nuclei templates from GitHub to the specified path
        """
        try:
            logger.info(f"Manually downloading nuclei templates from GitHub to {self.templates_path}...")
            
            # GitHub repository URL for nuclei-templates
            repo_url = "https://github.com/projectdiscovery/nuclei-templates/archive/refs/heads/master.zip"
            
            # Try to get the latest commit hash
            commit_hash = None
            try:
                import requests
                response = requests.get("https://api.github.com/repos/projectdiscovery/nuclei-templates/commits/master")
                if response.status_code == 200:
                    commit_hash = response.json()["sha"]
                    logger.info(f"Latest templates commit: {commit_hash[:7]}")
            except Exception as e:
                logger.warning(f"Could not get latest commit info: {str(e)}")
            
            # Create a temporary file to download the templates
            temp_path = None
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as temp_file:
                    temp_path = temp_file.name
                
                # Download the templates zip file - ensure temp_path is a Path object
                session = create_requests_session()
                download_file(repo_url, Path(temp_path))
                
                # Extract to a temporary directory
                import zipfile
                with tempfile.TemporaryDirectory() as temp_dir:
                    with zipfile.ZipFile(temp_path, 'r') as zip_ref:
                        zip_ref.extractall(temp_dir)
                    
                    # Move the extracted content to the templates path
                    extracted_dir = Path(temp_dir) / "nuclei-templates-master"
                    if extracted_dir.exists():
                        # Create parent directory if it doesn't exist
                        self.templates_path.parent.mkdir(parents=True, exist_ok=True)
                        
                        # If templates_path already exists as a file, remove it
                        if self.templates_path.is_file():
                            self.templates_path.unlink()
                        
                        # Copy the extracted directory to the templates path
                        if self.templates_path.exists():
                            shutil.rmtree(self.templates_path)
                        
                        # Copy with a more detailed progress message
                        logger.info(f"Copying template files to {self.templates_path}...")
                        shutil.copytree(extracted_dir, self.templates_path)
                        
                        # Save version information if available
                        if commit_hash:
                            version_file = self.templates_path / ".version"
                            try:
                                with open(version_file, "w") as f:
                                    f.write(commit_hash)
                                logger.info(f"Saved template version info: {commit_hash[:7]}")
                            except Exception as e:
                                logger.warning(f"Could not save version info: {str(e)}")
                        
                        logger.info(f"Templates successfully downloaded to {self.templates_path}")
                    else:
                        raise FileNotFoundError("Failed to extract nuclei templates")
            finally:
                # Remove the temporary zip file
                if temp_path and os.path.exists(temp_path):
                    os.unlink(temp_path)
                
        except Exception as e:
            logger.error(f"Failed to manually download templates: {str(e)}")
            raise

    def _setup_tools(self) -> None:
        """
        Setup and verify required tools with improved error handling
        """
        try:
            # Verify if tools are installed
            tool_status = self.tool_manager.verify_all_tools()
            
            # Only install missing tools
            missing_tools = [tool for tool, installed in tool_status.items() if not installed]
            if missing_tools:
                logger.info(f"Installing missing tools: {', '.join(missing_tools)}")
                
                # Install tools concurrently
                with ThreadPoolExecutor(max_workers=min(len(missing_tools), self.max_workers)) as executor:
                    futures = {executor.submit(self.tool_manager.install_tool, tool): tool for tool in missing_tools}
                    
                    for future in as_completed(futures):
                        tool = futures[future]
                        try:
                            future.result()
                            logger.info(f"Successfully installed {tool}")
                        except Exception as e:
                            logger.error(f"Failed to install {tool}: {str(e)}")

                # Verify installation again
                tool_status = self.tool_manager.verify_all_tools()
                if not all(tool_status.values()):
                    still_missing = [tool for tool, installed in tool_status.items() if not installed]
                    self.notifier.send_cancellation_notification(self.domain, f"Failed to install tools: {', '.join(still_missing)}")
                    raise RuntimeError(f"Failed to install required tools: {', '.join(still_missing)}")
            else:
                logger.info("All required tools are already installed")
        except Exception as e:
            logger.error(f"Tool setup error: {str(e)}")
            raise

    def _strip_ansi_codes(self, text: str) -> str:
        """
        Strip ANSI color codes from text output
        """
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        return ansi_escape.sub('', text)

    async def _run_command_async(self, command: List[str], shell: bool = False) -> subprocess.CompletedProcess:
        """
        Run a command asynchronously for better performance
        """
        logger.debug(f"Running command: {' '.join(command)}")
        
        try:
            # Run the command in a separate thread to not block the event loop
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(
                None,
                lambda: subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    shell=shell,
                    check=True
                )
            )
        except subprocess.CalledProcessError as e:
            logger.error(f"Command failed: {' '.join(command)}")
            logger.error(f"Error output: {e.stderr}")
            raise

    def _get_cache_key(self, command: List[str]) -> str:
        """
        Generate a cache key based on command and its arguments
        """
        command_str = " ".join(command)
        return hashlib.md5(command_str.encode()).hexdigest()

    def _get_cached_result(self, cache_key: str) -> Optional[str]:
        """
        Get cached result if available and not expired
        """
        cache_file = self.cache_dir / f"{cache_key}.json"
        
        if cache_file.exists():
            try:
                with open(cache_file, 'r') as f:
                    cache_data = json.load(f)
                
                # Check if cache is still valid (24 hours expiry)
                if time.time() - cache_data.get("timestamp", 0) < 86400:
                    logger.debug(f"Using cached result for {cache_key}")
                    return cache_data.get("result")
            except Exception as e:
                logger.warning(f"Failed to read cache: {str(e)}")
        
        return None

    def _save_to_cache(self, cache_key: str, result: str) -> None:
        """
        Save result to cache
        """
        cache_file = self.cache_dir / f"{cache_key}.json"
        
        try:
            with open(cache_file, 'w') as f:
                json.dump({
                    "timestamp": time.time(),
                    "result": result
                }, f)
        except Exception as e:
            logger.warning(f"Failed to save to cache: {str(e)}")

    async def _run_subfinder(self) -> Set[str]:
        """
        Run subfinder to discover subdomains with caching support
        """
        logger.info(f"Running subfinder for {self.domain}")
        self.scan_state["status"] = "discovering_subdomains"
        
        command = ["subfinder", "-d", self.domain, "-silent"]
        cache_key = self._get_cache_key(command)
        
        # Try to get from cache first
        cached_result = self._get_cached_result(cache_key)
        if cached_result:
            subdomains = set(cached_result.strip().split('\n'))
            if subdomains:
                logger.info(f"Found {len(subdomains)} subdomains from cache")
                self.scan_state["subdomains"] = len(subdomains)
                self.notifier.send_subdomains_found(self.domain, list(subdomains))
                return subdomains
        
        # Run the actual command
        result = await self._run_command_async(command)
        subdomains = set(result.stdout.strip().split('\n'))
        if '' in subdomains:
            subdomains.remove('')
            
        logger.info(f"Found {len(subdomains)} subdomains")
        self.scan_state["subdomains"] = len(subdomains)
        self.notifier.send_subdomains_found(self.domain, list(subdomains))
        
        # Save to cache
        self._save_to_cache(cache_key, result.stdout)
        
        return subdomains

    async def _run_httpx_batch(self, subdomains_batch: List[str]) -> Set[str]:
        """
        Run httpx on a batch of subdomains
        """
        # Write subdomains to temporary file
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as temp:
            temp.write('\n'.join(subdomains_batch))
            temp_path = temp.name
        
        try:
            command = [
                "httpx",
                "-l", temp_path,
                "-silent",
                "-status-code",
                "-title",
                "-tech-detect"
            ]
            
            result = await self._run_command_async(command)
            
            # Strip ANSI codes from output
            clean_output = self._strip_ansi_codes(result.stdout)
            batch_alive = set(line for line in clean_output.strip().split('\n') if line)
            
            return batch_alive
        finally:
            # Clean up temp file
            os.unlink(temp_path)

    async def _run_httpx(self, subdomains: Set[str]) -> Set[str]:
        """
        Run httpx to find alive subdomains with concurrent batching
        """
        logger.info("Running httpx to find alive subdomains")
        self.scan_state["status"] = "probing_subdomains"
        
        # Split subdomains into batches for concurrent processing
        batch_size = max(10, len(subdomains) // self.max_workers)
        subdomains_list = list(subdomains)
        batches = [subdomains_list[i:i + batch_size] 
                  for i in range(0, len(subdomains_list), batch_size)]
        
        # Process batches concurrently
        tasks = [self._run_httpx_batch(batch) for batch in batches]
        batch_results = await asyncio.gather(*tasks)
        
        # Combine results
        alive_subdomains = set()
        for result in batch_results:
            alive_subdomains.update(result)
        
        logger.info(f"Found {len(alive_subdomains)} alive subdomains")
        self.scan_state["alive_subdomains"] = len(alive_subdomains)
        self.notifier.send_alive_subdomains(self.domain, list(alive_subdomains))
        
        return alive_subdomains

    async def _run_nuclei_batch(self, subdomains_batch: List[str], severities: List[str], template_batch: List[str]) -> Dict[str, Any]:
        """
        Run nuclei scan on a batch of subdomains with specific templates
        """
        # Write subdomains to temporary file
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as temp:
            temp.write('\n'.join(subdomains_batch))
            temp_path = temp.name
        
        # Create output file
        output_file = self.output_dir / f"results_{hashlib.md5(''.join(subdomains_batch).encode()).hexdigest()[:8]}.txt"
        
        try:
            command = [
                "nuclei",
                "-l", temp_path,
                "-t", ",".join(template_batch) if template_batch else str(self.templates_path),
                "-severity", ",".join(severities),
                "-o", str(output_file),
                "-silent"
            ]
            
            # Add additional nuclei optimization flags
            command.extend(["-c", str(self.max_workers)])
            
            await self._run_command_async(command)
            
            # Count vulnerabilities from the output file
            vuln_count = 0
            if output_file.exists():
                with open(output_file, 'r') as f:
                    vuln_count = sum(1 for _ in f)
            
            return {
                "output_file": output_file,
                "vulnerabilities": vuln_count
            }
        except Exception as e:
            logger.error(f"Error in nuclei batch: {str(e)}")
            return {
                "output_file": output_file,
                "vulnerabilities": 0,
                "error": str(e)
            }
        finally:
            # Clean up temp file
            os.unlink(temp_path)

    async def _run_nuclei(self, alive_subdomains: Set[str], severities: List[str]) -> None:
        """
        Run nuclei scan on alive subdomains with parallel batches
        """
        logger.info("Running nuclei scan")
        self.scan_state["status"] = "scanning_vulnerabilities"
        
        # Verify templates exist before running
        if not self.templates_path.exists():
            logger.error(f"Nuclei templates not found at {self.templates_path}")
            raise FileNotFoundError(f"Templates directory not found: {self.templates_path}")
        
        # Split subdomains into batches for concurrent processing
        subdomains_list = list(alive_subdomains)
        batch_size = max(5, len(subdomains_list) // self.max_workers)
        subdomain_batches = [subdomains_list[i:i + batch_size] 
                          for i in range(0, len(subdomains_list), batch_size)]
        
        # Process batches concurrently
        tasks = []
        for batch in subdomain_batches:
            # Run each batch with all templates
            tasks.append(self._run_nuclei_batch(batch, severities, []))
        
        batch_results = await asyncio.gather(*tasks)
        
        # Combine results into a single output file
        final_output = self.output_dir / "results.txt"
        total_vulns = 0
        
        with open(final_output, 'w') as outfile:
            for result in batch_results:
                output_file = result.get("output_file")
                if output_file and output_file.exists():
                    with open(output_file, 'r') as infile:
                        outfile.write(infile.read())
                    # Add to total vulnerabilities
                    total_vulns += result.get("vulnerabilities", 0)
                    # Clean up individual output files
                    output_file.unlink()
        
        logger.info(f"Found {total_vulns} potential vulnerabilities")
        self.scan_state["vulnerabilities"] = total_vulns

    async def scan(self, severities: List[str], notify: bool = True) -> None:
        """
        Run the complete security scan pipeline asynchronously
        """
        try:
            self.scan_state["start_time"] = time.time()
            
            # Send start notification
            if notify and self.config_manager.is_notifications_enabled():
                self.notifier.send_scan_start(self.domain)

            # Step 1: Discover subdomains
            subdomains = await self._run_subfinder()
            
            if not subdomains:
                logger.warning("No subdomains found")
                self.scan_state["status"] = "completed"
                self._save_scan_state()
                return

            # Step 2: Find alive subdomains
            alive_subdomains = await self._run_httpx(subdomains)
            
            if not alive_subdomains:
                logger.warning("No alive subdomains found")
                self.scan_state["status"] = "completed"
                self._save_scan_state()
                return

            # Step 3: Run nuclei scan
            await self._run_nuclei(alive_subdomains, severities)
            
            # Set completion status and save state
            self.scan_state["status"] = "completed"
            self.scan_state["duration"] = time.time() - self.scan_state["start_time"]
            self._save_scan_state()
            
            # Send completion notification
            if notify and self.config_manager.is_notifications_enabled():
                self.notifier.send_scan_complete(self.domain)

        except Exception as e:
            logger.error(f"Error during scan: {str(e)}")
            self.scan_state["status"] = "error"
            self.scan_state["error"] = str(e)
            self._save_scan_state()
            raise 