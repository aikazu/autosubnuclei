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
from typing import Optional, Dict, Any, Tuple, Callable, TypeVar
from tqdm import tqdm
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Type variable for generic return type
T = TypeVar('T')

def retry_with_backoff(func: Callable[[], T], max_retries=3, base_delay=1, max_delay=60) -> T:
    """
    Execute a function with exponential backoff retry logic.
    
    Args:
        func: Function to execute
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
        
    Returns:
        The result of the function call
        
    Raises:
        The last exception encountered after all retries
    """
    logger = logging.getLogger(__name__)
    
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