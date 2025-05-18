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
from typing import List, Optional, Set, Dict, Any, Generator, Iterator, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import tempfile
import hashlib
import json
import shutil
import itertools

# Import psutil for memory monitoring
import psutil

from autosubnuclei.utils.tool_manager import ToolManager
from autosubnuclei.config.config_manager import ConfigManager
from autosubnuclei.utils.notifier import Notifier
from autosubnuclei.utils.helpers import create_requests_session, download_file
from autosubnuclei.core.checkpoint_manager import CheckpointManager

logger = logging.getLogger(__name__)

class SecurityScanner:
    def __init__(self, domain: str, output_dir: Path, templates_path: Path, checkpoint: Optional[Path] = None):
        self.domain = domain
        self.output_dir = output_dir
        self.templates_path = templates_path.resolve()  # Ensure absolute path
        self.tool_manager = ToolManager()
        self.config_manager = ConfigManager()
        self.notifier = Notifier(self.config_manager)
        
        # Create cache directory
        self.cache_dir = self.output_dir / ".cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Create memory logs directory
        self.memory_logs_dir = self.output_dir / ".memory_logs"
        self.memory_logs_dir.mkdir(parents=True, exist_ok=True)
        
        # Memory usage tracking
        self.memory_stats = {
            "peak_usage": 0,
            "measurements": []
        }
        
        # Initialize checkpoint manager and resumption state
        self.checkpoint_manager = CheckpointManager(domain, output_dir)
        self.resuming = checkpoint is not None
        
        # Load or create scan state
        if self.resuming:
            # Load existing checkpoint
            if not self.checkpoint_manager.load_checkpoint(checkpoint):
                raise ValueError(f"Failed to load checkpoint file: {checkpoint}")
            logger.info(f"Resuming scan from checkpoint: {checkpoint}")
            
            # Initialize scan state from checkpoint
            self._initialize_scan_state_from_checkpoint()
        else:
            # Start a new scan
            self._initialize_new_scan_state()
        
        # Max concurrent tasks
        self.max_workers = os.cpu_count() or 4
        
        # Set memory thresholds for adaptive batch sizing
        self.memory_threshold_mb = 1024  # 1GB default threshold
        
        self._setup_tools()
        self._setup_signal_handlers()
        self._ensure_templates_exist()
        
        # Log initial memory usage
        self._log_memory_usage("initialization")

    def _initialize_new_scan_state(self) -> None:
        """
        Initialize a new scan state and checkpoint
        """
        self.scan_state = {
            "start_time": time.time(),
            "status": "initializing",
            "subdomains": 0,
            "alive_subdomains": 0,
            "vulnerabilities": 0
        }
        
        # Initialize checkpoint with tool versions
        tool_versions = self._get_tool_versions()
        self.checkpoint_manager.initialize_checkpoint(tool_versions)
        logger.info(f"Initialized new scan checkpoint for {self.domain}")

    def _initialize_scan_state_from_checkpoint(self) -> None:
        """
        Initialize scan state from an existing checkpoint
        """
        # Get summary data from checkpoint
        summary = self.checkpoint_manager.get_scan_summary()
        
        # Initialize scan state from checkpoint data
        self.scan_state = {
            "start_time": time.time(),  # Use current time as start time
            "original_start_time": summary.get("start_time", "unknown"),
            "status": "resuming",
            "subdomains": summary.get("statistics", {}).get("subdomains_found", 0),
            "alive_subdomains": summary.get("statistics", {}).get("alive_subdomains", 0),
            "vulnerabilities": summary.get("statistics", {}).get("vulnerabilities_found", 0)
        }
        
        # Validate tool versions against current environment
        current_tool_versions = self._get_tool_versions()
        is_valid, mismatches = self.checkpoint_manager.validate_environment(current_tool_versions)
        
        if not is_valid:
            logger.warning(f"Environment mismatch detected: {mismatches}")
        
        logger.info(f"Loaded scan state from checkpoint for {self.domain}")

    def _get_tool_versions(self) -> Dict[str, str]:
        """
        Get versions of all required tools
        """
        tool_versions = {}
        for tool in self.tool_manager.required_tools:
            tool_versions[tool] = self.tool_manager.get_tool_version(tool) or "unknown"
        return tool_versions

    def _get_memory_usage(self) -> float:
        """
        Get current memory usage in MB.
        """
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        memory_mb = memory_info.rss / 1024 / 1024  # Convert to MB
        
        # Update peak memory usage
        self.memory_stats["peak_usage"] = max(self.memory_stats["peak_usage"], memory_mb)
        
        return memory_mb

    def _log_memory_usage(self, label: str) -> None:
        """
        Log current memory usage with a label.
        """
        memory_mb = self._get_memory_usage()
        logger.debug(f"Memory usage at {label}: {memory_mb:.2f} MB")
        
        # Record the measurement
        self.memory_stats["measurements"].append({
            "timestamp": time.time(),
            "label": label,
            "memory_mb": memory_mb
        })
        
        # Warn if memory usage is approaching the threshold
        if memory_mb > self.memory_threshold_mb * 0.8:
            logger.warning(f"Memory usage is high: {memory_mb:.2f} MB")

    def _save_memory_stats(self) -> None:
        """
        Save memory usage statistics to a JSON file.
        """
        stats_file = self.memory_logs_dir / f"memory_stats_{int(time.time())}.json"
        
        try:
            with open(stats_file, 'w') as f:
                json.dump(self.memory_stats, f, indent=2)
            logger.debug(f"Memory stats saved to {stats_file}")
        except Exception as e:
            logger.error(f"Failed to save memory stats: {str(e)}")

    def _adaptive_batch_size(self, total_items: int) -> int:
        """
        Calculate an appropriate batch size based on current memory usage and total items.
        
        Returns smaller batch sizes when memory usage is high.
        """
        current_memory_mb = self._get_memory_usage()
        memory_ratio = min(1.0, self.memory_threshold_mb / max(1, current_memory_mb))
        
        # Base batch size calculation - adjusted to be more conservative with large lists
        if total_items > 10000:
            # For very large lists, use smaller batches
            base_batch_size = max(10, min(500, total_items // (self.max_workers * 2)))
        else:
            base_batch_size = max(10, total_items // self.max_workers)
        
        # Adjust batch size based on memory usage
        adjusted_batch_size = int(base_batch_size * memory_ratio)
        
        # More aggressive scaling for high memory usage
        if current_memory_mb > self.memory_threshold_mb * 0.7:
            # If memory usage is above 70% of threshold, further reduce batch size
            adjusted_batch_size = int(adjusted_batch_size * 0.5)
        
        # Ensure batch size is at least 5 and at most total_items/2
        batch_size = max(5, min(adjusted_batch_size, total_items // 2 or 1))
        
        logger.debug(f"Adaptive batch size: {batch_size} (memory: {current_memory_mb:.2f} MB, ratio: {memory_ratio:.2f})")
        return batch_size

    def _setup_signal_handlers(self) -> None:
        """
        Setup signal handlers for graceful shutdown
        """
        signal.signal(signal.SIGINT, self._handle_interrupt)
        signal.signal(signal.SIGTERM, self._handle_interrupt)

    def _handle_interrupt(self, signum, frame) -> None:
        """
        Handle interrupt signals with proper cleanup and checkpoint creation
        """
        logger.info("Received interrupt signal, creating checkpoint and cleaning up...")
        
        # Update scan status
        self.scan_state["status"] = "paused"
        
        # Save the checkpoint with current state
        self.checkpoint_manager.set_scan_status("paused")
        self.checkpoint_manager.save_checkpoint()
        
        # Send notification
        self.notifier.send_cancellation_notification(self.domain)
        
        # Save memory stats before exiting
        self._save_memory_stats()
        
        # Save scan state before exiting
        self._save_scan_state()
        
        print(f"\n⏸️  Scan paused. To resume, run: autosubnuclei resume {self.domain}")
        print(f"   Checkpoint saved to: {self.output_dir}/checkpoints/scan_state.json")
        
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
            
            # Update checkpoint with templates hash
            if self.templates_path.exists():
                templates_hash = self._calculate_templates_hash()
                self.checkpoint_manager.set_templates_hash(templates_hash)

    def _calculate_templates_hash(self) -> str:
        """
        Calculate a hash representing the state of templates directory.
        For efficiency, we'll just hash a sample of template files.
        """
        hash_obj = hashlib.md5()
        
        # Get a list of template files
        template_files = list(self.templates_path.glob("**/*.yaml"))
        
        # If there are too many templates, sample a subset
        if len(template_files) > 100:
            import random
            random.shuffle(template_files)
            template_files = template_files[:100]
        
        # Hash the content of each template file
        for template_file in template_files:
            try:
                with open(template_file, 'rb') as f:
                    hash_obj.update(f.read(4096))  # Read only first 4KB for efficiency
            except Exception as e:
                logger.warning(f"Failed to hash template file {template_file}: {str(e)}")
        
        return hash_obj.hexdigest()

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
        Run subfinder to enumerate subdomains.
        
        Returns:
            Set of subdomains
        """
        if self.resuming and self.checkpoint_manager.get_phase_status("subdomain_enumeration") == "completed":
            # If resuming and this phase is already completed, load results from checkpoint
            logger.info("Loading subdomain enumeration results from checkpoint")
            subdomains_file = self.output_dir / "subdomains.txt"
            
            if not subdomains_file.exists():
                logger.warning("Subdomain file not found despite checkpoint indicating completion")
                raise FileNotFoundError(f"Subdomain file not found: {subdomains_file}")
                
            with open(subdomains_file, 'r') as f:
                subdomains = set(line.strip() for line in f if line.strip())
                
            # Update scan state
            self.scan_state["subdomains"] = len(subdomains)
            
            logger.info(f"Loaded {len(subdomains)} subdomains from checkpoint")
            return subdomains
            
        # Update checkpoint status
        self.checkpoint_manager.update_phase_status(
            phase="subdomain_enumeration",
            status="in_progress",
            progress=0,
            results_count=0
        )
            
        # Notify start of subdomain enumeration
        self.scan_state["status"] = "enumerating_subdomains"
        
        # If subfinder is not installed, raise error
        if not await self.tool_manager.ensure_tool_exists("subfinder"):
            raise RuntimeError("subfinder not installed and could not be installed")
            
        logger.info(f"Starting subdomain enumeration for {self.domain}")
        
        # Generate cache key for this command
        subfinder_path = await self.tool_manager.get_tool_path("subfinder")
        cmd = [str(subfinder_path), "-d", self.domain, "-silent"]
        cache_key = self._get_cache_key(cmd)
        
        # Check if we have cached results
        cached_result = self._get_cached_result(cache_key)
        if cached_result:
            logger.info("Using cached subfinder results")
            subdomains_text = cached_result
        else:
            # Run subfinder
            logger.debug(f"Running command: {' '.join(cmd)}")
            result = await self._run_command_async(cmd)
            subdomains_text = result.stdout
            
            # Save to cache
            self._save_to_cache(cache_key, subdomains_text)
            
        # Process and filter results
        subdomains = set(line.strip() for line in subdomains_text.splitlines() if line.strip())
        
        # Save to a file for future reference
        subdomains_file = self.output_dir / "subdomains.txt"
        with open(subdomains_file, 'w') as f:
            for subdomain in sorted(subdomains):
                f.write(f"{subdomain}\n")
        
        self.scan_state["subdomains"] = len(subdomains)
        logger.info(f"Found {len(subdomains)} subdomains for {self.domain}")
        
        # Update statistics in the checkpoint
        self.checkpoint_manager.update_statistics(subdomains_found=len(subdomains))
        
        # Update phase status to completed
        self.checkpoint_manager.update_phase_status(
            phase="subdomain_enumeration",
            status="completed",
            progress=100,
            results_count=len(subdomains)
        )
        
        # Save checkpoint
        self.checkpoint_manager.save_checkpoint()
        
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
            # Return lines as a list instead of a set for streaming processing
            return [line for line in clean_output.strip().split('\n') if line]
        finally:
            # Clean up temp file
            os.unlink(temp_path)

    async def _run_httpx(self, subdomains) -> str:
        """
        Run httpx to check for alive domains.
        
        Args:
            subdomains: List or set of subdomains to check
            
        Returns:
            String output from httpx
        """
        if self.resuming and self.checkpoint_manager.get_phase_status("alive_check") == "completed":
            return await self._load_completed_alive_check()
        
        # Initialize the phase as in-progress
        self._initialize_alive_check_phase()
        
        # Get information about resumption state if applicable
        processed_count = self._get_alive_check_resume_state()
        
        # Ensure httpx is installed
        if not await self.tool_manager.ensure_tool_exists("httpx"):
            raise RuntimeError("httpx not installed and could not be installed")
            
        self.scan_state["status"] = "checking_alive_domains"
        logger.info(f"Checking {len(subdomains)} subdomains for alive hosts")
        
        # Convert to list for indexing
        subdomain_list = list(subdomains)
        
        # Use a temporary file for input to httpx
        temp_file = tempfile.NamedTemporaryFile(mode='w+', delete=False)
        temp_filepath = Path(temp_file.name)
        
        try:
            # Write all subdomains to the temp file
            for subdomain in subdomain_list:
                temp_file.write(f"{subdomain}\n")
            temp_file.flush()
            temp_file.close()
            
            # Process subdomains in batches
            alive_str = await self._process_httpx_batches(subdomain_list, processed_count)
            
            return alive_str
            
        finally:
            # Clean up the temporary file
            try:
                os.unlink(temp_filepath)
            except Exception as e:
                logger.warning(f"Failed to delete temporary file {temp_filepath}: {str(e)}")

    async def _load_completed_alive_check(self) -> str:
        """Load alive subdomains from a completed checkpoint."""
        logger.info("Loading alive subdomains from checkpoint")
        alive_file = self.output_dir / "alive.txt"
        
        if not alive_file.exists():
            logger.warning("Alive subdomains file not found despite checkpoint indicating completion")
            raise FileNotFoundError(f"Alive subdomains file not found: {alive_file}")
            
        with open(alive_file, 'r') as f:
            alive_data = f.read()
            
        # Count lines to update scan state
        alive_subdomains = len([line for line in alive_data.splitlines() if line.strip()])
        self.scan_state["alive_subdomains"] = alive_subdomains
        
        logger.info(f"Loaded {alive_subdomains} alive subdomains from checkpoint")
        return alive_data

    def _initialize_alive_check_phase(self) -> None:
        """Initialize the alive check phase as in-progress."""
        self.checkpoint_manager.update_phase_status(
            phase="alive_check",
            status="in_progress",
            progress=0,
            results_count=0
        )

    def _get_alive_check_resume_state(self) -> int:
        """
        Get information about the resumption state for alive checking.
        
        Returns:
            int: Number of already processed items
        """
        processed_count = 0
        if self.resuming:
            phase_data = self.checkpoint_manager.get_phase_data("alive_check")
            if phase_data and "checkpoint" in phase_data:
                # Get the last processed batch index
                last_batch_index = phase_data["checkpoint"].get("batch_index", 0)
                processed_count = last_batch_index * phase_data["checkpoint"].get("batch_size", 0)
                logger.info(f"Resuming alive check from batch {last_batch_index} ({processed_count} already processed)")
        return processed_count

    async def _process_httpx_batches(self, subdomain_list: List[str], processed_count: int) -> str:
        """
        Process subdomains in batches using httpx.
        
        Args:
            subdomain_list: List of subdomains to process
            processed_count: Number of already processed items
            
        Returns:
            String representation of alive domains
        """
        # Calculate appropriate batch size based on memory usage
        batch_size = self._adaptive_batch_size(len(subdomain_list))
        
        # Process in batches to prevent memory issues
        total_batches = (len(subdomain_list) + batch_size - 1) // batch_size
        all_alive = []
        
        # Skip already processed batches if resuming
        start_batch = processed_count // batch_size if processed_count > 0 else 0
        
        for batch_idx in range(start_batch, total_batches):
            all_alive = await self._process_single_httpx_batch(
                subdomain_list, batch_idx, batch_size, total_batches, all_alive
            )
        
        # Convert list of alive domains to string format
        alive_str = "\n".join(sorted(all_alive))
        
        # Save alive domains to a file and update checkpoint
        self._save_alive_results(alive_str, len(all_alive))
        
        return alive_str

    async def _process_single_httpx_batch(
        self, subdomain_list: List[str], batch_idx: int, batch_size: int, 
        total_batches: int, all_alive: List[str]
    ) -> List[str]:
        """
        Process a single batch of subdomains with httpx.
        
        Args:
            subdomain_list: Complete list of subdomains
            batch_idx: Current batch index
            batch_size: Size of each batch
            total_batches: Total number of batches
            all_alive: List of already found alive domains
            
        Returns:
            Updated list of alive domains
        """
        batch_start = batch_idx * batch_size
        batch_end = min((batch_idx + 1) * batch_size, len(subdomain_list))
        current_batch = subdomain_list[batch_start:batch_end]
        
        # Update checkpoint with current batch progress
        self._update_batch_checkpoint(batch_idx, batch_size, total_batches)
        
        # Run httpx on this batch
        alive_batch = await self._run_httpx_batch(current_batch)
        all_alive.extend(alive_batch)
        
        # Update progress and statistics
        self._update_httpx_progress(batch_idx, total_batches, all_alive)
        
        # Perform memory management
        self._perform_batch_memory_management(batch_idx)
        
        return all_alive

    def _update_batch_checkpoint(self, batch_idx: int, batch_size: int, total_batches: int) -> None:
        """Update checkpoint with current batch progress."""
        self.checkpoint_manager.update_checkpoint(
            phase="alive_check",
            checkpoint={
                "batch_index": batch_idx,
                "batch_size": batch_size,
                "progress": int((batch_idx / total_batches) * 100)
            }
        )
        self.checkpoint_manager.save_checkpoint()

    def _update_httpx_progress(self, batch_idx: int, total_batches: int, all_alive: List[str]) -> None:
        """Update progress indicators and phase status."""
        progress_percentage = int(((batch_idx + 1) / total_batches) * 100)
        self.checkpoint_manager.update_phase_status(
            phase="alive_check",
            status="in_progress",
            progress=progress_percentage,
            results_count=len(all_alive)
        )
        
        # Update scan state
        self.scan_state["alive_subdomains"] = len(all_alive)

    def _perform_batch_memory_management(self, batch_idx: int) -> None:
        """Perform memory management after processing a batch."""
        # Log memory usage after batch
        self._log_memory_usage(f"httpx_batch_{batch_idx}")
        
        # Trigger garbage collection to release memory
        import gc
        gc.collect()
        
        # Save checkpoint every 5 batches
        if (batch_idx + 1) % 5 == 0:
            self.checkpoint_manager.save_checkpoint()

    def _save_alive_results(self, alive_str: str, alive_count: int) -> None:
        """
        Save alive domains results and update checkpoint.
        
        Args:
            alive_str: String representation of alive domains
            alive_count: Number of alive domains found
        """
        # Save alive domains to a file
        alive_file = self.output_dir / "alive.txt"
        with open(alive_file, 'w') as f:
            f.write(alive_str)
        
        # Update statistics in the checkpoint
        self.checkpoint_manager.update_statistics(alive_subdomains=alive_count)
        
        # Update phase status to completed
        self.checkpoint_manager.update_phase_status(
            phase="alive_check",
            status="completed",
            progress=100,
            results_count=alive_count
        )
        
        # Save final checkpoint for this phase
        self.checkpoint_manager.save_checkpoint()

    async def _run_nuclei_in_batches(self, targets_file: Path, severities: List[str], batch_size: int) -> List[Dict[str, Any]]:
        """
        Run nuclei scan by processing the targets file in batches.
        This approach helps manage memory usage for large target lists.
        
        Args:
            targets_file: Path to the file containing all targets
            severities: List of severity levels to scan for
            batch_size: Number of targets to process in each batch
            
        Returns:
            List of dictionaries containing batch results
        """
        logger.info(f"Running nuclei scan in batches with batch size {batch_size}")
        
        # Count total targets and calculate batches
        total_lines, total_batches = self._count_targets_and_calculate_batches(targets_file, batch_size)
        
        # Process all batches and collect results
        return await self._process_nuclei_batches(targets_file, severities, batch_size, total_batches)

    def _count_targets_and_calculate_batches(self, targets_file: Path, batch_size: int) -> Tuple[int, int]:
        """
        Count targets in file and calculate number of batches needed.
        
        Args:
            targets_file: Path to the targets file
            batch_size: Size of each batch
            
        Returns:
            Tuple containing (total_lines, total_batches)
        """
        with open(targets_file, 'r') as f:
            total_lines = sum(1 for _ in f)
        
        # Calculate total batches
        total_batches = (total_lines + batch_size - 1) // batch_size
        logger.info(f"Processing {total_lines} targets in {total_batches} batches")
        
        return total_lines, total_batches

    async def _process_nuclei_batches(
        self, targets_file: Path, severities: List[str], batch_size: int, total_batches: int
    ) -> List[Dict[str, Any]]:
        """
        Process all batches with nuclei scan.
        
        Args:
            targets_file: Path to the targets file
            severities: List of severity levels to scan for
            batch_size: Size of each batch
            total_batches: Total number of batches
            
        Returns:
            List of batch results
        """
        batch_results = []
        
        # Process the file in streaming fashion, don't load entire file into memory
        with open(targets_file, 'r') as main_file:
            for batch_num in range(total_batches):
                # Log memory usage before each batch
                self._log_memory_usage(f"before_nuclei_batch_{batch_num+1}")
                
                # Create and process batch file
                batch_file = self._create_batch_file(batch_num)
                
                try:
                    # Process this batch and add results
                    valid_lines = self._write_batch_from_source(main_file, batch_file, batch_size)
                    
                    # Skip empty batch files
                    if valid_lines == 0:
                        logger.debug(f"Skipping empty batch {batch_num+1}")
                        self._clean_batch_file(batch_file)
                        continue
                    
                    # Process the batch
                    result = await self._process_single_nuclei_batch(
                        batch_file, severities, batch_num, total_batches, valid_lines
                    )
                    batch_results.append(result)
                    
                except Exception as e:
                    logger.error(f"Error processing batch {batch_num+1}: {str(e)}")
                finally:
                    # Clean up batch file
                    self._clean_batch_file(batch_file)
        
        return batch_results

    def _create_batch_file(self, batch_num: int) -> Path:
        """
        Create a batch file path.
        
        Args:
            batch_num: Batch number
            
        Returns:
            Path to the batch file
        """
        return self.output_dir / f"nuclei_batch_{batch_num}_{int(time.time())}.txt"

    def _write_batch_from_source(self, source_file, batch_file_path: Path, batch_size: int) -> int:
        """
        Write batch_size lines from source file to batch file.
        
        Args:
            source_file: Source file object to read from
            batch_file_path: Path to write batch to
            batch_size: Number of lines to write
            
        Returns:
            Number of valid lines written
        """
        valid_lines = 0
        
        with open(batch_file_path, 'w') as batch_f:
            # Loop until we have batch_size valid lines or reach EOF
            while valid_lines < batch_size:
                line = source_file.readline()
                if not line:  # End of file
                    break
                
                # Only write non-empty lines
                line = line.strip()
                if line:
                    batch_f.write(f"{line}\n")
                    valid_lines += 1
        
        return valid_lines

    def _clean_batch_file(self, batch_file_path: Path) -> None:
        """
        Delete a batch file if it exists.
        
        Args:
            batch_file_path: Path to the batch file
        """
        if batch_file_path.exists():
            batch_file_path.unlink()

    async def _process_single_nuclei_batch(
        self, batch_file: Path, severities: List[str], batch_num: int, 
        total_batches: int, valid_lines: int
    ) -> Dict[str, Any]:
        """
        Process a single batch with nuclei.
        
        Args:
            batch_file: Path to the batch file
            severities: List of severity levels to scan for
            batch_num: Current batch number
            total_batches: Total number of batches
            valid_lines: Number of valid lines in the batch
            
        Returns:
            Dictionary with batch results
        """
        logger.info(f"Processing nuclei batch {batch_num+1}/{total_batches} with {valid_lines} targets")
        
        # Run nuclei on this batch
        result = await self._run_nuclei_single_batch(batch_file, severities)
        
        # Log memory usage after each batch
        self._log_memory_usage(f"after_nuclei_batch_{batch_num+1}")
        
        # Force garbage collection after each batch
        import gc
        gc.collect()
        
        return result

    async def _run_nuclei_single_batch(self, targets_file: Path, severities: List[str]) -> Dict[str, Any]:
        """
        Run nuclei scan on a single batch of targets.
        
        Args:
            targets_file: Path to the file containing targets for this batch
            severities: List of severity levels to scan for
            
        Returns:
            Dictionary with batch results
        """
        # Create output file for this batch
        output_file = self.output_dir / f"nuclei_results_{int(time.time())}.txt"
        
        # Build nuclei command
        command = [
            "nuclei",
            "-l", str(targets_file),
            "-t", str(self.templates_path),
            "-o", str(output_file),
            "-silent",
        ]
        
        # Add severity filter if provided
        if severities:
            command.extend(["-severity", ",".join(severities)])
        
        # Add additional default flags
        command.extend([
            "-ni",  # No interaction/color
            "-c", str(min(self.max_workers, 25)),  # Limit concurrency
            "-bulk-size", "25",  # Use smaller bulk size to reduce memory usage
            "-rate-limit", "150",  # Limit request rate
        ])
        
        try:
            # Run nuclei command
            await self._run_command_async(command)
            
            # Check for results
            vulnerability_count = 0
            if output_file.exists():
                with open(output_file, 'r') as f:
                    vulnerability_count = sum(1 for line in f if line.strip())
            
            # Log result
            logger.info(f"Found {vulnerability_count} potential vulnerabilities in batch")
            
            return {
                "output_file": output_file,
                "vulnerabilities": vulnerability_count
            }
        except Exception as e:
            logger.error(f"Error running nuclei: {str(e)}")
            return {
                "output_file": output_file if output_file.exists() else None,
                "vulnerabilities": 0,
                "error": str(e)
            }

    async def _run_nuclei(self, alive_subdomains, severities: List[str]) -> None:
        """
        Run nuclei on alive domains.
        
        Args:
            alive_subdomains: String of alive domains (from httpx)
            severities: List of severity levels to scan for
        """
        if self.resuming and self.checkpoint_manager.get_phase_status("vulnerability_scan") == "completed":
            # If resuming and this phase is already completed, load results from checkpoint
            logger.info("Loading vulnerability scan results from checkpoint")
            results_file = self.output_dir / "results.txt"
            
            if not results_file.exists():
                logger.warning("Results file not found despite checkpoint indicating completion")
                # Continue with scan, we may have an incomplete checkpoint
            else:
                # Count vulnerabilities to update scan state
                with open(results_file, 'r') as f:
                    vulnerability_count = len([line for line in f if line.strip()])
                
                self.scan_state["vulnerabilities"] = vulnerability_count
                logger.info(f"Loaded {vulnerability_count} vulnerabilities from checkpoint")
                return
        
        # Update checkpoint status
        self.checkpoint_manager.update_phase_status(
            phase="vulnerability_scan",
            status="in_progress",
            progress=0,
            results_count=0
        )
        self.checkpoint_manager.save_checkpoint()
        
        # Notify start of vulnerability scan
        self.scan_state["status"] = "scanning_vulnerabilities"
        
        # Ensure nuclei is installed
        if not await self.tool_manager.ensure_tool_exists("nuclei"):
            raise RuntimeError("nuclei not installed and could not be installed")
            
        # Check if we have alive domains to scan
        if not alive_subdomains or not alive_subdomains.strip():
            logger.warning("No alive domains found, skipping nuclei scan")
            
            # Update phase status to completed
            self.checkpoint_manager.update_phase_status(
                phase="vulnerability_scan",
                status="completed",
                progress=100,
                results_count=0
            )
            self.checkpoint_manager.save_checkpoint()
            return
            
        # Count the number of targets
        targets_count = len(alive_subdomains.strip().split("\n"))
        logger.info(f"Starting nuclei scan on {targets_count} targets")
        
        # Create a targets file for nuclei
        targets_file = self.output_dir / "alive.txt"
        with open(targets_file, "w") as f:
            f.write(alive_subdomains)
            
        # Get batch size appropriate for memory constraints
        batch_size = self._adaptive_batch_size(targets_count)
        
        # Run nuclei in batches
        try:
            results = await self._run_nuclei_in_batches(targets_file, severities, batch_size)
            
            # Parse and save results
            results_text = ""
            for result in results:
                if "raw_result" in result:
                    results_text += result["raw_result"] + "\n"
                    
            # Save results to file
            results_file = self.output_dir / "results.txt"
            with open(results_file, "w") as f:
                f.write(results_text)
                
            # Count vulnerabilities found
            vulnerability_count = len(results)
            self.scan_state["vulnerabilities"] = vulnerability_count
            
            # Update statistics in the checkpoint
            self.checkpoint_manager.update_statistics(vulnerabilities_found=vulnerability_count)
            
            # Update phase status to completed
            self.checkpoint_manager.update_phase_status(
                phase="vulnerability_scan",
                status="completed",
                progress=100,
                results_count=vulnerability_count
            )
            
            # Save final checkpoint
            self.checkpoint_manager.save_checkpoint()
            
            logger.info(f"Found {vulnerability_count} vulnerabilities")
            
        except Exception as e:
            # If we encounter an error, mark the phase as failed
            self.checkpoint_manager.update_phase_status(
                phase="vulnerability_scan",
                status="failed",
                progress=0,
                results_count=0
            )
            self.checkpoint_manager.save_checkpoint()
            
            # Re-raise the exception
            raise e

    async def scan(self, severities: List[str], notify: bool = True) -> None:
        """
        Run the full security scan pipeline
        
        Args:
            severities: List of severity levels to scan for
            notify: Whether to send notifications
        """
        start_time = time.time()
        
        try:
            # Set scan status to running
            self.scan_state["status"] = "running"
            self.checkpoint_manager.set_scan_status("in_progress")
            self.checkpoint_manager.save_checkpoint()
            
            # Send start notification
            if notify:
                self.notifier.send_start_notification(self.domain)
            
            # Step 1: Run subfinder to enumerate subdomains
            subdomain_phase_status = self.checkpoint_manager.get_phase_status("subdomain_enumeration") 
            if not self.resuming or subdomain_phase_status != "completed":
                subdomains = await self._run_subfinder()
                logger.info(f"Subfinder found {len(subdomains)} subdomains")
            else:
                # Load subdomains from file if we're resuming
                subdomains_file = self.output_dir / "subdomains.txt"
                with open(subdomains_file, 'r') as f:
                    subdomains = set(line.strip() for line in f if line.strip())
                logger.info(f"Loaded {len(subdomains)} subdomains from previous scan")
                
            # Step 2: Run httpx to check for alive domains
            alive_phase_status = self.checkpoint_manager.get_phase_status("alive_check")
            if not self.resuming or alive_phase_status != "completed":
                alive_domains_text = await self._run_httpx(subdomains)
                logger.info(f"HTTPX found {self.scan_state['alive_subdomains']} alive domains")
            else:
                # Load alive domains from file if we're resuming
                alive_file = self.output_dir / "alive.txt"
                with open(alive_file, 'r') as f:
                    alive_domains_text = f.read()
                logger.info(f"Loaded {self.scan_state['alive_subdomains']} alive domains from previous scan")
            
            # Step 3: Run nuclei to scan for vulnerabilities
            vulnerability_phase_status = self.checkpoint_manager.get_phase_status("vulnerability_scan")
            if not self.resuming or vulnerability_phase_status != "completed":
                await self._run_nuclei(alive_domains_text, severities)
            else:
                logger.info("Skipping vulnerability scan - already completed in previous run")
            
            # Set scan status to completed
            self.scan_state["status"] = "completed"
            self.checkpoint_manager.set_scan_status("completed")
            
            # Calculate and save duration
            duration = time.time() - start_time
            self.scan_state["duration"] = duration
            
            # Log final memory usage
            self._log_memory_usage("scan_complete")
            self._save_memory_stats()
            
            # Clean up any temporary files
            self._clean_temp_files()
            
            # Save final scan state
            self._save_scan_state()
            self.checkpoint_manager.save_checkpoint()
            
            # Send completion notification
            if notify:
                self.notifier.send_completion_notification(
                    domain=self.domain,
                    subdomains=self.scan_state["subdomains"],
                    alive=self.scan_state["alive_subdomains"],
                    vulnerabilities=self.scan_state["vulnerabilities"],
                    duration=duration
                )
                
            logger.info(f"Scan completed in {duration:.2f} seconds")
            
        except Exception as e:
            # Set scan status to failed
            self.scan_state["status"] = "failed"
            self.checkpoint_manager.set_scan_status("failed")
            
            # Save scan state and checkpoint
            self._save_scan_state()
            self.checkpoint_manager.save_checkpoint()
            
            # Send error notification
            if notify:
                self.notifier.send_error_notification(self.domain, str(e))
                
            logger.error(f"Scan failed: {str(e)}")
            raise e

    def _clean_temp_files(self) -> None:
        """
        Clean up temporary files to free disk space.
        """
        try:
            # Get all temporary files in the output directory
            temp_files = list(self.output_dir.glob("nuclei_batch_*")) + \
                        list(self.output_dir.glob("nuclei_targets_*")) + \
                        list(self.output_dir.glob("nuclei_results_*")) + \
                        list(self.output_dir.glob("*_temp_*"))
            
            for temp_file in temp_files:
                if temp_file.exists():
                    try:
                        temp_file.unlink()
                        logger.debug(f"Removed temporary file: {temp_file}")
                    except Exception as e:
                        logger.debug(f"Failed to remove temporary file {temp_file}: {str(e)}")
        except Exception as e:
            logger.error(f"Error cleaning up temporary files: {str(e)}") 