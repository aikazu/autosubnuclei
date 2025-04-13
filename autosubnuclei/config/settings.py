"""
Configuration settings and validation functions
"""

import re
import os
from pathlib import Path
from typing import List, Dict, Any

# Default paths
DEFAULT_CONFIG_PATH = Path.home() / ".autosubnuclei" / "config.json"
DEFAULT_OUTPUT_DIR = Path.home() / ".autosubnuclei" / "output"
DEFAULT_TEMPLATES_DIR = Path.home() / ".autosubnuclei" / "templates"

# Default settings
DEFAULT_CONFIG: Dict[str, Any] = {
    "output_dir": str(DEFAULT_OUTPUT_DIR),
    "templates_dir": str(DEFAULT_TEMPLATES_DIR),
    "severities": ["critical", "high", "medium", "low"],
    "concurrency": os.cpu_count() or 4,
    "auto_update": True,
    "notifications": {
        "enabled": False,
        "webhook_url": "",
        "slack_enabled": False,
        "slack_webhook": "",
        "discord_enabled": False,
        "discord_webhook": "",
        "telegram_enabled": False,
        "telegram_bot_token": "",
        "telegram_chat_id": ""
    },
    "nuclei_template_filters": {
        "exclude_tags": [
            "fuzz",
            "dos",
            "intrusive"
        ],
        "include_tags": [],
        "exclude_templates": [],
        "use_automated_selection": True,
        "template_severity_mapping": {
            "quick": ["critical", "high"],
            "medium": ["critical", "high", "medium"],
            "full": ["critical", "high", "medium", "low", "info"]
        }
    },
    "nuclei_optimization": {
        "timeout": 5,
        "retries": 2,
        "rate_limit": 150,
        "bulk_size": 25,
        "concurrency": 25
    }
}

def validate_domain(domain: str) -> bool:
    """
    Validate domain format
    """
    domain_regex = r'^([a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$'
    return bool(re.match(domain_regex, domain))

def validate_severities(severities: List[str]) -> bool:
    """
    Validate severity levels
    """
    return all(severity in DEFAULT_CONFIG["severities"] for severity in severities)

def validate_output_dir(output_dir: Path) -> bool:
    """
    Validate and create output directory if it doesn't exist
    """
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        return True
    except Exception:
        return False 