"""
Implements the 'results' command logic.
"""

import logging
import sys
import json
from pathlib import Path
from datetime import datetime

import click
from tabulate import tabulate

# Assuming utils are accessible
from ..utils.helpers import setup_logging

logger = logging.getLogger(__name__)

def _parse_results_file_fallback(results_file: Path) -> list[list]:
    # Purpose: Parse severities directly from results.txt when state file lacks counts.
    # Usage: sev_table = _parse_results_file_fallback(Path("output/domain/results.txt"))
    severities_parsed = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0, "unknown": 0}
    sev_table = []
    try:
        logger.debug(f"Parsing results file: {results_file}")
        with open(results_file, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line_lower = line.strip().lower()
                if not line_lower:
                    continue
                found_sev = False
                # Check known severities first
                for sev in ("critical", "high", "medium", "low", "info"):
                    if f"[{sev}]" in line_lower:
                        severities_parsed[sev] += 1
                        found_sev = True
                        break # Stop checking once a severity is found
                # Count as unknown if no known severity found but looks like a result line
                if not found_sev and '[' in line_lower and ']' in line_lower:
                     severities_parsed["unknown"] += 1

        # Convert counts to table format
        sev_table = [[sev.capitalize(), count] for sev, count in severities_parsed.items() if count > 0]

    except Exception as e:
        logger.error(f"Error reading/parsing results file {results_file}: {e}", exc_info=True)
        print(f"⚠️ Could not parse vulnerability details from {results_file.name}: {e}")
        # Return empty list on error
        sev_table = []

    return sev_table

@click.command(name='results') # Explicit name
@click.argument('domain')
@click.option('--output', type=click.Path(), default="output", show_default=True,
              help="Output directory where results were saved.")
def results_command(domain, output):
    # Purpose: Handle the 'results' command, find, parse, and display previous scan results.
    # Usage: Invoked via `python autosubnuclei.py results <domain> [options]`
    """View the summary of previous scan results for a domain."""
    setup_logging() # Setup basic logging for this command
    logger = logging.getLogger(__name__) # Re-init logger
    logger.info(f"Fetching results for domain: {domain}")

    workspace_dir = Path.cwd()
    output_path = Path(output)
    if not output_path.is_absolute():
        output_path = workspace_dir / output_path
    output_path = output_path.resolve()

    domain_output_dir = output_path / domain

    logger.debug(f"Checking for results in: {domain_output_dir}")
    if not domain_output_dir.exists() or not domain_output_dir.is_dir():
        print(f"❌ No scan results found for {click.style(domain, bold=True)} in {domain_output_dir}")
        sys.exit(1)

    # Define expected file names
    state_file = domain_output_dir / "scan_state.json"
    results_file = domain_output_dir / "results.txt"

    if not state_file.exists():
        print(f"❌ Scan state file ({state_file.name}) not found for {click.style(domain, bold=True)}.")
        if results_file.exists():
             print(f"ℹ️  However, a results file ({results_file.name}) was found. You can view it directly.")
        sys.exit(1)

    try:
        logger.debug(f"Loading state file: {state_file}")
        with open(state_file, 'r') as f:
            state = json.load(f)

        # --- Display Scan Summary --- #
        print(f"📊 Scan Summary for {click.style(domain, bold=True)}")
        print(f"Status: {state.get('status', 'Unknown').capitalize()}")

        duration = state.get("duration", 0)
        duration_str = f"{duration:.1f}s" if duration < 60 else f"{duration/60:.1f}m"
        print(f"Duration: {duration_str}")

        scan_time = state.get("scan_time", "Not recorded")
        if scan_time != "Not recorded":
            try:
                 dt_object = datetime.fromisoformat(scan_time)
                 scan_time = dt_object.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                 pass # Keep original string if format fails
        print(f"Completed At: {scan_time}")

        table_data = [
            ["Subdomains Found", state.get("subdomains", "N/A")],
            ["Alive Subdomains", state.get("alive_subdomains", "N/A")],
            ["Vulnerabilities", state.get("vulnerabilities", "N/A")]
        ]
        print("\n" + tabulate(table_data, headers=["Metric", "Count"], tablefmt="pretty"))

        # --- Display Vulnerability Summary --- #
        if state.get("vulnerabilities", 0) > 0 and results_file.exists():
            print(f"\n🔍 Vulnerability Summary (from {results_file.name}):")
            sev_table = [] # Initialize table
            # Use severity counts from state if available (more reliable)
            severity_counts_state = state.get("severity_counts")
            if severity_counts_state:
                logger.debug("Using severity counts from scan_state.json")
                sev_table = [[sev.capitalize(), count] for sev, count in severity_counts_state.items() if count > 0]
            else:
                # Fallback to parsing results.txt
                logger.warning("Severity counts not found in state file, attempting to parse results.txt")
                sev_table = _parse_results_file_fallback(results_file)

            # Display the table
            if sev_table:
                print(tabulate(sev_table, headers=["Severity", "Count"], tablefmt="pretty", showindex=False))
            else:
                print("   No specific severities could be parsed or found.")

            print(f"\n📄 Detailed results file: {results_file}")

        elif state.get("vulnerabilities", 0) > 0:
             print(f"\n⚠️ State indicates {state.get('vulnerabilities')} vulnerabilities, but results file ({results_file.name}) not found.")
        else:
            print("\n✅ No vulnerabilities recorded in the scan state.")

    except json.JSONDecodeError as e:
        logger.error(f"Failed to decode JSON from state file {state_file}: {e}", exc_info=True)
        print(f"❌ Error reading scan state file {state_file.name}: Invalid JSON - {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error displaying results for {domain}: {e}", exc_info=True)
        print(f"❌ An unexpected error occurred: {e}")
        sys.exit(1) 