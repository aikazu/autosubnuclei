"""
Provides the ProgressMonitor class for CLI feedback during scans.
"""

import logging
import time
from datetime import datetime
from typing import TYPE_CHECKING

# To avoid circular import, use TYPE_CHECKING for SecurityScanner hint
if TYPE_CHECKING:
    from ..core.scanner import SecurityScanner

logger = logging.getLogger(__name__)

class ProgressMonitor:
    # Purpose: Monitor and display scan progress with simple status messages and timestamps.
    # Usage: monitor = ProgressMonitor(scanner_instance)
    #        monitor.update() / monitor.set_using_cache(...)
    """Monitor and display scan progress with simple status messages"""

    def __init__(self, scanner: 'SecurityScanner'):
        self.scanner = scanner
        self.last_status = ""
        self.last_message_time = 0
        # Define status messages centrally
        self.status_messages = {
            "initializing": "🚀 Initializing scan",
            "setting_up_tools": "🛠️ Verifying/Installing tools",
            "downloading_templates": "📥 Downloading/Verifying Nuclei templates",
            "discovering_subdomains": "📡 Discovering subdomains (subfinder)",
            "probing_subdomains": "🌐 Probing subdomains (httpx)",
            "scanning_vulnerabilities": "🔍 Scanning for vulnerabilities (nuclei)",
            "completed": "✅ Scan completed",
            "cancelled": "🛑 Scan cancelled",
            "error": "❌ Scan failed"
        }
        self.using_cache = False # Flag to indicate if cache was used

    def set_using_cache(self, tool_name: str):
        # Purpose: Indicate that cached results are being used for a specific tool/step.
        # Usage: monitor.set_using_cache("subfinder")
        """Call this when cached results are used for a step."""
        self.using_cache = True
        # Consistent timestamp and level format
        print(f"  {datetime.now().strftime('%H:%M:%S')} [CACHE] Using cached results for {tool_name}.")

    def update(self):
        # Purpose: Update the progress display based on the scanner's current state.
        # Usage: Called periodically by the monitoring task.
        """Update the progress display with simple status messages and timestamps"""
        try:
            # Get current state from the scanner
            current_status = self.scanner.scan_state.get("status", "")
            now_str = datetime.now().strftime('%H:%M:%S')

            if not current_status:
                return # Nothing to report yet

            # Print message only if status changes (to avoid spamming the console)
            if self.last_status != current_status:
                message = self.status_messages.get(current_status, f"⏳ {current_status.replace('_', ' ').title()}")
                status_level = "INFO" # Default level

                # Add specific counts/details if available
                if current_status == "discovering_subdomains":
                    subdomains = self.scanner.scan_state.get("subdomains", 0)
                    if subdomains > 0:
                        message = f"{message} (Found {subdomains})"
                elif current_status == "probing_subdomains":
                    subdomains = self.scanner.scan_state.get("subdomains", 0)
                    alive = self.scanner.scan_state.get("alive_subdomains", 0)
                    if subdomains > 0:
                        message = f"{message} ({alive}/{subdomains} alive)"
                elif current_status == "scanning_vulnerabilities":
                    alive = self.scanner.scan_state.get("alive_subdomains", 0)
                    if alive > 0:
                        message = f"{message} (Scanning {alive} targets)"
                elif current_status == "completed":
                    duration = self.scanner.scan_state.get("duration", 0)
                    vulns = self.scanner.scan_state.get("vulnerabilities", 0)
                    duration_str = f"{duration:.1f}s" if duration < 60 else f"{duration/60:.1f}m"
                    message = f"{message} in {duration_str}. Found {vulns} potential vulnerabilities."
                    status_level = "SUCCESS"
                elif current_status == "error":
                    error_msg = self.scanner.scan_state.get("error", "Unknown error")
                    message = f"{message}: {error_msg}"
                    status_level = "ERROR"
                elif current_status == "cancelled":
                     message = f"{message}."
                     status_level = "WARN"

                # Format and print the final message
                # Use status_level for potential coloring or prefixing later
                print(f"  {now_str} [{status_level}] {message}")

                # Update tracking variables
                self.last_status = current_status
                self.last_message_time = time.time() # Keep track of last message time

        except Exception as e:
            # Log errors in the progress monitor itself
            logger.error(f"Progress monitoring error: {e}", exc_info=True)
            # Avoid printing directly to console to prevent clutter/confusion

# Ensure no trailing characters or placeholders 