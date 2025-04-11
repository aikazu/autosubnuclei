import platform
import logging
from typing import Optional, Dict, Any
from pathlib import Path
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_os() -> str:
    """Returns the operating system name."""
    return platform.system().lower()

def get_architecture() -> str:
    """Returns the system architecture."""
    machine = platform.machine().lower()
    if machine in ("x86_64", "amd64"):
        return "amd64"
    elif machine in ("arm64", "aarch64"):
        return "arm64"
    else:
        raise ValueError(f"Unsupported architecture: {machine}")

def create_requests_session() -> requests.Session:
    """Create a requests session with retry logic."""
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[500, 502, 503, 504]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session

def get_zip_url(release_info: Dict[str, Any]) -> str:
    """Extracts the download URL for the appropriate zip asset from the release info."""
    os_name = get_os()
    arch = get_architecture()
    
    for asset in release_info.get("assets", []):
        asset_name = asset["name"].lower()
        if os_name in asset_name and arch in asset_name and asset_name.endswith(".zip"):
            return asset["browser_download_url"]
    raise ValueError(f"No {os_name} {arch} zip asset found in release {release_info['tag_name']}")

def get_latest_release_url(binary: str, api_url: str) -> str:
    """Fetches the latest release info for a given binary from GitHub."""
    session = create_requests_session()
    try:
        response = session.get(api_url.format(binary=binary))
        response.raise_for_status()
        return get_zip_url(response.json())
    except requests.exceptions.RequestException as err:
        logger.error(f"Error fetching release info for {binary}: {err}")
        raise

def format_discord_message(data: str, title: str, max_length: int = 2000) -> str:
    """Format message for Discord with length limit."""
    max_content_length = max_length - len(title) - 100
    if len(data) > max_content_length:
        data = data[:max_content_length] + "\n... (truncated)"
    return f"## {title}\n{data}"

def validate_file(file_path: Path, step_name: str) -> None:
    """Validates if output file exists and has content."""
    if not file_path.exists():
        raise FileNotFoundError(f"{step_name} failed to create output file")
    if file_path.stat().st_size == 0:
        raise ValueError(f"{step_name} produced empty results")

def setup_logging(log_file: Optional[Path] = None) -> None:
    """Configure logging with optional file output."""
    handlers = [logging.StreamHandler()]
    if log_file:
        handlers.append(logging.FileHandler(log_file))
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=handlers
    ) 