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
        
        # Get notification URLs and settings
        self.discord_webhook = self.config_manager.get_discord_webhook()
        self.slack_webhook = self.config_manager.get_slack_webhook()
        self.telegram_config = self.config_manager.get_telegram_config()
        
        # Check which notification channels are enabled
        self.discord_enabled = self.config_manager.is_discord_enabled()
        self.slack_enabled = self.config_manager.is_slack_enabled()
        self.telegram_enabled = self.config_manager.is_telegram_enabled()

    def _send_discord_message(self, content: str, title: Optional[str] = None) -> bool:
        """
        Send a message to Discord webhook
        """
        if not self.discord_webhook or not self.discord_enabled:
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
                self.discord_webhook,
                data=json.dumps(data),
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Failed to send Discord notification: {str(e)}")
            return False
            
    def _send_slack_message(self, content: str, title: Optional[str] = None) -> bool:
        """
        Send a message to Slack webhook
        """
        if not self.slack_webhook or not self.slack_enabled:
            return False

        try:
            data = {
                "text": content
            }

            if title:
                data["blocks"] = [
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": title
                        }
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": content
                        }
                    }
                ]

            response = requests.post(
                self.slack_webhook,
                data=json.dumps(data),
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Failed to send Slack notification: {str(e)}")
            return False
            
    def _send_telegram_message(self, content: str, title: Optional[str] = None) -> bool:
        """
        Send a message to Telegram chat
        """
        if not self.telegram_config.get("bot_token") or not self.telegram_config.get("chat_id") or not self.telegram_enabled:
            return False

        try:
            message = content
            if title:
                message = f"*{title}*\n\n{content}"
                
            data = {
                "chat_id": self.telegram_config["chat_id"],
                "text": message,
                "parse_mode": "Markdown"
            }

            response = requests.post(
                f"https://api.telegram.org/bot{self.telegram_config['bot_token']}/sendMessage",
                data=data
            )
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Failed to send Telegram notification: {str(e)}")
            return False
            
    def _send_notification(self, content: str, title: Optional[str] = None) -> None:
        """
        Send notification to all enabled channels
        """
        if not self.config_manager.is_notifications_enabled():
            return
            
        # Send to all enabled channels
        if self.discord_enabled:
            self._send_discord_message(content, title)
            
        if self.slack_enabled:
            self._send_slack_message(content, title)
            
        if self.telegram_enabled:
            self._send_telegram_message(content, title)

    def send_scan_start(self, domain: str) -> None:
        """
        Send notification about scan start
        """
        message = f"🚀 Starting security scan for domain: {domain}"
        self._send_notification(message, "Scan Started")

    def send_subdomains_found(self, domain: str, subdomains: List[str]) -> None:
        """
        Send notification about found subdomains
        """
        message = f"🔍 Found {len(subdomains)} subdomains for {domain}:\n"
        
        # Limit the number of subdomains to display to avoid message size limits
        displayed_subdomains = subdomains[:20]
        message += "\n".join(f"• {sub}" for sub in displayed_subdomains)
        
        if len(subdomains) > 20:
            message += f"\n... and {len(subdomains) - 20} more"
            
        self._send_notification(message, "Subdomains Found")

    def send_alive_subdomains(self, domain: str, alive_subdomains: List[str]) -> None:
        """
        Send notification about alive subdomains
        """
        message = f"🌐 Found {len(alive_subdomains)} alive subdomains for {domain}:\n"
        
        # Limit the number of subdomains to display
        displayed_subdomains = alive_subdomains[:20]
        message += "\n".join(f"• {sub}" for sub in displayed_subdomains)
        
        if len(alive_subdomains) > 20:
            message += f"\n... and {len(alive_subdomains) - 20} more"
            
        self._send_notification(message, "Alive Subdomains")

    def send_scan_results(self, domain: str, results_file: Path) -> None:
        """
        Send notification about scan results
        """
        try:
            with open(results_file, 'r') as f:
                results = f.read()

            if results:
                # Limit the results to prevent message size limits
                if len(results) > 1500:
                    results = results[:1500] + "...\n(truncated, see full results in output file)"
                
                message = f"📊 Scan results for {domain}:\n```\n{results}\n```"
                self._send_notification(message, "Scan Results")
            else:
                message = f"✅ No vulnerabilities found for {domain}"
                self._send_notification(message, "Scan Completed")
        except Exception as e:
            logger.error(f"Failed to read results file: {str(e)}")

    def send_scan_complete(self, domain: str) -> None:
        """
        Send notification about scan completion
        """
        message = f"✅ Scan completed for domain: {domain}"
        self._send_notification(message, "Scan Completed")

    def send_cancellation_notification(self, domain: str, reason: str = "User cancelled") -> None:
        """
        Send a cancellation notification
        """
        message = f"🚫 Scan cancelled for {domain}\nReason: {reason}"
        self._send_notification(message, "Scan Cancelled") 