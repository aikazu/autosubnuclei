"""
Configuration manager for handling settings and credentials
"""

import json
import os
from pathlib import Path
from typing import Optional, Dict

class ConfigManager:
    def __init__(self, config_dir: Optional[Path] = None):
        self.config_dir = config_dir or Path.home() / ".autosubnuclei"
        self.config_file = self.config_dir / "config.json"
        self.config = self._load_config()

    def _load_config(self) -> Dict:
        """
        Load configuration from file or create default
        """
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        if not self.config_file.exists():
            return {
                "discord_webhook": None,
                "notifications_enabled": False
            }
        
        try:
            with open(self.config_file, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {
                "discord_webhook": None,
                "notifications_enabled": False
            }

    def _save_config(self) -> None:
        """
        Save configuration to file
        """
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=4)

    def set_discord_webhook(self, webhook_url: str) -> None:
        """
        Set Discord webhook URL
        """
        self.config["discord_webhook"] = webhook_url
        self.config["notifications_enabled"] = True
        self._save_config()

    def get_discord_webhook(self) -> Optional[str]:
        """
        Get Discord webhook URL
        """
        return self.config.get("discord_webhook")

    def is_notifications_enabled(self) -> bool:
        """
        Check if notifications are enabled
        """
        return self.config.get("notifications_enabled", False)

    def disable_notifications(self) -> None:
        """
        Disable notifications
        """
        self.config["notifications_enabled"] = False
        self._save_config() 