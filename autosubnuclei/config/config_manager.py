"""
Configuration manager for handling settings and credentials
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

class ConfigManager:
    def __init__(self):
        # Use root directory for config file
        self.config_dir = Path(__file__).parent.parent.parent  # Root workspace directory
        self.config_file = self.config_dir / "config.json"
        self._ensure_config_exists()

    def _ensure_config_exists(self) -> None:
        """
        Ensure config file exists with default values
        """
        if not self.config_file.exists():
            # Check if old config exists in config/ directory
            old_config_path = self.config_dir / "config" / "config.json"
            if old_config_path.exists():
                # Migrate config from old location
                try:
                    with open(old_config_path, 'r') as f:
                        config = json.load(f)
                    self.save_config(config)
                    logger.info(f"Migrated config from {old_config_path} to {self.config_file}")
                    return
                except Exception as e:
                    logger.warning(f"Failed to migrate old config: {str(e)}")
            
            # Create default config
            default_config = {
                "discord_webhook": "",
                "notifications_enabled": False,
                "default_severities": ["critical", "high", "medium", "low"],
                "default_output_dir": "results",
                "log_file": "autosubnuclei.log"
            }
            self.save_config(default_config)
            logger.info(f"Created default config at {self.config_file}")

    def load_config(self) -> Dict[str, Any]:
        """
        Load configuration from file
        """
        try:
            with open(self.config_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load config: {str(e)}")
            return {}

    def save_config(self, config: Dict[str, Any]) -> None:
        """
        Save configuration to file
        """
        try:
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to save config: {str(e)}")
            raise

    def update_config(self, updates: Dict[str, Any]) -> None:
        """
        Update configuration with new values
        """
        config = self.load_config()
        config.update(updates)
        self.save_config(config)

    def set_discord_webhook(self, webhook_url: str) -> None:
        """
        Set Discord webhook URL and enable notifications
        """
        self.update_config({
            "discord_webhook": webhook_url,
            "notifications_enabled": True
        })

    def get_discord_webhook(self) -> Optional[str]:
        """
        Get Discord webhook URL
        """
        config = self.load_config()
        return config.get("discord_webhook")

    def is_notifications_enabled(self) -> bool:
        """
        Check if notifications are enabled
        """
        config = self.load_config()
        return config.get("notifications_enabled", False)

    def disable_notifications(self) -> None:
        """
        Disable notifications
        """
        self.update_config({"notifications_enabled": False})

    def get_default_severities(self) -> List[str]:
        """
        Get default severity levels for scanning
        """
        config = self.load_config()
        return config.get("default_severities", ["critical", "high", "medium", "low"])

    def get_default_output_dir(self) -> str:
        """
        Get default output directory
        """
        config = self.load_config()
        return config.get("default_output_dir", "results")

    def get_log_file(self) -> str:
        """
        Get log file path
        """
        config = self.load_config()
        return config.get("log_file", "autosubnuclei.log") 