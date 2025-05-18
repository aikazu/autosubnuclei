#!/usr/bin/env python3

import asyncio
import logging
from pathlib import Path
import sys
import os
import json
from typing import List

import click
from tqdm import tqdm
from tabulate import tabulate

from autosubnuclei.core.scanner import SecurityScanner
from autosubnuclei.config.settings import (
    validate_domain,
    validate_severities,
    validate_output_dir,
    NUCLEI_CONFIG
)
from autosubnuclei.utils.helpers import setup_logging
from autosubnuclei.commands.setup import setup
from autosubnuclei.commands.resume import register_command as register_resume_command
from autosubnuclei.utils.tool_manager import ToolManager

@click.group()
def cli():
    """AutoSubNuclei - Automated Security Scanning Pipeline"""
    pass

# Register commands
register_resume_command(cli)

@cli.command()
@click.argument('domain')
@click.option('--templates', default="./nuclei-templates/",
              help="Path to nuclei templates (will be downloaded to workspace if not found)")
@click.option('--output', type=click.Path(), default="output",
              help="Output directory for results")
@click.option('--no-notify', is_flag=True,
              help="Disable notifications")
@click.option('--severities', default=",".join(NUCLEI_CONFIG["default_severities"]),
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

        # After scan completion, check if results.txt exists and has content
        results_file = domain_output_dir / "results.txt"
        if results_file.exists() and results_file.stat().st_size == 0:
            # If results.txt is empty but we reported vulnerabilities, check for nuclei result files
            state_file = domain_output_dir / "scan_state.json"
            if state_file.exists():
                with open(state_file, 'r') as f:
                    state = json.load(f)
                    if state.get("vulnerabilities", 0) > 0:
                        print(f"⚠️ Note: Results file exists but is empty despite finding {state['vulnerabilities']} vulnerabilities.")
                        print("   This is a known issue that has been fixed in the latest version.")
                        print("   To view results, check for nuclei_results_* files in the output directory.")

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
            vulnerabilities_found = state.get("vulnerabilities", 0)
            
            if vulnerabilities_found > 0:
                print("\n🔍 Vulnerability Summary:")
                
                # Handle case where results.txt is empty but vulnerabilities were found
                if not results_file.exists() or results_file.stat().st_size == 0:
                    # Look for nuclei_results_* files
                    nuclei_results = list(domain_output_dir.glob("nuclei_results_*"))
                    if nuclei_results:
                        print(f"⚠️ results.txt file is empty, but found {len(nuclei_results)} nuclei result files.")
                        
                        # Consolidate all nuclei result files into memory
                        all_results = []
                        for result_file in nuclei_results:
                            if result_file.exists() and result_file.stat().st_size > 0:
                                with open(result_file, 'r') as f:
                                    all_results.extend([line.strip() for line in f if line.strip()])
                        
                        # Process the results
                        if all_results:
                            # Extract severities
                            severities = {"critical": [], "high": [], "medium": [], "low": [], "info": []}
                            for line in all_results:
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
                                
                                # Show raw results
                                print("\nRaw results from nuclei scan:")
                                for i, result in enumerate(all_results[:10]):  # Limit to first 10
                                    print(f"  {result}")
                                
                                if len(all_results) > 10:
                                    print(f"  ... and {len(all_results) - 10} more results")
                                
                                # Fix the issue
                                print("\n🛠️ Would you like to fix the empty results.txt file? (y/n)")
                                response = input().strip().lower()
                                if response == 'y' or response == 'yes':
                                    # Combine all results into results.txt
                                    with open(results_file, 'w') as f:
                                        f.write("\n".join(all_results))
                                    print(f"✅ Successfully wrote {len(all_results)} results to {results_file}")
                        else:
                            print("No content found in nuclei result files despite vulnerability count.")
                    else:
                        print("No results found. This could be due to a known issue with results processing.")
                        print("Please run the scan again with the latest version.")
                else:
                    # Normal case - results.txt exists with content
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
    """Monitor and display scan progress"""
    
    def __init__(self, scanner):
        self.scanner = scanner
        self.last_status = ""
        self.progress_bar = None
    
    def update(self):
        """Update the progress display"""
        try:
            current_status = self.scanner.scan_state.get("status", "")
            
            # Skip updates if status is missing
            if not current_status:
                return
            
            # Process status change or update existing progress bar
            if self.last_status != current_status:
                self._handle_status_change(current_status)
            elif self.progress_bar:
                self._update_existing_progress(current_status)
                
        except Exception as e:
            # If progress bar update fails, close it and log error
            if self.progress_bar:
                self._close_progress_bar()
            print(f"Progress monitoring error: {str(e)}")
    
    def _handle_status_change(self, current_status):
        """Handle change in status by creating appropriate progress bar"""
        # Close existing progress bar if any
        self._close_progress_bar()
        
        # Create appropriate progress bar based on the current stage
        if current_status == "downloading_templates":
            self._create_templates_progress_bar()
        elif current_status == "discovering_subdomains":
            self._create_subdomain_discovery_progress_bar()
        elif current_status == "probing_subdomains":
            self._create_subdomain_probing_progress_bar()
        elif current_status == "scanning_vulnerabilities":
            self._create_vulnerability_scanning_progress_bar()
        elif current_status == "completed":
            self._display_completion_message()
        elif current_status == "error":
            self._display_error_message()
            
        self.last_status = current_status
    
    def _update_existing_progress(self, current_status):
        """Update existing progress bar based on current status"""
        if current_status == "downloading_templates":
            self._pulse_templates_progress()
        elif current_status == "discovering_subdomains":
            self._update_subdomain_discovery_progress()
        elif current_status == "probing_subdomains":
            self._update_subdomain_probing_progress()
        elif current_status == "scanning_vulnerabilities":
            self._update_vulnerability_scanning_progress()
    
    def _create_templates_progress_bar(self):
        """Create progress bar for template downloading"""
        self.progress_bar = tqdm(desc="📥 Downloading nuclei templates", unit=" bytes")
        # Indeterminate progress - we'll pulse it
        self.progress_bar.total = 100
        self.progress_bar.n = 0
    
    def _create_subdomain_discovery_progress_bar(self):
        """Create progress bar for subdomain discovery"""
        self.progress_bar = tqdm(desc="📡 Discovering subdomains", unit=" subdomains")
    
    def _create_subdomain_probing_progress_bar(self):
        """Create progress bar for subdomain probing"""
        total = self.scanner.scan_state.get("subdomains", 0)
        if total > 0:
            self.progress_bar = tqdm(desc="🌐 Probing subdomains", total=total, unit=" alive")
        else:
            # If no subdomains found, use indeterminate progress
            self.progress_bar = tqdm(desc="🌐 Probing subdomains", unit=" alive")
    
    def _create_vulnerability_scanning_progress_bar(self):
        """Create progress bar for vulnerability scanning"""
        total = self.scanner.scan_state.get("alive_subdomains", 0)
        if total > 0:
            self.progress_bar = tqdm(desc="🔍 Scanning for vulnerabilities", total=total, unit=" scanned")
        else:
            # If no alive subdomains found, use indeterminate progress
            self.progress_bar = tqdm(desc="🔍 Scanning for vulnerabilities", unit=" scanned")
    
    def _display_completion_message(self):
        """Display completion message with statistics"""
        duration = self.scanner.scan_state.get("duration", 0)
        vulns = self.scanner.scan_state.get("vulnerabilities", 0)
        print(f"✅ Scan completed in {duration:.1f}s, found {vulns} potential vulnerabilities")
        self.progress_bar = None
    
    def _display_error_message(self):
        """Display error message"""
        error_msg = self.scanner.scan_state.get("error", "Unknown error")
        print(f"❌ Scan failed: {error_msg}")
        self.progress_bar = None
    
    def _pulse_templates_progress(self):
        """Pulse the templates progress bar to show activity"""
        # For template downloading, just pulse the progress bar
        self.progress_bar.n = (self.progress_bar.n + 5) % 100
        self.progress_bar.refresh()
    
    def _update_subdomain_discovery_progress(self):
        """Update subdomain discovery progress bar"""
        subdomains = self.scanner.scan_state.get("subdomains", 0)
        if subdomains > 0 and self.progress_bar.n < subdomains:
            self.progress_bar.update(subdomains - self.progress_bar.n)
    
    def _update_subdomain_probing_progress(self):
        """Update subdomain probing progress bar"""
        alive = self.scanner.scan_state.get("alive_subdomains", 0)
        if alive > 0 and self.progress_bar.n < alive:
            self.progress_bar.update(alive - self.progress_bar.n)
    
    def _update_vulnerability_scanning_progress(self):
        """Update vulnerability scanning progress bar"""
        # For vulnerability scanning, we approximate progress
        if self.progress_bar.total and self.progress_bar.total > 0:
            remaining = max(0, self.progress_bar.total - self.progress_bar.n)
            step = max(1, int(remaining * 0.1))  # Update in steps of 10%
            self.progress_bar.update(step)
    
    def _close_progress_bar(self):
        """Safely close the progress bar if it exists"""
        if self.progress_bar:
            try:
                self.progress_bar.close()
            except:
                pass  # Ignore errors when closing
            self.progress_bar = None

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
        raise
    finally:
        # Ensure monitoring task is canceled when scan is done
        monitoring_task.cancel()
        try:
            await monitoring_task
        except asyncio.CancelledError:
            pass
        # Make sure to close any leftover progress bars
        if progress_monitor.progress_bar:
            progress_monitor.progress_bar.close()

async def monitor_progress(progress_monitor):
    """Monitor and display progress"""
    try:
        while True:
            progress_monitor.update()
            await asyncio.sleep(0.5)
    except asyncio.CancelledError:
        # Final update before exiting
        progress_monitor.update()
        # Close progress bar if still open to prevent tqdm errors
        if progress_monitor.progress_bar:
            progress_monitor.progress_bar.close()
            progress_monitor.progress_bar = None
        raise

# Add commands
cli.add_command(scan)
cli.add_command(setup)
cli.add_command(results)
cli.add_command(update)

if __name__ == "__main__":
    cli()
