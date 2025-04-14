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
from typing import List, Optional, Set, Dict, Any, TYPE_CHECKING, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import tempfile
import hashlib
import json
import shutil
from datetime import datetime

from autosubnuclei.utils.tool_manager import ToolManager
from autosubnuclei.config.config_manager import ConfigManager
from autosubnuclei.utils.notifier import Notifier
from autosubnuclei.utils.helpers import create_requests_session, download_file
from .template_manager import TemplateManager

if TYPE_CHECKING:
    from autosubnuclei.cli import ProgressMonitor # Or wherever it's defined

logger = logging.getLogger(__name__)

class SecurityScanner:
    def __init__(self, domain: str, output_dir: Path, templates_path: Path,
                 use_cache: bool = True, # Add cache flag
                 progress_monitor: Optional['ProgressMonitor'] = None):
        # Purpose: Initialize the SecurityScanner with target, paths, and config.
        # Usage: scanner = SecurityScanner("example.com", Path("./output"), Path("./templates"))
        self.domain = domain
        self.output_dir = output_dir
        self.templates_path = templates_path.resolve()  # Ensure absolute path
        self.tool_manager = ToolManager()
        self.config_manager = ConfigManager()
        self.notifier = Notifier(self.config_manager)
        self.use_cache = use_cache
        self.progress_monitor = progress_monitor # Store the progress monitor
        # Instantiate TemplateManager
        self.template_manager = TemplateManager(self.templates_path)
        
        # Get system information from tool manager
        self.system, self.arch = self.tool_manager.system, self.tool_manager.arch
        
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
        self.template_manager.ensure_templates_exist()

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

    def _setup_tools(self) -> None:
        """
        Setup and verify required tools with improved error handling and feedback
        """
        try:
            print("[INFO] Verifying required tools (Subfinder, httpx, Nuclei)...")
            # Verify if tools are installed
            tool_status = self.tool_manager.verify_all_tools()
            
            # Only install missing tools
            missing_tools = [tool for tool, installed in tool_status.items() if not installed]
            if missing_tools:
                print(f"[WARN] Missing tools detected: {', '.join(missing_tools)}.")
                # Optionally add confirmation here if needed, or proceed directly
                print(f"[INFO] Attempting to install missing tools...")
                logger.info(f"Installing missing tools: {', '.join(missing_tools)}")
                self.scan_state["status"] = "setting_up_tools" # Update status
                
                installed_tools = []
                failed_tools = []
                # Install tools concurrently
                with ThreadPoolExecutor(max_workers=min(len(missing_tools), self.max_workers)) as executor:
                    futures = {executor.submit(self.tool_manager.install_tool, tool): tool for tool in missing_tools}
                    
                    for future in as_completed(futures):
                        tool = futures[future]
                        try:
                            future.result() # Wait for install to complete
                            print(f"[SUCCESS] Successfully installed {tool}.")
                            logger.info(f"Successfully installed {tool}")
                            installed_tools.append(tool)
                        except Exception as e:
                            print(f"[ERROR] Failed to install {tool}: {str(e)}")
                            logger.error(f"Failed to install {tool}: {str(e)}", exc_info=True)
                            failed_tools.append(tool)

                # Verify installation again
                tool_status = self.tool_manager.verify_all_tools()
                if not all(tool_status.values()):
                    still_missing = [tool for tool, installed in tool_status.items() if not installed]
                    error_msg = f"Failed to install required tools: {', '.join(still_missing)}"
                    print(f"[ERROR] {error_msg}")
                    self.notifier.send_cancellation_notification(self.domain, error_msg)
                    raise RuntimeError(error_msg)
                else:
                    print("[SUCCESS] All required tools are now installed.")
            else:
                print("[INFO] All required tools are already installed.")
                logger.info("All required tools are already installed")
        except Exception as e:
            print(f"[ERROR] Tool setup failed: {str(e)}")
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
        if not self.use_cache:
            return None # Skip cache check if disabled

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
        if not self.use_cache:
             return # Don't save if caching is disabled

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
        # Purpose: Execute the subfinder tool to discover subdomains for the target domain.
        # Usage: subdomains = await self._run_subfinder()
        """
        Run subfinder to discover subdomains with caching support
        """
        logger.info(f"Running subfinder for {self.domain}")
        self.scan_state["status"] = "discovering_subdomains"
        
        command = [self.tool_manager.get_tool_path("subfinder"), "-d", self.domain, "-silent"]
        cache_key = self._get_cache_key(command)
        
        # Try to get from cache first
        cached_result = self._get_cached_result(cache_key)
        if cached_result:
            # Notify progress monitor about cache usage
            if self.progress_monitor:
                self.progress_monitor.set_using_cache("subfinder")

            subdomains = set(cached_result.strip().split('\n'))
            if '' in subdomains:
                subdomains.remove('')
            
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
        # Purpose: Execute httpx to probe discovered subdomains and identify live HTTP/S services.
        # Usage: alive_subdomains = await self._run_httpx(subdomains)
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

    def _build_nuclei_command(self, input_list_path: str, output_file_path: Path, severities: List[str]) -> List[str]:
        # Purpose: Construct the command-line arguments for running Nuclei.
        # Usage: command_args = self._build_nuclei_command("input.txt", Path("out.txt"), ["high"])
        nuclei_path = self.tool_manager.get_tool_path("nuclei")
        if not nuclei_path:
            logger.warning("Nuclei binary not found in tools directory, trying PATH...")
            nuclei_path_str = "nuclei" # Fallback to PATH
        else:
            nuclei_path_str = str(nuclei_path.absolute())

        command = [
            nuclei_path_str,
            "-l", input_list_path,
            "-t", str(self.templates_path), # Use resolved templates path
            "-severity", ",".join(severities),
            "-stats", # Include stats for better logging potentially
            "-o", str(output_file_path),
            "-no-color", # Standardize output
            "-exclude-tags", "fuzz" # Exclude fuzzing templates by default
            # Add other standard flags as needed, e.g., -timeout, -retries
        ]
        logger.debug(f"Built Nuclei command: {' '.join(command)}")
        return command

    async def _execute_nuclei_process(self, command: List[str]) -> None:
        # Purpose: Execute the constructed Nuclei command with appropriate async/sync handling.
        # Usage: await self._execute_nuclei_process(nuclei_command_args)
        logger.info(f"Executing Nuclei batch: {' '.join(command)}")
        start_time = time.time()
        timeout_seconds = 300 # 5 minutes timeout

        try:
            if self.system == "windows":
                # Use subprocess.run in executor for Windows compatibility
                loop = asyncio.get_running_loop()
                process = await loop.run_in_executor(
                    None,
                    lambda: subprocess.run(
                        command,
                        capture_output=True,
                        text=True,
                        timeout=timeout_seconds,
                        check=False, # Don't raise exception on non-zero exit
                        creationflags=subprocess.CREATE_NO_WINDOW
                    )
                )
                stdout = process.stdout
                stderr = process.stderr
                returncode = process.returncode
            else:
                # Use asyncio.create_subprocess_exec for non-Windows
                process = await asyncio.create_subprocess_exec(
                    *command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    limit=1024*1024 # 1MB buffer limit
                )
                try:
                    stdout_bytes, stderr_bytes = await asyncio.wait_for(process.communicate(), timeout=timeout_seconds)
                    stdout = stdout_bytes.decode(errors='ignore') if stdout_bytes else ""
                    stderr = stderr_bytes.decode(errors='ignore') if stderr_bytes else ""
                    returncode = process.returncode
                except asyncio.TimeoutError:
                    process.kill()
                    await process.wait() # Ensure process is cleaned up
                    logger.warning(f"Nuclei process timed out after {timeout_seconds} seconds and was killed.")
                    raise TimeoutError(f"Nuclei scan batch timed out after {timeout_seconds}s") # Raise specific error

            # Log results
            duration = time.time() - start_time
            logger.debug(f"Nuclei batch finished in {duration:.2f}s with exit code {returncode}")
            if stdout:
                logger.debug(f"Nuclei stdout:\n{stdout[-1000:]}") # Log last 1000 chars
            if returncode != 0:
                logger.warning(f"Nuclei exited with code {returncode}. Stderr:\n{stderr[-1000:]}")
            # Allow non-zero exit codes, process results regardless

        except FileNotFoundError:
            logger.error(f"Nuclei command failed: Executable not found at '{command[0]}' or in PATH.")
            raise RuntimeError("Nuclei executable not found. Ensure it is installed and accessible.")
        except Exception as e:
            logger.error(f"Exception running nuclei process: {e}", exc_info=True)
            raise RuntimeError(f"Failed to execute Nuclei batch: {e}")

    def _process_nuclei_output(self, output_file: Path, severities: List[str]) -> Dict[str, Any]:
        # Purpose: Read a Nuclei output file and count vulnerabilities by severity.
        # Usage: results = self._process_nuclei_output(Path("results.txt"), ["high"])
        vuln_count = 0
        vulnerabilities = []
        if output_file.exists() and output_file.stat().st_size > 0:
            logger.debug(f"Processing Nuclei output file: {output_file}")
            try:
                with open(output_file, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        line_strip = line.strip()
                        if not line_strip:
                            continue
                        # Simple check for severity tags - adjust if Nuclei format changes
                        if any(f"[{sev}]" in line_strip.lower() for sev in severities):
                            vuln_count += 1
                            vulnerabilities.append(line_strip)
            except Exception as e:
                 logger.error(f"Error reading Nuclei output file {output_file}: {e}", exc_info=True)
                 # Return partial results if reading failed mid-way
        else:
            logger.debug(f"Nuclei output file not found or empty: {output_file}")

        return {
            "output_file": output_file,
            "vulnerabilities": vuln_count,
            "vulnerability_data": vulnerabilities
        }

    async def _run_nuclei_batch(self, subdomains_batch: List[str], severities: List[str]) -> Dict[str, Any]:
        # Purpose: Run a single batch of nuclei scanning against a list of subdomains.
        # Usage: results = await self._run_nuclei_batch(["sub1.example.com"], ["high"])
        """
        Run nuclei scan on a batch of subdomains.
        Refactored for clarity and reduced complexity.
        """
        output_file = None # Initialize output_file
        temp_path = None
        try:
            # Write subdomains to temporary file
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as temp:
                temp.write('\n'.join(subdomains_batch))
                temp_path = temp.name

            # Create unique output file path for this batch
            batch_hash = hashlib.md5(''.join(subdomains_batch).encode()).hexdigest()[:8]
            output_file = self.output_dir / f"results_{batch_hash}.jsonl" # Use jsonl for easier parsing?

            # 1. Build command
            command = self._build_nuclei_command(temp_path, output_file, severities)

            # 2. Execute command
            await self._execute_nuclei_process(command)

            # 3. Process results
            return self._process_nuclei_output(output_file, severities)

        except Exception as e:
            logger.error(f"Error in nuclei batch execution or processing: {e}", exc_info=True)
            # Ensure output_file path is returned even on error for potential cleanup
            return {
                "output_file": output_file if output_file else Path("error.txt"), # Provide dummy if None
                "vulnerabilities": 0,
                "vulnerability_data": [],
                "error": str(e)
            }
        finally:
            # Clean up temp input file
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except OSError as e:
                    logger.warning(f"Could not remove temporary nuclei input file {temp_path}: {e}")

    def _combine_nuclei_batch_results(self, batch_results: List[Dict[str, Any]]) -> Tuple[int, Dict[str, int]]:
        # Purpose: Combine results from multiple Nuclei batches into a single file and count severities.
        # Usage: total_vulns, severity_counts = self._combine_nuclei_batch_results(list_of_batch_result_dicts)
        final_output_file = self.output_dir / "results.txt"
        total_vulns = 0
        severity_counts = {sev: 0 for sev in ["critical", "high", "medium", "low", "info", "unknown"]}

        # Ensure the final output file exists and is empty before appending
        try:
            with open(final_output_file, 'w') as outfile:
                outfile.write("# Combined Nuclei Scan Results\n")
        except IOError as e:
            logger.error(f"Failed to create or clear final results file {final_output_file}: {e}")
            raise RuntimeError(f"Could not write to results file: {e}")

        logger.info(f"Combining batch results into {final_output_file}...")
        for result in batch_results:
            batch_output_file = result.get("output_file")
            vulnerability_data = result.get("vulnerability_data", [])

            if vulnerability_data:
                try:
                    with open(final_output_file, 'a', encoding='utf-8') as outfile:
                        for line in vulnerability_data:
                            outfile.write(line + '\n')
                            total_vulns += 1
                            # Count severity (simple check)
                            line_lower = line.lower()
                            found_sev = False
                            for sev in severity_counts.keys():
                                if f"[{sev}]" in line_lower:
                                    severity_counts[sev] += 1
                                    found_sev = True
                                    break
                            if not found_sev:
                                severity_counts["unknown"] += 1
                except IOError as e:
                    logger.warning(f"Could not append batch results to {final_output_file}: {e}")

            # Clean up individual batch output file
            if batch_output_file and batch_output_file.exists():
                try:
                    batch_output_file.unlink()
                except OSError as e:
                    logger.warning(f"Could not remove batch output file {batch_output_file}: {e}")

        logger.info(f"Combined results contain {total_vulns} total findings.")
        return total_vulns, severity_counts

    def _generate_scan_report(self, total_vulns: int, severity_counts: Dict[str, int]) -> None:
        # Purpose: Generate a human-readable text report summarizing the scan findings.
        # Usage: self._generate_scan_report(total_vulns, severity_counts)
        report_file = self.output_dir / "scan_report.txt"
        logger.info(f"Generating summary report: {report_file}")
        try:
            with open(report_file, 'w') as report:
                report.write(f"Nuclei Scan Report for {self.domain}\n")
                report.write("=" * 50 + "\n\n")
                report.write(f"Scan Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                report.write(f"Total Potential Vulnerabilities Found: {total_vulns}\n\n")

                report.write("Findings by Severity:\n")
                report.write("-" * 35 + "\n")

                has_findings = False
                for severity, count in severity_counts.items():
                    if count > 0:
                        report.write(f"  {severity.capitalize():<10}: {count}\n")
                        has_findings = True

                if not has_findings:
                     report.write("  No findings with recognized severity levels.\n")

                report.write("\n" + "-"*35 + "\n")
                report.write("\nFor detailed findings, check results.txt\n")
        except IOError as e:
            logger.error(f"Failed to write scan report to {report_file}: {e}")

    async def _run_nuclei(self, alive_subdomains: Set[str], severities: List[str]) -> None:
        # Purpose: Execute the nuclei scanner against live subdomains using specified templates and severity filters.
        # Usage: await self._run_nuclei(alive_subdomains, ["high", "critical"])
        """
        Run nuclei scan on alive subdomains with parallel batches and detailed reporting.
        Refactored for clarity.
        """
        logger.info("Running nuclei scan...")
        self.scan_state["status"] = "scanning_vulnerabilities"

        if not self.templates_path.exists():
            logger.error(f"Nuclei templates not found at {self.templates_path}")
            raise FileNotFoundError(f"Templates directory not found: {self.templates_path}")

        subdomains_list = list(alive_subdomains)
        if not subdomains_list:
            logger.info("No alive subdomains to scan with Nuclei.")
            self.scan_state["vulnerabilities"] = 0
            return

        # Split subdomains into batches for concurrent processing
        # Consider adjusting batch size based on system resources or testing
        batch_size = max(5, len(subdomains_list) // self.max_workers)
        subdomain_batches = [subdomains_list[i:i + batch_size]
                           for i in range(0, len(subdomains_list), batch_size)]
        logger.info(f"Running Nuclei scan in {len(subdomain_batches)} batches...")

        # Process batches concurrently (adjust if needed for stability)
        # If stability issues arise on some systems, process sequentially:
        # batch_results = []
        # for i, batch in enumerate(subdomain_batches):
        #     logger.info(f"Starting Nuclei batch {i+1}/{len(subdomain_batches)}...")
        #     result = await self._run_nuclei_batch(batch, severities)
        #     batch_results.append(result)

        # Concurrent execution:
        tasks = [self._run_nuclei_batch(batch, severities) for batch in subdomain_batches]
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle potential exceptions from gather
        processed_results = []
        for i, result in enumerate(batch_results):
            if isinstance(result, Exception):
                logger.error(f"Error encountered in Nuclei batch {i+1}: {result}", exc_info=result)
                # Optionally create a dummy result dict to avoid breaking combination logic
                processed_results.append({"output_file": None, "vulnerabilities": 0, "vulnerability_data": [], "error": str(result)})
            else:
                processed_results.append(result)

        # Combine results and generate report
        total_vulns, severity_counts = self._combine_nuclei_batch_results(processed_results)
        self._generate_scan_report(total_vulns, severity_counts)

        # Log final counts
        logger.info(f"Nuclei scan finished. Found {total_vulns} potential vulnerabilities.")
        if total_vulns > 0:
            sev_summary = ", ".join([f"{sev.capitalize()}={count}" for sev, count in severity_counts.items() if count > 0])
            logger.info(f"Severity breakdown: {sev_summary}")

        self.scan_state["vulnerabilities"] = total_vulns
        self.scan_state["severity_counts"] = severity_counts

    async def scan(self, severities: List[str], notify: bool = True) -> None:
        # Purpose: Orchestrate the entire scanning pipeline: subdomain discovery, probing, and vulnerability scanning.
        # Usage: await scanner.scan(severities=["medium", "high"], notify=True)
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