"""
Implements the 'scan' command logic.
"""

import asyncio
import logging
import subprocess
import sys
from pathlib import Path

import click

# Assuming core scanner and utils are accessible
from ..core.scanner import SecurityScanner
from ..config.settings import (
    validate_domain,
    validate_severities,
    validate_output_dir,
    DEFAULT_CONFIG
)
from ..utils.helpers import setup_logging
# Update imports for moved helpers
from ..utils.progress import ProgressMonitor
from ..utils.async_utils import run_scan_with_progress
# Need ProgressMonitor and async helpers from cli.py or a shared location
# For now, assume they are moved to utils or imported carefully
# Let's define dummy placeholders if direct import from cli isn't ideal
# Option 1: Direct import (might create circular dependency if not careful)
# from ..cli import ProgressMonitor, run_scan_with_progress

# Option 2: Move ProgressMonitor/helpers to utils (better)
# Let's assume they will be moved to utils for this example:
# from ..utils.async_utils import run_scan_with_progress # Hypothetical module
# from ..utils.progress import ProgressMonitor # Hypothetical module

logger = logging.getLogger(__name__)


def _validate_scan_inputs(domain: str, severities_str: str) -> list[str]:
    # Purpose: Validate domain and severity inputs for the scan command.
    # Usage: severities_list = _validate_scan_inputs("example.com", "high,critical")
    logger.debug("Validating domain...")
    if not validate_domain(domain):
        raise click.BadParameter(f"Invalid domain format: {domain}", param_hint='domain')

    logger.debug("Validating severities...")
    severities_list = [s.strip().lower() for s in severities_str.split(",") if s.strip()]
    if not severities_list:
        raise click.BadParameter("Severities cannot be empty.", param_hint='severities')
    if not validate_severities(severities_list):
        allowed = ", ".join(DEFAULT_CONFIG["nuclei_template_filters"]["allowed_severities"])
        raise click.BadParameter(f"Invalid severity levels: {severities_str}. Allowed: {allowed}", param_hint='severities')
    return severities_list

def _prepare_scan_paths(templates_str: str, output_str: str, domain: str) -> tuple[Path, Path]:
    # Purpose: Resolve and validate template and output paths.
    # Usage: templates_path, domain_output_dir = _prepare_scan_paths("./tpl", "out", "ex.com")
    logger.debug("Processing paths...")
    workspace_dir = Path.cwd()

    templates_path = Path(templates_str)
    if not templates_path.is_absolute():
        templates_path = workspace_dir / templates_path
    templates_path = templates_path.resolve()

    output_path = Path(output_str)
    if not output_path.is_absolute():
        output_path = workspace_dir / output_path
    output_path = output_path.resolve()

    domain_output_dir = output_path / domain
    logger.debug(f"Ensuring output directory exists: {domain_output_dir}")
    if not validate_output_dir(domain_output_dir):
        raise click.ClickException(f"Failed to create or access output directory: {domain_output_dir}")

    return templates_path, domain_output_dir


@click.command(name='scan') # Add name explicitly for registration
@click.argument('domain')
@click.option('--templates', default="./nuclei-templates/", show_default=True,
              help="Path to nuclei templates directory.")
@click.option('--output', type=click.Path(), default="output", show_default=True,
              help="Output directory for results.")
@click.option('--no-notify', is_flag=True, default=False,
              help="Disable notifications (if configured).")
@click.option('--severities',
              default=",".join(DEFAULT_CONFIG["nuclei_template_filters"]["template_severity_mapping"]["medium"]), # Example, adjust as needed
              show_default=True,
              help="Comma-separated Nuclei severity levels (critical, high, medium, low, info).")
@click.option('--log-file', type=click.Path(), default=None,
              help="Path to log file (optional).")
@click.option('--concurrency', type=int, default=0, show_default="auto",
              help="Maximum number of concurrent operations (0 = auto).")
@click.option('--cache/--no-cache', default=True,
              help="Enable/disable caching for faster repeat scans.")
def scan_command(domain, templates, output, no_notify, severities, log_file, concurrency, cache):
    # Purpose: Handle the 'scan' command, validate inputs, initialize, and run the security scan.
    # Usage: Invoked via `python autosubnuclei.py scan <domain> [options]`
    """Run a security scan on a target domain."""
    setup_logging(log_file)
    logger = logging.getLogger(__name__) # Re-init logger for this module scope
    logger.info(f"Starting scan command for domain: {domain}")

    try:
        # Validate inputs
        severities_list = _validate_scan_inputs(domain, severities)

        # Prepare paths
        templates_path, domain_output_dir = _prepare_scan_paths(templates, output, domain)

        # Display parameters and ask for confirmation
        print(f"🚀 Starting security scan for {click.style(domain, bold=True)}")
        print(f"🔧 Using templates from: {templates_path}")
        print(f"📂 Saving results to: {domain_output_dir}")
        print(f"⚠️  Selected severities: {', '.join(severities_list)}")
        print(f"⏱️  Concurrency: {'auto' if concurrency == 0 else concurrency}")
        print(f"💾 Cache: {'enabled' if cache else 'disabled'}")
        print("-" * 30)

        if not click.confirm("Do you want to proceed with the scan?", default=True, abort=True):
            pass # Aborted by user

        logger.info("User confirmed scan start.")
        print("Initializing scanner and checking tools/templates...")

        scanner = None # Define scanner before try block
        try:
            # Initialize Scanner
            scanner = SecurityScanner(
                domain=domain,
                output_dir=domain_output_dir,
                templates_path=templates_path,
                use_cache=cache,
                progress_monitor=None
            )
        except (FileNotFoundError, RuntimeError) as e:
            logger.error(f"Scanner Initialization Error: {e}", exc_info=True)
            print(f"❌ Error: Failed to initialize scanner: {e}")
            print("   Check tool paths, template paths, and permissions.")
            sys.exit(1)
        except Exception as e:
            logger.error(f"Unexpected Scanner Initialization Error: {e}", exc_info=True)
            print(f"❌ An unexpected error occurred during scanner setup: {e}")
            sys.exit(1)

        # Configure concurrency and attach progress monitor
        if concurrency > 0:
            logger.info(f"Setting concurrency to {concurrency}")
            scanner.max_workers = concurrency

        progress_monitor = ProgressMonitor(scanner)
        scanner.progress_monitor = progress_monitor

        # Execute the scan
        try:
            asyncio.run(run_scan_with_progress(
                scanner=scanner,
                severities=severities_list,
                notify=not no_notify,
                progress_monitor=progress_monitor
            ))
        except (RuntimeError, FileNotFoundError, subprocess.CalledProcessError, TimeoutError) as e:
            logger.error(f"Scanning Error: {e}", exc_info=True)
            print(f"❌ Scan failed. Check status messages above and logs for details.")
            # Monitor should have printed specific error
            sys.exit(1)
        except Exception as err:
            logger.critical(f"Fatal unexpected error during scan execution: {err}", exc_info=True)
            print(f"❌ Fatal Unexpected Error: {err}")
            print("   Please check the log file.")
            sys.exit(1)

        # Completion message
        print("-" * 30)
        logger.info(f"Scan command for {domain} finished.")
        # Final summary is printed by ProgressMonitor

    except click.ClickException as e:
         # Catches validation errors (BadParameter) and confirmation abort
         logger.error(f"CLI Error: {e}", exc_info=False) # Don't need full traceback for user errors
         print(f"❌ Error: {e}")
         sys.exit(1)
    # No generic Exception catch here - should be handled within scan execution

# Ensure no trailing characters or placeholders after the function definition 