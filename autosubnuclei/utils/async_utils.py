"""
Asyncio helper functions for running scans with progress monitoring.
"""

import asyncio
import logging
from typing import List, TYPE_CHECKING

# Avoid circular imports with type checking
if TYPE_CHECKING:
    from ..core.scanner import SecurityScanner
    from .progress import ProgressMonitor

logger = logging.getLogger(__name__)

async def run_scan_with_progress(scanner: 'SecurityScanner', severities: List[str], notify: bool, progress_monitor: 'ProgressMonitor') -> None:
    # Purpose: Run the core scanner.scan method while concurrently monitoring progress.
    # Usage: await run_scan_with_progress(scanner_instance, ["high"], True, monitor_instance)
    """Run the scan with progress monitoring"""
    # Start the progress monitoring task in the background
    monitoring_task = asyncio.create_task(monitor_progress(progress_monitor))
    logger.debug("Progress monitoring task started.")

    try:
        # Run the main scanning task
        logger.info("Starting core scan execution...")
        await scanner.scan(severities=severities, notify=notify)
        logger.info("Core scan execution finished.")
    except Exception as e:
        # Log and ensure the error state is set in the scanner if an exception occurs
        logger.error(f"Exception during scanner.scan: {e}", exc_info=True)
        if hasattr(scanner, 'scan_state'): # Check if scan_state exists
            scanner.scan_state["status"] = "error"
            scanner.scan_state["error"] = str(e)
        # Wait briefly to allow the monitor to potentially update with the error status
        await asyncio.sleep(0.1)
        raise # Re-raise the exception to be handled by the caller
    finally:
        # Ensure monitoring task is always cancelled when scan finishes or errors out
        if monitoring_task and not monitoring_task.done():
            logger.debug("Cancelling progress monitoring task...")
            monitoring_task.cancel()
            try:
                await monitoring_task # Wait for cancellation to complete
                logger.debug("Progress monitoring task cancelled successfully.")
            except asyncio.CancelledError:
                logger.debug("Progress monitoring task cancellation confirmed.")
            except Exception as e_cancel:
                # Log if there's an error during cancellation itself
                logger.error(f"Error awaiting cancelled monitor task: {e_cancel}", exc_info=True)


async def monitor_progress(progress_monitor: 'ProgressMonitor') -> None:
    # Purpose: Periodically call the progress_monitor's update method to display status.
    # Usage: asyncio.create_task(monitor_progress(monitor_instance))
    """Monitor and display progress periodically"""
    try:
        while True:
            progress_monitor.update() # Call the update method on the monitor instance
            await asyncio.sleep(1)  # Check for updates every second
    except asyncio.CancelledError:
        # This is expected when the task is cancelled, just exit gracefully
        logger.debug("Monitor progress task cancelled as expected.")
        pass
    except Exception as e:
        # Log any unexpected errors during the monitoring loop
        logger.error(f"Unexpected error in monitor_progress loop: {e}", exc_info=True)
        # Avoid raising here to prevent crashing the main monitoring flow if possible

# Ensure no trailing characters or placeholders 