"""
Helper functions for logging and other utilities
"""

import os
import sys
import platform
import subprocess
import logging
import zipfile
import requests
import time
import random
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, Callable, TypeVar, Set, Iterator
from tqdm import tqdm
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import hashlib
import json

# Type variable for generic return type
T = TypeVar('T')

def retry_with_backoff(func: Callable[[], T], max_retries=3, base_delay=1, max_delay=60, initial_wait=0, backoff_factor=None) -> T:
    """
    Execute a function with exponential backoff retry logic.
    
    Args:
        func: Function to execute
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
        initial_wait: Initial wait before first attempt (seconds)
        backoff_factor: Alias for base_delay (for backward compatibility)
        
    Returns:
        The result of the function call
        
    Raises:
        The last exception encountered after all retries
    """
    logger = logging.getLogger(__name__)
    
    # Use backoff_factor if provided (for compatibility)
    if backoff_factor is not None:
        base_delay = backoff_factor
    
    # Wait initial period if specified
    if initial_wait > 0:
        time.sleep(initial_wait)
    
    retries = 0
    last_exception = None
    
    while retries <= max_retries:
        try:
            return func()
        except Exception as e:
            last_exception = e
            retries += 1
            
            if retries > max_retries:
                break
                
            # Calculate delay with exponential backoff and jitter
            delay = min(base_delay * (2 ** (retries - 1)) + random.uniform(0, 1), max_delay)
            
            logger.warning(f"Retry attempt {retries}/{max_retries} after {delay:.2f}s due to: {str(e)}")
            time.sleep(delay)
    
    # If we reach here, all retries failed
    raise last_exception

def setup_logging(log_file: Optional[Path] = None) -> None:
    """
    Configure logging with both file and console handlers
    """
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    formatter = logging.Formatter(log_format)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler if specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

def get_platform_info() -> Tuple[str, str]:
    """
    Get the current platform and architecture information
    """
    system = platform.system().lower()
    machine = platform.machine().lower()
    
    # Map machine types to download types
    arch_map = {
        'x86_64': 'amd64',
        'amd64': 'amd64',
        'i386': '386',
        'i686': '386',
        'arm64': 'arm64',
        'aarch64': 'arm64',
        'armv7l': 'arm',
        'armv6l': 'arm'
    }
    
    # Map OS names to download types
    os_map = {
        'windows': 'windows',
        'linux': 'linux',
        'darwin': 'darwin'
    }
    
    return os_map.get(system, "linux"), arch_map.get(machine, "amd64")

def create_requests_session() -> requests.Session:
    """
    Create a requests session with retry logic
    """
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[500, 502, 503, 504]
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

def download_file(url: str, output_path: Path) -> None:
    """
    Download a file with progress bar
    
    Args:
        url: URL to download from
        output_path: Path object where to save the file
    """
    logger = logging.getLogger(__name__)
    
    # Validate that output_path is a Path object
    if not isinstance(output_path, Path):
        raise TypeError(f"output_path must be a Path object, got {type(output_path).__name__}")
    
    try:
        session = create_requests_session()
        logger.debug(f"Downloading from {url} to {output_path}")
        
        # Ensure parent directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Download the file
        response = session.get(url, stream=True)
        response.raise_for_status()
        
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
                
        # Verify download
        if not output_path.exists():
            raise FileNotFoundError(f"Download failed: {output_path} not found after download")
        if output_path.stat().st_size == 0:
            raise ValueError(f"Download failed: {output_path} is empty (0 bytes)")
            
        logger.debug(f"Download completed: {output_path} ({output_path.stat().st_size} bytes)")
    except Exception as e:
        logger.error(f"Download failed from {url}: {str(e)}")
        # Clean up partial downloads
        if output_path.exists():
            output_path.unlink()
        raise

def extract_zip(zip_path: Path, extract_to: Path) -> None:
    """
    Extract a zip file
    """
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_to)

def validate_file(file_path: Path, step_name: str) -> None:
    """
    Validate if output file exists and has content
    """
    if not file_path.exists():
        raise FileNotFoundError(f"{step_name} failed to create output file")
    if file_path.stat().st_size == 0:
        raise ValueError(f"{step_name} produced empty results")

