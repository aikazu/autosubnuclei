"""
Checkpoint manager for handling scan state persistence and resumption
"""

import json
import logging
import os
import time
import datetime
import hashlib
import fcntl
import errno
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

logger = logging.getLogger(__name__)

class FileLock:
    """
    A simple file-based lock mechanism to prevent concurrent writes to checkpoint files.
    """
    def __init__(self, lock_file: Path):
        self.lock_file = lock_file
        self.lock_handle = None
        self.lock_strategy = self._create_lock_strategy()
        
    def _create_lock_strategy(self):
        """Create appropriate lock strategy based on platform."""
        if os.name == 'nt':  # Windows
            return WindowsLockStrategy()
        else:  # Unix/Linux/Mac
            return UnixLockStrategy()
        
    def acquire(self, timeout: int = 10, check_interval: float = 0.1) -> bool:
        """
        Acquire the lock with timeout.
        
        Args:
            timeout: Maximum time to wait for lock in seconds
            check_interval: Time between retry attempts
            
        Returns:
            bool: True if lock acquired, False otherwise
        """
        start_time = time.time()
        
        # Create parent directory if it doesn't exist
        self.lock_file.parent.mkdir(parents=True, exist_ok=True)
        
        while True:
            try:
                # Open the file in exclusive mode
                self.lock_handle = open(str(self.lock_file), 'w')
                
                # Acquire lock using platform-specific strategy
                if self.lock_strategy.acquire_lock(self.lock_handle):
                    logger.debug(f"Lock acquired on {self.lock_file}")
                    return True
                    
            except (IOError, OSError) as e:
                # Check if we should retry or fail based on error type
                if not self.lock_strategy.should_retry(e):
                    logger.error(f"Error acquiring lock: {str(e)}")
                    return False
                    
                # Check if we've exceeded the timeout
                if time.time() - start_time > timeout:
                    logger.warning(f"Timeout waiting for lock on {self.lock_file}")
                    return False
                
                # Sleep before trying again
                time.sleep(check_interval)
    
    def release(self) -> bool:
        """
        Release the lock.
        
        Returns:
            bool: True if released successfully, False otherwise
        """
        if not self.lock_handle:
            return False
            
        try:
            # Release lock using platform-specific strategy
            self.lock_strategy.release_lock(self.lock_handle)
            
            self.lock_handle.close()
            self.lock_handle = None
            
            # Remove the lock file
            if self.lock_file.exists():
                self.lock_file.unlink()
                
            logger.debug(f"Lock released on {self.lock_file}")
            return True
            
        except Exception as e:
            logger.error(f"Error releasing lock: {str(e)}")
            return False
            
    def __enter__(self):
        self.acquire()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()


class LockStrategy:
    """Base class for platform-specific lock strategies."""
    
    def acquire_lock(self, file_handle) -> bool:
        """
        Acquire a lock on the file handle.
        
        Args:
            file_handle: Open file handle
            
        Returns:
            bool: True if lock acquired, False otherwise
        """
        raise NotImplementedError("Subclasses must implement acquire_lock")
        
    def release_lock(self, file_handle) -> None:
        """
        Release the lock on the file handle.
        
        Args:
            file_handle: Open file handle
        """
        raise NotImplementedError("Subclasses must implement release_lock")
        
    def should_retry(self, error: Exception) -> bool:
        """
        Determine if lock acquisition should be retried based on the error.
        
        Args:
            error: Exception raised during lock acquisition
            
        Returns:
            bool: True if should retry, False otherwise
        """
        raise NotImplementedError("Subclasses must implement should_retry")


class WindowsLockStrategy(LockStrategy):
    """Lock strategy for Windows platforms."""
    
    def acquire_lock(self, file_handle) -> bool:
        """
        Acquire a lock on Windows (simplified implementation).
        
        Args:
            file_handle: Open file handle
            
        Returns:
            bool: True (Windows implementation is simplified)
        """
        # Windows doesn't have fcntl, so this is a simple implementation
        # that doesn't handle all edge cases but works for basic locking
        return True
        
    def release_lock(self, file_handle) -> None:
        """
        Release the lock on Windows (no special action needed).
        
        Args:
            file_handle: Open file handle
        """
        # No special action needed for Windows
        pass
        
    def should_retry(self, error: Exception) -> bool:
        """
        Determine if lock acquisition should be retried on Windows.
        
        Args:
            error: Exception raised during lock acquisition
            
        Returns:
            bool: False (simplified implementation doesn't retry)
        """
        # Simplified implementation doesn't retry on any errors
        return False


