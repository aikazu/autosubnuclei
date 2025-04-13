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
                "notifications": {
                    "enabled": False,
                    "discord": {
                        "enabled": False,
                        "webhook_url": ""
                    },
                    "slack": {
                        "enabled": False,
                        "webhook_url": ""
                    },
                    "telegram": {
                        "enabled": False,
                        "bot_token": "",
                        "chat_id": ""
                    }
                },
                "default_severities": ["critical", "high", "medium", "low"],
                "default_output_dir": "results",
                "log_file": "autosubnuclei.log"
            }
            
            # Add backward compatibility for older config
            if hasattr(self, 'discord_webhook') and self.discord_webhook:
                default_config["notifications"]["discord"]["webhook_url"] = self.discord_webhook
                default_config["notifications"]["discord"]["enabled"] = True
                default_config["notifications"]["enabled"] = True
                
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
        config = self.load_config()
        
        # Create notifications section if it doesn't exist
        if "notifications" not in config:
            config["notifications"] = {
                "enabled": True,
                "discord": {"enabled": False, "webhook_url": ""},
                "slack": {"enabled": False, "webhook_url": ""},
                "telegram": {"enabled": False, "bot_token": "", "chat_id": ""}
            }
            
        # Update Discord configuration
        config["notifications"]["enabled"] = True
        config["notifications"]["discord"] = {
            "enabled": True,
            "webhook_url": webhook_url
        }
        
        # For backward compatibility
        config["discord_webhook"] = webhook_url
        
        self.save_config(config)
        
    def set_slack_webhook(self, webhook_url: str) -> None:
        """
        Set Slack webhook URL and enable notifications
        """
        config = self.load_config()
        
        # Create notifications section if it doesn't exist
        if "notifications" not in config:
            config["notifications"] = {
                "enabled": True,
                "discord": {"enabled": False, "webhook_url": ""},
                "slack": {"enabled": False, "webhook_url": ""},
                "telegram": {"enabled": False, "bot_token": "", "chat_id": ""}
            }
            
        # Update Slack configuration
        config["notifications"]["enabled"] = True
        config["notifications"]["slack"] = {
            "enabled": True,
            "webhook_url": webhook_url
        }
        
        self.save_config(config)
        
    def set_telegram_bot(self, bot_token: str, chat_id: str) -> None:
        """
        Set Telegram bot token and chat ID and enable notifications
        """
        config = self.load_config()
        
        # Create notifications section if it doesn't exist
        if "notifications" not in config:
            config["notifications"] = {
                "enabled": True,
                "discord": {"enabled": False, "webhook_url": ""},
                "slack": {"enabled": False, "webhook_url": ""},
                "telegram": {"enabled": False, "bot_token": "", "chat_id": ""}
            }
            
        # Update Telegram configuration
        config["notifications"]["enabled"] = True
        config["notifications"]["telegram"] = {
            "enabled": True,
            "bot_token": bot_token,
            "chat_id": chat_id
        }
        
        self.save_config(config)

    def get_discord_webhook(self) -> Optional[str]:
        """
        Get Discord webhook URL
        """
        config = self.load_config()
        
        # Try new config structure first
        if "notifications" in config and "discord" in config["notifications"]:
            return config["notifications"]["discord"].get("webhook_url")
            
        # Fallback to legacy config
        return config.get("discord_webhook")
        
    def get_slack_webhook(self) -> Optional[str]:
        """
        Get Slack webhook URL
        """
        config = self.load_config()
        
        if "notifications" in config and "slack" in config["notifications"]:
            return config["notifications"]["slack"].get("webhook_url")
            
        return None
        
    def get_telegram_config(self) -> Dict[str, str]:
        """
        Get Telegram configuration (bot token and chat ID)
        """
        config = self.load_config()
        
        if "notifications" in config and "telegram" in config["notifications"]:
            telegram_config = config["notifications"]["telegram"]
            return {
                "bot_token": telegram_config.get("bot_token", ""),
                "chat_id": telegram_config.get("chat_id", "")
            }
            
        return {"bot_token": "", "chat_id": ""}

    def is_notifications_enabled(self) -> bool:
        """
        Check if notifications are enabled
        """
        config = self.load_config()
        
        # Try new config structure first
        if "notifications" in config:
            return config["notifications"].get("enabled", False)
            
        # Fallback to legacy config
        return config.get("notifications_enabled", False)
        
    def is_discord_enabled(self) -> bool:
        """
        Check if Discord notifications are enabled
        """
        config = self.load_config()
        
        if "notifications" in config and "discord" in config["notifications"]:
            return config["notifications"]["discord"].get("enabled", False)
            
        # Fallback to legacy config
        return bool(config.get("discord_webhook"))
        
    def is_slack_enabled(self) -> bool:
        """
        Check if Slack notifications are enabled
        """
        config = self.load_config()
        
        if "notifications" in config and "slack" in config["notifications"]:
            return config["notifications"]["slack"].get("enabled", False)
            
        return False
        
    def is_telegram_enabled(self) -> bool:
        """
        Check if Telegram notifications are enabled
        """
        config = self.load_config()
        
        if "notifications" in config and "telegram" in config["notifications"]:
            return config["notifications"]["telegram"].get("enabled", False)
            
        return False

    def disable_notifications(self) -> None:
        """
        Disable all notifications
        """
        config = self.load_config()
        
        if "notifications" in config:
            config["notifications"]["enabled"] = False
        else:
            config["notifications"] = {"enabled": False}
            
        # For backward compatibility
        config["notifications_enabled"] = False
        
        self.save_config(config)

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

    def get_config(self) -> Dict[str, Any]:
        """
        Get the entire configuration dictionary
        
        Returns:
            Dict[str, Any]: Complete configuration dictionary
        """
        config = self.load_config()
        
        # Apply defaults from settings if needed
        from autosubnuclei.config.settings import DEFAULT_CONFIG
        
        # Make sure nuclei template filters exist
        if "nuclei_template_filters" not in config:
            config["nuclei_template_filters"] = DEFAULT_CONFIG["nuclei_template_filters"]
            
        # Make sure nuclei optimization exists
        if "nuclei_optimization" not in config:
            config["nuclei_optimization"] = DEFAULT_CONFIG["nuclei_optimization"]
            
        return config 