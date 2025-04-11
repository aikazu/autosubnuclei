"""
Notification manager for sending alerts and updates
"""

import json
import logging
import requests
from typing import Optional, Dict, List
from pathlib import Path

from autosubnuclei.config.config_manager import ConfigManager

logger = logging.getLogger(__name__)

class Notifier:
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self.webhook_url = self.config_manager.get_discord_webhook()

    def _send_discord_message(self, content: str, title: Optional[str] = None) -> bool:
        """
        Send a message to Discord webhook
        """
        if not self.webhook_url:
            return False

        try:
            data = {
                "content": content,
                "embeds": []
            }

            if title:
                data["embeds"].append({
                    "title": title,
                    "color": 0x00ff00  # Green color
                })

            response = requests.post(
                self.webhook_url,
                data=json.dumps(data),
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Failed to send Discord notification: {str(e)}")
            return False

    def send_scan_start(self, domain: str) -> None:
        """
        Send notification about scan start
        """
        if not self.config_manager.is_notifications_enabled():
            return

        message = f"🚀 Starting security scan for domain: {domain}"
        self._send_discord_message(message, "Scan Started")

    def send_subdomains_found(self, domain: str, subdomains: List[str]) -> None:
        """
        Send notification about found subdomains
        """
        if not self.config_manager.is_notifications_enabled():
            return

        message = f"🔍 Found {len(subdomains)} subdomains for {domain}:\n"
        message += "\n".join(f"• {sub}" for sub in subdomains)
        self._send_discord_message(message, "Subdomains Found")

    def send_alive_subdomains(self, domain: str, alive_subdomains: List[str]) -> None:
        """
        Send notification about alive subdomains
        """
        if not self.config_manager.is_notifications_enabled():
            return

        message = f"🌐 Found {len(alive_subdomains)} alive subdomains for {domain}:\n"
        message += "\n".join(f"• {sub}" for sub in alive_subdomains)
        self._send_discord_message(message, "Alive Subdomains")

    def send_scan_results(self, domain: str, results_file: Path) -> None:
        """
        Send notification about scan results
        """
        if not self.config_manager.is_notifications_enabled():
            return

        try:
            with open(results_file, 'r') as f:
                results = f.read()

            if results:
                message = f"📊 Scan results for {domain}:\n```\n{results}\n```"
                self._send_discord_message(message, "Scan Results")
            else:
                message = f"✅ No vulnerabilities found for {domain}"
                self._send_discord_message(message, "Scan Completed")
        except Exception as e:
            logger.error(f"Failed to read results file: {str(e)}")

    def send_scan_complete(self, domain: str) -> None:
        """
        Send notification about scan completion
        """
        if not self.config_manager.is_notifications_enabled():
            return

        message = f"✅ Scan completed for domain: {domain}"
        self._send_discord_message(message, "Scan Completed")

    def send_cancellation_notification(self, domain: str, reason: str = "User cancelled") -> None:
        """
        Send a cancellation notification
        """
        message = f"🚫 Scan cancelled for {domain}\nReason: {reason}"
        self._send_discord_message(message, "Scan Cancelled") 