class DiskBackedSet:
    """
    A set-like object that stores items on disk to reduce memory usage.
    """
    def __init__(self, path: Path, cache_size: int = 1000):
        """
        Initialize a disk-backed set.
        
        Args:
            path: Path to the file to store the set items
            cache_size: Size of the in-memory cache for fast lookups
        """
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create empty file if it doesn't exist
        if not self.path.exists():
            with open(self.path, 'w'):
                pass
        
        # In-memory cache for fast membership tests
        self._cache = {}
        self._cache_size = cache_size
        self._size = None  # Lazy-loaded size
        
        # Load initial cache with a sample of items
        self._initialize_cache()
    
    def _initialize_cache(self) -> None:
        """
        Initialize the cache with a sample of existing items.
        """
        try:
            if self.path.exists() and self.path.stat().st_size > 0:
                with open(self.path, 'r') as f:
                    # Try to load cache_size items or all items if fewer
                    lines = []
                    for i, line in enumerate(f):
                        if i >= self._cache_size:
                            break
                        lines.append(line.strip())
                    
                    # Add to cache
                    for line in lines:
                        self._cache[line] = True
                        
                    logger.debug(f"Initialized DiskBackedSet cache with {len(self._cache)} items")
        except Exception as e:
            logger.warning(f"Failed to initialize cache: {str(e)}")
    
    def add(self, item: str) -> None:
        """
        Add an item to the set.
        
        Args:
            item: The item to add
        """
        # Check if the item is already in the set
        if self._in_cache(item) or self._in_file(item):
            return
        
        # Add to file
        with open(self.path, 'a') as f:
            f.write(f"{item}\n")
        
        # Add to cache
        self._add_to_cache(item)
        
        # Reset size cache
        self._size = None
    
    def update(self, items) -> None:
        """
        Add multiple items to the set.
        
        Args:
            items: Iterable of items to add
        """
        # For efficiency, we'll write all items at once
        to_add = []
        for item in items:
            if not (self._in_cache(item) or self._in_file(item)):
                to_add.append(item)
        
        if to_add:
            # Write all new items at once
            with open(self.path, 'a') as f:
                for item in to_add:
                    f.write(f"{item}\n")
                    self._add_to_cache(item)
            
            # Reset size cache
            self._size = None
    
    def _add_to_cache(self, item: str) -> None:
        """
        Add an item to the in-memory cache.
        
        Args:
            item: The item to add to the cache
        """
        # Maintain cache size
        if len(self._cache) >= self._cache_size:
            # Remove oldest item (first key in dict)
            self._cache.pop(next(iter(self._cache)))
        
        self._cache[item] = True
    
    def _in_cache(self, item: str) -> bool:
        """
        Check if an item is in the cache.
        
        Args:
            item: The item to check
            
        Returns:
            bool: True if the item is in the cache, False otherwise
        """
        return item in self._cache
    
    def _in_file(self, item: str) -> bool:
        """
        Check if an item is in the file.
        
        This is a slow operation and should be avoided when possible.
        
        Args:
            item: The item to check
            
        Returns:
            bool: True if the item is in the file, False otherwise
        """
        try:
            # Use grep-like approach for more efficient lookup
            with open(self.path, 'r') as f:
                return any(line.strip() == item for line in f)
        except Exception as e:
            logger.warning(f"Error checking if item is in file: {str(e)}")
            return False
    
    def __iter__(self) -> Iterator[str]:
        """
        Iterate over all items in the set.
        
        Returns:
            Iterator yielding each item in the set
        """
        try:
            with open(self.path, 'r') as f:
                for line in f:
                    yield line.strip()
        except Exception as e:
            logger.error(f"Error iterating over DiskBackedSet: {str(e)}")
            # Yield nothing on error
    
    def __len__(self) -> int:
        """
        Return the number of items in the set.
        
        Returns:
            int: The number of items in the set
        """
        if self._size is None:
            try:
                with open(self.path, 'r') as f:
                    self._size = sum(1 for _ in f)
            except Exception as e:
                logger.error(f"Error counting items in DiskBackedSet: {str(e)}")
                self._size = 0
        
        return self._size
    
    def clear(self) -> None:
        """
        Clear the set.
        """
        try:
            with open(self.path, 'w'):
                pass
            self._cache = {}
            self._size = 0
        except Exception as e:
            logger.error(f"Error clearing DiskBackedSet: {str(e)}")
    
    def to_file(self, output_path: Path) -> None:
        """
        Write the set to a new file.
        
        Args:
            output_path: Path to write the set to
        """
        try:
            if self.path.exists():
                import shutil
                shutil.copy(self.path, output_path)
            else:
                with open(output_path, 'w'):
                    pass
        except Exception as e:
            logger.error(f"Error writing DiskBackedSet to file: {str(e)}")
    
    @classmethod
    def from_iterable(cls, items, path: Path, cache_size: int = 1000) -> 'DiskBackedSet':
        """
        Create a DiskBackedSet from an iterable.
        
        Args:
            items: Iterable of items to add to the set
            path: Path to store the set
            cache_size: Size of the in-memory cache
            
        Returns:
            DiskBackedSet: A new DiskBackedSet containing the items
        """
        result = cls(path, cache_size)
        
        # Write all items directly to file
        with open(path, 'w') as f:
            for item in items:
                f.write(f"{item}\n")
        
        # Initialize cache
        result._initialize_cache()
        result._size = None
        
        return result 