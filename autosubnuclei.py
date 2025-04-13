#!/usr/bin/env python3

import asyncio
import logging
from pathlib import Path
import sys
import os
import json
from typing import List
import time

import click
from tqdm import tqdm
from tabulate import tabulate

from autosubnuclei.core.scanner import SecurityScanner
from autosubnuclei.config.settings import (
    validate_domain,
    validate_severities,
    validate_output_dir,
    DEFAULT_CONFIG
)
from autosubnuclei.utils.helpers import setup_logging
from autosubnuclei.commands.setup import setup
from autosubnuclei.utils.tool_manager import ToolManager

@click.group()
def cli():
    """AutoSubNuclei - Automated Security Scanning Pipeline"""
    pass

@cli.command()
@click.argument('domain')
@click.option('--templates', default="./nuclei-templates/",
              help="Path to nuclei templates (will be downloaded to workspace if not found)")
@click.option('--output', type=click.Path(), default="output",
              help="Output directory for results")
@click.option('--no-notify', is_flag=True,
              help="Disable notifications")
@click.option('--severities', 
              default=",".join(DEFAULT_CONFIG["nuclei_template_filters"]["template_severity_mapping"]["medium"]),
              help="Comma-separated Nuclei severity levels")
@click.option('--log-file', type=click.Path(),
              help="Path to log file")
@click.option('--concurrency', type=int, default=0,
              help="Maximum number of concurrent operations (0 = auto)")
@click.option('--cache/--no-cache', default=True,
              help="Use cache for faster repeat scans")
def scan(domain, templates, output, no_notify, severities, log_file, concurrency, cache):
    """Run security scan on a domain"""
    # Setup logging
    setup_logging(log_file)
    logger = logging.getLogger(__name__)

    try:
        # Validate inputs
        if not validate_domain(domain):
            raise ValueError(f"Invalid domain format: {domain}")

        severities_list = [s.strip() for s in severities.split(",")]
        if not validate_severities(severities_list):
            raise ValueError(f"Invalid severity levels: {severities}")

        # Get workspace directory (where the tool is running)
        workspace_dir = Path.cwd()
        
        # Make templates path relative to workspace if it's not an absolute path
        templates_path = Path(templates)
        if not templates_path.is_absolute():
            templates_path = workspace_dir / templates_path
        
        templates_path = templates_path.resolve()
        
        # Check if templates path exists
        if not templates_path.exists():
            print(f"📁 Templates not found at {templates_path}")
            print("✨ They will be automatically downloaded to the workspace")

        # Prepare output directory - make it relative to workspace if not absolute
        output_path = Path(output)
        if not output_path.is_absolute():
            output_path = workspace_dir / output_path
            
        domain_output_dir = output_path / domain
        if not validate_output_dir(domain_output_dir):
            raise ValueError(f"Failed to create output directory: {domain_output_dir}")

        # Initialize scanner
        scanner = SecurityScanner(
            domain=domain,
            output_dir=domain_output_dir,
            templates_path=templates_path
        )
        
        # Set concurrency if specified
        if concurrency > 0:
            scanner.max_workers = concurrency
        
        # Create progress monitor
        progress_monitor = ProgressMonitor(scanner)
        
        # Run the scan asynchronously
        print(f"🚀 Starting security scan for {domain}")
        print(f"🔧 Using templates from: {templates_path}")
        print(f"📂 Saving results to: {domain_output_dir}")
        
        asyncio.run(run_scan_with_progress(
            scanner=scanner,
            severities=severities_list,
            notify=not no_notify,
            progress_monitor=progress_monitor
        ))

    except Exception as err:
        logger.error(f"Fatal error: {err}")
        print(f"❌ Error: {err}")
        sys.exit(1)

@cli.command()
@click.argument('domain')
@click.option('--output', type=click.Path(), default="output",
              help="Output directory for results")
