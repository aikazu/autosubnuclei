from pathlib import Path
from typing import Dict, List
import os

# Constants
GITHUB_API_URL = "https://api.github.com/repos/projectdiscovery/{binary}/releases/latest"
DISCORD_MESSAGE_LIMIT = 2000
SCRIPT_DIR = Path(__file__).parent.parent.resolve()
BIN_DIR = SCRIPT_DIR / "bin"

# Binary configurations
BINARIES = {
    "subfinder": {
        "name": "subfinder",
        "required": True,
        "default_args": ["-silent"]
    },
    "httpx": {
        "name": "httpx",
        "required": True,
        "default_args": ["-silent"]
    },
    "nuclei": {
        "name": "nuclei",
        "required": True,
        "default_args": ["-silent"]
    },
    "notify": {
        "name": "notify",
        "required": False,
        "default_args": ["-silent"]
    }
}

# Nuclei configuration
NUCLEI_CONFIG = {
    "default_severities": ["critical", "high", "medium", "low"],
    "default_tags": ["dast", "cve", "misconfig", "oast", "xss"],
    "rate_limit": 10
}

# Validation functions
def validate_domain(domain: str) -> bool:
    """Validate domain format."""
    if not domain or len(domain) > 253:
        return False
    parts = domain.split('.')
    if len(parts) < 2:
        return False
    return all(part.isalnum() or '-' in part for part in parts)

def validate_severities(severities: List[str]) -> bool:
    """Validate nuclei severity levels."""
    valid_severities = {"critical", "high", "medium", "low", "info"}
    return all(sev.lower() in valid_severities for sev in severities)

def validate_output_dir(path: Path) -> bool:
    """Validate output directory."""
    try:
        path.mkdir(parents=True, exist_ok=True)
        return True
    except Exception:
        return False

def get_environment_variables() -> Dict[str, str]:
    """Get required environment variables."""
    return {
        "DISCORD_USERNAME": os.environ.get("DISCORD_USERNAME"),
        "DISCORD_WEBHOOK_URL": os.environ.get("DISCORD_WEBHOOK_URL")
    } 