class UnixLockStrategy(LockStrategy):
    """Lock strategy for Unix/Linux/Mac platforms."""
    
    def acquire_lock(self, file_handle) -> bool:
        """
        Acquire a lock using fcntl on Unix systems.
        
        Args:
            file_handle: Open file handle
            
        Returns:
            bool: True if lock acquired
        """
        # Try to acquire an exclusive lock
        fcntl.flock(file_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
        
    def release_lock(self, file_handle) -> None:
        """
        Release the lock using fcntl on Unix systems.
        
        Args:
            file_handle: Open file handle
        """
        fcntl.flock(file_handle, fcntl.LOCK_UN)
        
    def should_retry(self, error: Exception) -> bool:
        """
        Determine if lock acquisition should be retried on Unix.
        
        Args:
            error: Exception raised during lock acquisition
            
        Returns:
            bool: True if error indicates the file is locked, False otherwise
        """
        # Retry if the error indicates the file is locked
        return isinstance(error, (IOError, OSError)) and (
            error.errno == errno.EAGAIN or error.errno == errno.EACCES
        )


class CheckpointManager:
    """
    Manages scan state checkpoints for resuming interrupted scans
    """
    
    def __init__(self, domain: str, output_dir: Path):
        """
        Initialize the checkpoint manager.
        
        Args:
            domain: Domain being scanned
            output_dir: Output directory for scan results
        """
        self.domain = domain
        self.checkpoint_dir = output_dir / "checkpoints"
        self.checkpoint_file = self.checkpoint_dir / "scan_state.json"
        self.lock_file = self.checkpoint_dir / "scan_state.lock"
        self.scan_id = self._generate_scan_id()
        self.checkpoint_data = None
        
        # Create checkpoint directory
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
    
    def _generate_scan_id(self) -> str:
        """
        Generate a unique scan ID.
        
        Returns:
            str: Unique scan ID
        """
        # Use domain name, timestamp, and a random component for uniqueness
        timestamp = int(time.time())
        unique_str = f"{self.domain}-{timestamp}"
        
        # Add a short hash for additional uniqueness
        hash_obj = hashlib.md5(unique_str.encode())
        hash_suffix = hash_obj.hexdigest()[:8]
        
        return f"{self.domain}-{timestamp}-{hash_suffix}"
    
    def initialize_checkpoint(self, tool_versions: Dict[str, str]) -> None:
        """
        Initialize a new checkpoint.
        
        Args:
            tool_versions: Dictionary of tool names and versions
        """
        now = datetime.datetime.now().isoformat()
        
        # Create initial checkpoint structure
        self.checkpoint_data = {
            "scan_id": self.scan_id,
            "domain": self.domain,
            "start_time": now,
            "last_update": now,
            "status": "in_progress",
            "phases": {
                "subdomain_enumeration": {
                    "status": "pending",
                    "progress_percentage": 0,
                    "results_count": 0
                },
                "alive_check": {
                    "status": "pending",
                    "progress_percentage": 0,
                    "results_count": 0
                },
                "vulnerability_scan": {
                    "status": "pending",
                    "progress_percentage": 0,
                    "results_count": 0
                }
            },
            "statistics": {
                "subdomains_found": 0,
                "alive_subdomains": 0,
                "vulnerabilities_found": 0
            },
            "environment": {
                "tool_versions": tool_versions,
                "templates_hash": ""  # Will be populated when templates are loaded
            }
        }
        
        # Save the initial checkpoint
        self.save_checkpoint()
        logger.info(f"Initialized new scan checkpoint: {self.scan_id}")
    
    def update_phase_status(self, phase: str, status: str, progress: int, results_count: int) -> None:
        """
        Update a phase's status.
        
        Args:
            phase: Phase name
            status: Status string (pending, in_progress, completed)
            progress: Progress percentage (0-100)
            results_count: Number of results found
        """
        if not self.checkpoint_data:
            logger.error("Cannot update phase status: checkpoint not initialized")
            return
            
        with FileLock(self.lock_file):
            # Update the phase status
            if phase in self.checkpoint_data["phases"]:
                self.checkpoint_data["phases"][phase].update({
                    "status": status,
                    "progress_percentage": progress,
                    "results_count": results_count
                })
                
                # Update last update time
                self.checkpoint_data["last_update"] = datetime.datetime.now().isoformat()
                
                # Save the updated checkpoint
                self._write_checkpoint()
                logger.debug(f"Updated phase {phase} status to {status} ({progress}%)")
            else:
                logger.warning(f"Attempted to update unknown phase: {phase}")
    
    def update_checkpoint(self, phase: str, **kwargs) -> None:
        """
        Update checkpoint with phase-specific data.
        
        Args:
            phase: Phase name
            **kwargs: Additional data to store in the phase checkpoint
        """
        if not self.checkpoint_data:
            logger.error("Cannot update checkpoint: checkpoint not initialized")
            return
            
        with FileLock(self.lock_file):
            # Update the phase data
            if phase in self.checkpoint_data["phases"]:
                # Create checkpoint key if it doesn't exist
                if "checkpoint" not in self.checkpoint_data["phases"][phase]:
                    self.checkpoint_data["phases"][phase]["checkpoint"] = {}
                    
                # Update with provided data
                self.checkpoint_data["phases"][phase]["checkpoint"].update(kwargs)
                
                # Update last update time
                self.checkpoint_data["last_update"] = datetime.datetime.now().isoformat()
                
                # Save the updated checkpoint
                self._write_checkpoint()
                logger.debug(f"Updated checkpoint data for phase {phase}")
            else:
                logger.warning(f"Attempted to update unknown phase: {phase}")
    
    def update_statistics(self, **kwargs) -> None:
        """
        Update scan statistics.
        
        Args:
            **kwargs: Statistics to update
        """
        if not self.checkpoint_data:
            logger.error("Cannot update statistics: checkpoint not initialized")
            return
            
        with FileLock(self.lock_file):
            # Update statistics
            for key, value in kwargs.items():
                if key in self.checkpoint_data["statistics"]:
                    self.checkpoint_data["statistics"][key] = value
                    
            # Update last update time
            self.checkpoint_data["last_update"] = datetime.datetime.now().isoformat()
            
            # Save the updated checkpoint
            self._write_checkpoint()
            logger.debug(f"Updated scan statistics: {kwargs}")
    
    def set_templates_hash(self, templates_hash: str) -> None:
        """
        Set the templates hash.
        
        Args:
            templates_hash: Hash of templates used in the scan
        """
        if not self.checkpoint_data:
            logger.error("Cannot set templates hash: checkpoint not initialized")
            return
            
        with FileLock(self.lock_file):
            # Update templates hash
            self.checkpoint_data["environment"]["templates_hash"] = templates_hash
            
            # Update last update time
            self.checkpoint_data["last_update"] = datetime.datetime.now().isoformat()
            
            # Save the updated checkpoint
            self._write_checkpoint()
            logger.debug(f"Set templates hash: {templates_hash}")
    
    def set_scan_status(self, status: str) -> None:
        """
        Set the overall scan status.
        
        Args:
            status: Scan status (in_progress, paused, completed, failed)
        """
        if not self.checkpoint_data:
            logger.error("Cannot set scan status: checkpoint not initialized")
            return
            
        with FileLock(self.lock_file):
            # Update scan status
            self.checkpoint_data["status"] = status
            
            # Update last update time
            self.checkpoint_data["last_update"] = datetime.datetime.now().isoformat()
            
            # Save the updated checkpoint
            self._write_checkpoint()
            logger.info(f"Set scan status to {status}")
    
    def save_checkpoint(self) -> bool:
        """
        Save checkpoint to disk.
        
        Returns:
            bool: True if saved successfully, False otherwise
        """
        if not self.checkpoint_data:
            logger.error("Cannot save checkpoint: checkpoint not initialized")
            return False
            
        with FileLock(self.lock_file):
            # Save the checkpoint
            return self._write_checkpoint()
    
    def _write_checkpoint(self) -> bool:
        """
        Write checkpoint data to disk.
        
        Returns:
            bool: True if written successfully, False otherwise
        """
        try:
            # Ensure directory exists
            self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
            
            # Write checkpoint data to file
            with open(self.checkpoint_file, 'w') as f:
                json.dump(self.checkpoint_data, f, indent=2)
                
            logger.debug(f"Checkpoint saved to {self.checkpoint_file}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving checkpoint: {str(e)}")
            return False
    
    def load_checkpoint(self, checkpoint_file: Optional[Path] = None) -> bool:
        """
        Load checkpoint from disk.
        
        Args:
            checkpoint_file: Optional path to checkpoint file (defaults to self.checkpoint_file)
            
        Returns:
            bool: True if loaded successfully, False otherwise
        """
        try:
            # Use provided file or default
            target_file = checkpoint_file or self.checkpoint_file
            
            # Check if file exists
            if not target_file.exists():
                logger.error(f"Checkpoint file does not exist: {target_file}")
                return False
                
            # Load checkpoint data
            with open(target_file, 'r') as f:
                self.checkpoint_data = json.load(f)
                
            # Update scan ID from loaded data
            self.scan_id = self.checkpoint_data["scan_id"]
            
            logger.info(f"Loaded checkpoint for scan {self.scan_id} from {target_file}")
            return True
            
        except Exception as e:
            logger.error(f"Error loading checkpoint: {str(e)}")
            return False
    
    def validate_environment(self, current_tool_versions: Dict[str, str]) -> Tuple[bool, List[str]]:
        """
        Validate that the current environment matches the checkpoint environment.
        
        Args:
            current_tool_versions: Dictionary of tool names and versions
            
        Returns:
            Tuple[bool, List[str]]: (is_valid, list_of_mismatches)
        """
        if not self.checkpoint_data:
            logger.error("Cannot validate environment: checkpoint not initialized")
            return False, ["Checkpoint not initialized"]
            
        # Check tool versions
        mismatches = []
        checkpoint_versions = self.checkpoint_data["environment"]["tool_versions"]
        
        for tool, version in current_tool_versions.items():
            if tool in checkpoint_versions:
                if checkpoint_versions[tool] != version:
                    mismatches.append(f"Tool version mismatch for {tool}: {checkpoint_versions[tool]} (checkpoint) vs {version} (current)")
        
        # Consider valid if no mismatches or only minor version differences
        is_valid = len(mismatches) == 0
        
        if is_valid:
            logger.info("Environment validation passed")
        else:
            logger.warning(f"Environment validation failed: {', '.join(mismatches)}")
        
        return is_valid, mismatches
    
    def get_phase_status(self, phase: str) -> Optional[str]:
        """
        Get the status of a specific phase.
        
        Args:
            phase: Phase name
            
        Returns:
            Optional[str]: Phase status or None if phase not found
        """
        if not self.checkpoint_data:
            logger.error("Cannot get phase status: checkpoint not initialized")
            return None
            
        if phase in self.checkpoint_data["phases"]:
            return self.checkpoint_data["phases"][phase]["status"]
        else:
            logger.warning(f"Attempted to get status of unknown phase: {phase}")
            return None
            
    def get_phase_data(self, phase: str) -> Optional[Dict[str, Any]]:
        """
        Get all data for a specific phase.
        
        Args:
            phase: Phase name
            
        Returns:
            Optional[Dict[str, Any]]: Phase data or None if phase not found
        """
        if not self.checkpoint_data:
            logger.error("Cannot get phase data: checkpoint not initialized")
            return None
            
        if phase in self.checkpoint_data["phases"]:
            return self.checkpoint_data["phases"][phase]
        else:
            logger.warning(f"Attempted to get data of unknown phase: {phase}")
            return None
    
    def get_scan_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the scan state.
        
        Returns:
            Dict[str, Any]: Scan summary
        """
        if not self.checkpoint_data:
            logger.error("Cannot get scan summary: checkpoint not initialized")
            return {}
            
        # Create a summary of the scan
        return {
            "scan_id": self.checkpoint_data["scan_id"],
            "domain": self.checkpoint_data["domain"],
            "start_time": self.checkpoint_data["start_time"],
            "last_update": self.checkpoint_data["last_update"],
            "status": self.checkpoint_data["status"],
            "phase_status": {
                phase: data["status"] 
                for phase, data in self.checkpoint_data["phases"].items()
            },
            "statistics": self.checkpoint_data["statistics"]
        }
    
    def repair_checkpoint(self) -> bool:
        """
        Attempt to repair corrupted checkpoint data.
        
        Returns:
            bool: True if repair was successful, False otherwise
        """
        if not self.checkpoint_data:
            logger.error("Cannot repair checkpoint: checkpoint not initialized")
            return False
            
        try:
            # Ensure essential fields exist
            self._repair_missing_fields()
            
            # Ensure all phases exist
            self._repair_missing_phases()
            
            # Save repaired checkpoint
            with FileLock(self.lock_file):
                self._write_checkpoint()
                
            logger.info("Checkpoint repair successful")
            return True
            
        except Exception as e:
            logger.error(f"Error repairing checkpoint: {str(e)}")
            return False
    
    def _repair_missing_fields(self) -> None:
        """
        Repair missing top-level fields in checkpoint data.
        """
        required_fields = [
            "scan_id", "domain", "start_time", "last_update", "status", 
            "phases", "statistics", "environment"
        ]
        
        for field in required_fields:
            if field not in self.checkpoint_data:
                logger.warning(f"Repairing missing field: {field}")
                self._add_missing_field(field)
    
    def _add_missing_field(self, field: str) -> None:
        """
        Add a missing field with default values.
        
        Args:
            field: Name of the field to add
        """
        if field == "scan_id":
            self.checkpoint_data["scan_id"] = self._generate_scan_id()
        elif field == "domain":
            self.checkpoint_data["domain"] = self.domain
        elif field == "start_time" or field == "last_update":
            self.checkpoint_data[field] = datetime.datetime.now().isoformat()
        elif field == "status":
            self.checkpoint_data["status"] = "in_progress"
        elif field == "phases":
            self.checkpoint_data["phases"] = self._create_default_phases()
        elif field == "statistics":
            self.checkpoint_data["statistics"] = self._create_default_statistics()
        elif field == "environment":
            self.checkpoint_data["environment"] = self._create_default_environment()
    
    def _create_default_phases(self) -> Dict[str, Dict[str, Any]]:
        """
        Create default phases structure.
        
        Returns:
            Dict[str, Dict[str, Any]]: Default phases structure
        """
        return {
            "subdomain_enumeration": {
                "status": "pending",
                "progress_percentage": 0,
                "results_count": 0
            },
            "alive_check": {
                "status": "pending",
                "progress_percentage": 0,
                "results_count": 0
            },
            "vulnerability_scan": {
                "status": "pending",
                "progress_percentage": 0,
                "results_count": 0
            }
        }
    
    def _create_default_statistics(self) -> Dict[str, int]:
        """
        Create default statistics structure.
        
        Returns:
            Dict[str, int]: Default statistics structure
        """
        return {
            "subdomains_found": 0,
            "alive_subdomains": 0,
            "vulnerabilities_found": 0
        }
    
    def _create_default_environment(self) -> Dict[str, Any]:
        """
        Create default environment structure.
        
        Returns:
            Dict[str, Any]: Default environment structure
        """
        return {
            "tool_versions": {},
            "templates_hash": ""
        }
    
    def _repair_missing_phases(self) -> None:
        """
        Repair missing phases in the phases field.
        """
        # Skip if phases field itself is missing (it will be added by _repair_missing_fields)
        if "phases" not in self.checkpoint_data:
            return
            
        # Ensure all required phases exist
        required_phases = ["subdomain_enumeration", "alive_check", "vulnerability_scan"]
        for phase in required_phases:
            if phase not in self.checkpoint_data["phases"]:
                logger.warning(f"Repairing missing phase: {phase}")
                self.checkpoint_data["phases"][phase] = {
                    "status": "pending",
                    "progress_percentage": 0,
                    "results_count": 0
                }
    
    def optimize_checkpoint(self) -> bool:
        """
        Optimize checkpoint file size by removing unnecessary data.
        
        Returns:
            bool: True if optimization was successful, False otherwise
        """
        if not self.checkpoint_data:
            logger.error("Cannot optimize checkpoint: checkpoint not initialized")
            return False
            
        try:
            # Remove unnecessary detailed data for completed phases
            for phase, data in self.checkpoint_data["phases"].items():
                if data["status"] == "completed" and "checkpoint" in data:
                    # Keep only essential info for completed phases
                    logger.debug(f"Optimizing data for completed phase: {phase}")
                    data.pop("checkpoint", None)
            
            # Save optimized checkpoint
            with FileLock(self.lock_file):
                self._write_checkpoint()
                
            # Get file size
            file_size = self.checkpoint_file.stat().st_size
            logger.info(f"Checkpoint optimized. Current size: {file_size/1024:.1f} KB")
            return True
            
        except Exception as e:
            logger.error(f"Error optimizing checkpoint: {str(e)}")
            return False
    
    def verify_checkpoint_integrity(self) -> Tuple[bool, List[str]]:
        """
        Verify checkpoint data integrity and consistency.
        
        Returns:
            Tuple[bool, List[str]]: (is_valid, list_of_issues)
        """
        if not self.checkpoint_data:
            logger.error("Cannot verify checkpoint: checkpoint not initialized")
            return False, ["Checkpoint not initialized"]
            
        issues = []
        
        # Verify essential fields
        required_fields = [
            "scan_id", "domain", "start_time", "last_update", "status", 
            "phases", "statistics", "environment"
        ]
        
        for field in required_fields:
            if field not in self.checkpoint_data:
                issues.append(f"Missing required field: {field}")
        
        # If essential structure is missing, can't continue
        if issues:
            return False, issues
        
        # Verify domain matches
        if self.checkpoint_data["domain"] != self.domain:
            issues.append(f"Domain mismatch: {self.checkpoint_data['domain']} (checkpoint) vs {self.domain} (current)")
        
        # Verify phases data
        required_phases = ["subdomain_enumeration", "alive_check", "vulnerability_scan"]
        for phase in required_phases:
            if phase not in self.checkpoint_data["phases"]:
                issues.append(f"Missing phase: {phase}")
            else:
                # Check phase data structure
                phase_data = self.checkpoint_data["phases"][phase]
                if "status" not in phase_data:
                    issues.append(f"Missing status in phase: {phase}")
                if "progress_percentage" not in phase_data:
                    issues.append(f"Missing progress percentage in phase: {phase}")
                if "results_count" not in phase_data:
                    issues.append(f"Missing results count in phase: {phase}")
        
        # Verify statistics
        required_stats = ["subdomains_found", "alive_subdomains", "vulnerabilities_found"]
        for stat in required_stats:
            if stat not in self.checkpoint_data["statistics"]:
                issues.append(f"Missing statistic: {stat}")
        
        # Verify environment data
        if "tool_versions" not in self.checkpoint_data["environment"]:
            issues.append("Missing tool versions in environment")
            
        is_valid = len(issues) == 0
        
        if is_valid:
            logger.info("Checkpoint integrity verification passed")
        else:
            logger.warning(f"Checkpoint integrity verification failed: {', '.join(issues)}")
        
        return is_valid, issues
    
    def cleanup_old_checkpoints(self, max_checkpoints: int = 5) -> bool:
        """
        Clean up old checkpoint files to save disk space.
        Only keeps the most recent checkpoint files.
        
        Args:
            max_checkpoints: Maximum number of checkpoint files to keep
            
        Returns:
            bool: True if cleanup was successful, False otherwise
        """
        try:
            # Get all checkpoint files
            checkpoint_files = list(self.checkpoint_dir.glob("scan_state_*.json"))
            
            if len(checkpoint_files) <= max_checkpoints:
                logger.debug(f"No cleanup needed. Only {len(checkpoint_files)} checkpoints exist.")
                return True
            
            # Sort files by modification time (newest first)
            checkpoint_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
            
            # Delete old files
            for old_file in checkpoint_files[max_checkpoints:]:
                logger.debug(f"Removing old checkpoint file: {old_file}")
                old_file.unlink()
            
            logger.info(f"Cleaned up old checkpoints. Kept {max_checkpoints} most recent files.")
            return True
            
        except Exception as e:
            logger.error(f"Error cleaning up old checkpoints: {str(e)}")
            return False
    
    def create_backup_checkpoint(self) -> bool:
        """
        Create a backup of the current checkpoint file.
        
        Returns:
            bool: True if backup was created successfully, False otherwise
        """
        if not self.checkpoint_data:
            logger.error("Cannot create backup: checkpoint not initialized")
            return False
            
        try:
            # Generate backup filename with timestamp
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = self.checkpoint_dir / f"scan_state_{timestamp}.json"
            
            # Copy current checkpoint to backup
            with FileLock(self.lock_file):
                if self.checkpoint_file.exists():
                    import shutil
                    shutil.copy2(self.checkpoint_file, backup_file)
                    logger.info(f"Created checkpoint backup: {backup_file}")
                    return True
                else:
                    logger.warning("Cannot create backup: checkpoint file does not exist")
                    return False
                
        except Exception as e:
            logger.error(f"Error creating checkpoint backup: {str(e)}")
            return False 