def results(domain, output):
    """View scan results for a domain"""
    domain_output_dir = Path(output) / domain
    
    # Check if scan results exist
    if not domain_output_dir.exists():
        print(f"❌ No scan results found for {domain}")
        return
    
    # Check for state file
    state_file = domain_output_dir / "scan_state.json"
    if state_file.exists():
        try:
            with open(state_file, 'r') as f:
                state = json.load(f)
            
            # Print scan summary
            print(f"📊 Scan Summary for {domain}")
            print(f"Status: {state.get('status', 'unknown')}")
            
            duration = state.get("duration", 0)
            duration_str = f"{duration:.1f}s" if duration < 60 else f"{duration/60:.1f}m"
            print(f"Duration: {duration_str}")
            
            table_data = [
                ["Subdomains Found", state.get("subdomains", 0)],
                ["Alive Subdomains", state.get("alive_subdomains", 0)],
                ["Vulnerabilities", state.get("vulnerabilities", 0)]
            ]
            print(tabulate(table_data, headers=["Metric", "Count"], tablefmt="simple"))
            
            # Check if results file exists
            results_file = domain_output_dir / "results.txt"
            if results_file.exists() and state.get("vulnerabilities", 0) > 0:
                print("\n🔍 Vulnerability Summary:")
                
                # Read and categorize results by severity
                severities = {"critical": [], "high": [], "medium": [], "low": [], "info": []}
                with open(results_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        
                        # Try to extract severity
                        for sev in severities.keys():
                            if f"[{sev}]" in line.lower():
                                severities[sev].append(line)
                                break
                
                # Print counts by severity
                sev_table = []
                for sev, items in severities.items():
                    if items:
                        sev_table.append([sev.capitalize(), len(items)])
                
                if sev_table:
                    print(tabulate(sev_table, headers=["Severity", "Count"], tablefmt="simple"))
                    
                    # Show path to detailed results
                    print(f"\nDetailed results are available at: {results_file}")
        except Exception as e:
            print(f"❌ Error reading scan results: {str(e)}")
    else:
        print(f"❌ No scan state found for {domain}")
        
        # Check if there are any results files
        results_file = domain_output_dir / "results.txt"
        if results_file.exists():
            print(f"Results file exists but no scan state. View results at: {results_file}")

@cli.command()
@click.option('--tools', is_flag=True, help="Update security tools to the latest versions")
@click.option('--templates', is_flag=True, help="Update nuclei templates to the latest version")
@click.option('--all', 'update_all', is_flag=True, help="Update both tools and templates")
@click.option('--templates-dir', default="./nuclei-templates/", 
              help="Path to nuclei templates directory (default: ./nuclei-templates/)")
@click.option('--force', is_flag=True, help="Force update even if already up to date")
def update(tools, templates, update_all, templates_dir, force):
    """Update security tools and nuclei templates"""
    if not any([tools, templates, update_all]):
        update_all = True  # Default to updating everything if no option specified
    
    if update_all:
        tools = templates = True
    
    try:
        if tools:
            print("🔄 Checking for tool updates...")
            tool_manager = ToolManager()
            
            # Get current versions
            current_versions = {}
            for tool_name in tool_manager.required_tools:
                current_version = tool_manager.get_tool_version(tool_name)
                current_versions[tool_name] = current_version
                print(f"  📌 Current {tool_name} version: {current_version or 'unknown'}")
            
            # Check and update tools
            for tool_name in tool_manager.required_tools:
                try:
                    latest_version, _ = tool_manager._get_download_url(tool_name)
                    print(f"  🔎 Latest {tool_name} version: {latest_version}")
                    
                    if force or not current_versions[tool_name] or latest_version not in current_versions[tool_name]:
                        print(f"  ⬆️ Updating {tool_name} to version {latest_version}...")
                        tool_manager.update_tool(tool_name)
                        print(f"  ✅ {tool_name} updated successfully")
                    else:
                        print(f"  ✓ {tool_name} is already up to date")
                except Exception as e:
                    print(f"  ❌ Failed to update {tool_name}: {str(e)}")
            
            print("🎉 Tool update check completed")
        
        if templates:
            # Convert to Path and handle relative paths
            templates_path = Path(templates_dir)
            if not templates_path.is_absolute():
                templates_path = Path.cwd() / templates_path
            templates_path = templates_path.resolve()
            
            print(f"🔄 Checking nuclei templates at {templates_path}...")
            
            # Check if templates directory exists
            templates_exist = templates_path.exists() and templates_path.is_dir()
            
            if templates_exist and not force:
                # Check if templates are up to date by fetching latest commit hash
                try:
                    # Get latest commit hash from GitHub API
                    import requests
                    response = requests.get("https://api.github.com/repos/projectdiscovery/nuclei-templates/commits/master")
                    if response.status_code == 200:
                        latest_commit = response.json()
                        latest_hash = latest_commit["sha"]
                        latest_date = latest_commit["commit"]["committer"]["date"]
                        
                        # Check for local version marker
                        version_file = templates_path / ".version"
                        update_needed = True
                        
                        if version_file.exists():
                            try:
                                with open(version_file, "r") as f:
                                    local_hash = f.read().strip()
                                    if local_hash == latest_hash:
                                        update_needed = False
                                        print(f"  ✓ Templates already at latest version (commit: {local_hash[:7]})")
                                    else:
                                        print(f"  🔄 New templates available (current: {local_hash[:7]}, latest: {latest_hash[:7]})")
                            except:
                                pass
                        
                        if update_needed or force:
                            print("  🗑️ Removing existing templates for clean update...")
                            import shutil
                            shutil.rmtree(templates_path)
                            templates_exist = False
                        else:
                            print("  📁 Templates are up to date!")
                except Exception as e:
                    print(f"  ⚠️ Could not check for template updates: {str(e)}")
                    # Continue with existing templates
            
            if not templates_exist or force:
                # Download fresh templates
                print("  📥 Downloading latest templates...")
                try:
                    # Create a temporary scanner just for template downloading
                    from autosubnuclei.core.scanner import SecurityScanner
                    
                    # Create output directory if it doesn't exist
                    dummy_output_dir = Path("./output/update_temp")
                    dummy_output_dir.mkdir(parents=True, exist_ok=True)
                    
                    # Create the scanner which will download templates
                    try:
                        scanner = SecurityScanner(
                            domain="example.com",  # Dummy domain for template downloading
                            output_dir=dummy_output_dir,
                            templates_path=templates_path
                        )
                        
                        # Templates are downloaded in init if not found
                        print("  ✅ Templates downloaded successfully")
                        
                        # Save version info
                        try:
                            import requests
                            response = requests.get("https://api.github.com/repos/projectdiscovery/nuclei-templates/commits/master")
                            if response.status_code == 200:
                                latest_hash = response.json()["sha"]
                                with open(templates_path / ".version", "w") as f:
                                    f.write(latest_hash)
                        except:
                            pass
                        
                    finally:
                        # Clean up temporary directory
                        if dummy_output_dir.exists():
                            shutil.rmtree(dummy_output_dir)
                except Exception as e:
                    print(f"  ❌ Failed to update templates: {str(e)}")
                    # Print more detailed error information
                    import traceback
                    print(f"  Detailed error: {traceback.format_exc()}")
            
            print("🎉 Template update completed")
            
    except Exception as e:
        print(f"❌ Error during update: {str(e)}")
        sys.exit(1)

class ProgressMonitor:
    """Monitor and display scan progress with simple status messages"""
    
    def __init__(self, scanner):
        self.scanner = scanner
        self.last_status = ""
        self.last_message_time = 0
        self.status_messages = {
            "initializing": "🚀 Initializing scan...",
            "downloading_templates": "📥 Downloading nuclei templates...",
            "discovering_subdomains": "📡 Discovering subdomains...",
            "probing_subdomains": "🌐 Probing subdomains...",
            "scanning_vulnerabilities": "🔍 Scanning for vulnerabilities...",
            "completed": "✅ Scan completed!",
            "error": "❌ Scan failed!"
        }
    
    def update(self):
        """Update the progress display with simple status messages"""
        try:
            current_status = self.scanner.scan_state.get("status", "")
            current_time = time.time()
            
            # Skip updates if status is missing
            if not current_status:
                return
            
            # Only print a new status message if the status changed or 10 seconds passed
            if (self.last_status != current_status or 
                current_time - self.last_message_time > 10):
                
                # Get the appropriate message for this status
                message = self.status_messages.get(current_status, f"⏳ {current_status.replace('_', ' ').title()}...")
                
                # Add counts to the message if available
                if current_status == "discovering_subdomains":
                    subdomains = self.scanner.scan_state.get("subdomains", 0)
                    if subdomains > 0:
                        message = f"📡 Found {subdomains} subdomains..."
                
                elif current_status == "probing_subdomains":
                    subdomains = self.scanner.scan_state.get("subdomains", 0)
                    alive = self.scanner.scan_state.get("alive_subdomains", 0)
                    if alive > 0:
                        message = f"🌐 Found {alive}/{subdomains} alive subdomains..."
                
                elif current_status == "scanning_vulnerabilities":
                    alive = self.scanner.scan_state.get("alive_subdomains", 0)
                    if alive > 0:
                        message = f"🔍 Scanning {alive} targets for vulnerabilities..."
                
                elif current_status == "completed":
                    duration = self.scanner.scan_state.get("duration", 0)
                    vulns = self.scanner.scan_state.get("vulnerabilities", 0)
                    message = f"✅ Scan completed in {duration:.1f}s, found {vulns} potential vulnerabilities"
                
                elif current_status == "error":
                    error_msg = self.scanner.scan_state.get("error", "Unknown error")
                    message = f"❌ Scan failed: {error_msg}"
                
                # Print the message
                print(message)
                
                # Update the tracking variables
                self.last_status = current_status
                self.last_message_time = current_time
                
        except Exception as e:
            print(f"Progress monitoring error: {str(e)}")

async def run_scan_with_progress(scanner, severities, notify, progress_monitor):
    """Run the scan with progress monitoring"""
    # Start the progress monitoring task
    monitoring_task = asyncio.create_task(monitor_progress(progress_monitor))
    
    try:
        # Run the scanner
        await scanner.scan(severities=severities, notify=notify)
    except Exception as e:
        # Make sure the error is passed to the scan state
        scanner.scan_state["status"] = "error"
        scanner.scan_state["error"] = str(e)
        # Wait a moment for the progress monitor to update
        await asyncio.sleep(1)
        raise
    finally:
        # Ensure monitoring task is canceled when scan is done
        monitoring_task.cancel()
        try:
            await monitoring_task
        except asyncio.CancelledError:
            pass

async def monitor_progress(progress_monitor):
    """Monitor and display progress periodically"""
    try:
        while True:
            progress_monitor.update()
            await asyncio.sleep(1)  # Update every second
    except asyncio.CancelledError:
        # Expected when the task is cancelled
        pass

# Add commands
cli.add_command(scan)
cli.add_command(setup)
cli.add_command(results)
cli.add_command(update)

if __name__ == "__main__":
    cli()
