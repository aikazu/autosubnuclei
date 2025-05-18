"""
Configuration manager for handling settings and credentials
"""

import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

class ConfigManager:
    def __init__(self, config_path=None):
        """
        Initialize the ConfigManager with a specified or default config path.
        
        Args:
            config_path (str or Path, optional): Path to the config file.
                If not provided, will search in standard locations.
        """
        # If path specified, use it directly
        if config_path:
            self.config_file = Path(config_path).resolve()
            self.config_dir = self.config_file.parent
        else:
            # Try to find config in various locations
            self.config_file = self._find_config_file()
            self.config_dir = self.config_file.parent
            
        self._ensure_config_exists()

    def _find_config_file(self):
        """
        Find the configuration file in various possible locations.
        
        Returns:
            Path: Resolved path to the config file (may not exist yet)
        """
        # Possible locations in priority order
        possible_locations = [
            # 1. Explicitly defined environment variable
            os.environ.get("AUTOSUBNUCLEI_CONFIG"),
            
            # 2. In the same directory as the executing script
            self._get_script_directory() / "config.json",
            
            # 3. Root workspace directory
            Path.cwd() / "config.json",
            
            # 4. In config subdirectory of workspace
            Path.cwd() / "config" / "config.json",
            
            # 5. Application directory (relative to module path)
            Path(__file__).parent.parent.parent / "config.json",
            
            # 6. In user's home directory
            Path.home() / ".autosubnuclei" / "config.json",
            
            # 7. In system config directory (platform specific)
            self._get_system_config_dir() / "autosubnuclei" / "config.json"
        ]
        
        # Filter out None values (from environment variable)
        possible_locations = [loc for loc in possible_locations if loc is not None]
        
        # Try each location
        for loc in possible_locations:
            if isinstance(loc, Path) and loc.exists():
                logger.debug(f"Found existing config file at: {loc}")
                return loc
        
        # Default to user's home directory if no config found
        default_location = Path.home() / ".autosubnuclei" / "config.json"
        logger.debug(f"Using default config location: {default_location}")
        return default_location

    def _get_system_config_dir(self) -> Path:
        """
        Get the system configuration directory based on the current platform.
        
        Returns:
            Path: System configuration directory
        """
        if sys.platform == "win32":
            # Windows: Use %APPDATA% or fall back to %USERPROFILE%\AppData\Roaming
            appdata = os.environ.get("APPDATA")
            if appdata:
                return Path(appdata)
            return Path.home() / "AppData" / "Roaming"
        elif sys.platform == "darwin":
            # macOS: Use ~/Library/Application Support
            return Path.home() / "Library" / "Application Support"
        else:
            # Linux/Unix: Use XDG_CONFIG_HOME or ~/.config
            xdg_config = os.environ.get("XDG_CONFIG_HOME")
            if xdg_config:
                return Path(xdg_config)
            return Path.home() / ".config"

    def _get_script_directory(self) -> Path:
        """
        Get the directory of the executing script, handling different execution contexts.
        
        Returns:
            Path: Directory of the executing script
        """
        try:
            # If running as a script
            if hasattr(sys, 'argv') and len(sys.argv) > 0 and sys.argv[0]:
                script_path = Path(sys.argv[0]).resolve()
                if script_path.exists():
                    return script_path.parent
        except Exception as e:
            logger.debug(f"Error determining script directory: {str(e)}")
        
        # Fall back to current working directory
        return Path.cwd()

    def _ensure_config_exists(self) -> None:
        """
        Ensure config file exists with default values
        """
        if not self.config_file.exists():
            # Make sure the directory exists
            self.config_dir.mkdir(parents=True, exist_ok=True)
            
            # Check for configs in other locations we might want to migrate
            old_configs = [
                Path(__file__).parent.parent.parent / "config" / "config.json",
                Path.cwd() / "config" / "config.json"
            ]
            
            for old_config_path in old_configs:
                if old_config_path.exists():
                    # Migrate config from old location
                    try:
                        with open(old_config_path, 'r') as f:
                            config = json.load(f)
                        self.save_config(config)
                        logger.info(f"Migrated config from {old_config_path} to {self.config_file}")
                        return
                    except Exception as e:
                        logger.warning(f"Failed to migrate old config from {old_config_path}: {str(e)}")
            
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
            logger.error(f"Failed to load config from {self.config_file}: {str(e)}")
            # If loading fails, try to create a new default config
            try:
                self._ensure_config_exists()
                # Try loading again
                with open(self.config_file, 'r') as f:
                    return json.load(f)
            except Exception as nested_e:
                logger.error(f"Failed to create and load default config: {str(nested_e)}")
                return {}

    def save_config(self, config: Dict[str, Any]) -> None:
        """
        Save configuration to file
        """
        try:
            # Ensure directory exists
            self.config_dir.mkdir(parents=True, exist_ok=True)
            
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=4)
                
            logger.debug(f"Config saved to {self.config_file}")
        except Exception as e:
            logger.error(f"Failed to save config to {self.config_file}: {str(e)}")
            raise

    def update_config(self, updates: Dict[str, Any]) -> None:
        """
        Update configuration with new values
        """
        config = self.load_config()
        config.update(updates)
        self.save_config(config)

    def get_config_path(self) -> Path:
        """
        Get the path to the current config file
        
        Returns:
            Path: Path to the config file
        """
        return self.config_file

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