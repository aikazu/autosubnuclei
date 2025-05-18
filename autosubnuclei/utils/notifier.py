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

    def send_subdomains_found(self, domain: str, subdomains: List[str], total: Optional[int] = None) -> None:
        """
        Send notification about found subdomains
        
        Args:
            domain: The domain being scanned
            subdomains: List of subdomains to include in the notification
            total: Optional total count of subdomains (used when only sending a sample)
        """
        if not self.config_manager.is_notifications_enabled():
            return

        count = total if total is not None else len(subdomains)
        sample_note = ""
        if total is not None and len(subdomains) < total:
            sample_note = f" (showing {len(subdomains)} sample)"
            
        message = f"🔍 Found {count} subdomains for {domain}{sample_note}:\n"
        # Limit the number of subdomains shown to avoid message size limits
        message += "\n".join(f"• {sub}" for sub in subdomains[:100])
        
        if len(subdomains) > 100:
            message += f"\n... and {len(subdomains) - 100} more"
            
        self._send_discord_message(message, "Subdomains Found")

    def send_alive_subdomains(self, domain: str, alive_subdomains: List[str], total: Optional[int] = None) -> None:
        """
        Send notification about alive subdomains
        
        Args:
            domain: The domain being scanned
            alive_subdomains: List of alive subdomains to include in the notification
            total: Optional total count of alive subdomains (used when only sending a sample)
        """
        if not self.config_manager.is_notifications_enabled():
            return

        count = total if total is not None else len(alive_subdomains)
        sample_note = ""
        if total is not None and len(alive_subdomains) < total:
            sample_note = f" (showing {len(alive_subdomains)} sample)"
            
        message = f"🌐 Found {count} alive subdomains for {domain}{sample_note}:\n"
        # Limit the number of subdomains shown to avoid message size limits
        message += "\n".join(f"• {sub}" for sub in alive_subdomains[:100])
        
        if len(alive_subdomains) > 100:
            message += f"\n... and {len(alive_subdomains) - 100} more"
            
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

    def send_error_notification(self, domain: str, error_message: str) -> None:
        """
        Send notification about scan error
        
        Args:
            domain: The domain being scanned
            error_message: Error message to include in the notification
        """
        if not self.config_manager.is_notifications_enabled():
            return
            
        message = f"❌ Error scanning domain {domain}:\n```\n{error_message}\n```"
        self._send_discord_message(message, "Scan Error") 