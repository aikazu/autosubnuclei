"""
Configuration settings and validation functions
"""

import re
from pathlib import Path
from typing import List
from urllib.parse import urlparse

# Default configuration
NUCLEI_CONFIG = {
    "default_severities": ["critical", "high", "medium"],
    "valid_severities": ["critical", "high", "medium", "low", "info"]
}

def validate_domain(domain: str) -> bool:
    """
    Validate domain format - supports both raw domains and URLs
    """
    # Handle URLs by extracting domain
    if domain.startswith('http://') or domain.startswith('https://'):
        parsed = urlparse(domain)
        domain = parsed.netloc
    
    domain_regex = r'^([a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$'
    return bool(re.match(domain_regex, domain))

def validate_severities(severities: List[str]) -> bool:
    """
    Validate severity levels
    """
    return all(severity in NUCLEI_CONFIG["valid_severities"] for severity in severities)

def validate_output_dir(output_dir: Path) -> bool:
    """
    Validate and create output directory if it doesn't exist
    """
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        return True
    except Exception:
        return False 