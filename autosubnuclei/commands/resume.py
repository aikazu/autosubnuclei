"""
Command to resume an interrupted security scan
"""

import logging
import sys
from pathlib import Path
import click
import os
from tabulate import tabulate

from autosubnuclei.core.scanner import SecurityScanner
from autosubnuclei.core.checkpoint_manager import CheckpointManager
from autosubnuclei.config.settings import (
    validate_domain,
    validate_severities,
    validate_output_dir,
    NUCLEI_CONFIG
)
from autosubnuclei.utils.helpers import setup_logging
from autosubnuclei.utils.tool_manager import ToolManager

logger = logging.getLogger(__name__)

def register_command(cli):
    """
    Register the resume command with the CLI
    
    Args:
        cli: Click command group
    """
    cli.add_command(resume)

@click.command()
@click.argument('domain')
@click.option('--from-checkpoint', type=click.Path(exists=True),
              help="Resume from a specific checkpoint file")
@click.option('--force-phase', type=click.Choice(['subdomain', 'alive', 'nuclei']),
              help="Force restart from a specific phase")
@click.option('--skip-verification', is_flag=True,
              help="Skip environment verification")
@click.option('--output', type=click.Path(), default="output",
              help="Output directory for results")
@click.option('--templates', default="./nuclei-templates/",
              help="Path to nuclei templates (will be downloaded if not found)")
@click.option('--log-file', type=click.Path(),
              help="Path to log file")
@click.option('--no-confirm', is_flag=True,
              help="Skip confirmation prompt")
@click.option('--severities', default=None,
              help="Override comma-separated Nuclei severity levels")
def resume(domain, from_checkpoint, force_phase, skip_verification, output, templates, log_file, no_confirm, severities):
    """Resume an interrupted security scan"""
    # Setup logging
    setup_logging(log_file)

    try:
        # Validate domain
        if not validate_domain(domain):
            raise ValueError(f"Invalid domain format: {domain}")

        # Get workspace directory
        workspace_dir = Path.cwd()
        
        # Prepare output directory
        output_path = Path(output)
        if not output_path.is_absolute():
            output_path = workspace_dir / output_path
            
        domain_output_dir = output_path / domain
        
        # Check if domain output directory exists
        if not domain_output_dir.exists():
            raise ValueError(f"Domain output directory does not exist: {domain_output_dir}")
        
        # Locate checkpoint file
        checkpoint_file = None
        if from_checkpoint:
            checkpoint_file = Path(from_checkpoint)
            if not checkpoint_file.is_absolute():
                checkpoint_file = workspace_dir / checkpoint_file
        else:
            # Use default checkpoint location
            checkpoint_file = domain_output_dir / "checkpoints" / "scan_state.json"
            
        if not checkpoint_file.exists():
            raise ValueError(f"Checkpoint file does not exist: {checkpoint_file}")
        
        # Load checkpoint
        checkpoint_manager = CheckpointManager(domain, domain_output_dir)
        if not checkpoint_manager.load_checkpoint(checkpoint_file):
            raise ValueError("Failed to load checkpoint file")
        
        # Verify checkpoint integrity
        is_valid, issues = checkpoint_manager.verify_checkpoint_integrity()
        if not is_valid:
            print("\n⚠️ Checkpoint integrity issues detected:")
            for issue in issues:
                print(f"  - {issue}")
                
            if not skip_verification and not no_confirm:
                if not click.confirm("Attempt to repair checkpoint?", default=True):
                    print("Aborting resume operation.")
                    return
                
                # Try to repair checkpoint
                if checkpoint_manager.repair_checkpoint():
                    print("✅ Checkpoint repaired successfully")
                else:
                    print("❌ Failed to repair checkpoint")
                    if not click.confirm("Continue with possibly corrupted checkpoint?", default=False):
                        print("Aborting resume operation.")
                        return
        
        # Create backup of checkpoint before resuming
        checkpoint_manager.create_backup_checkpoint()
        
        # Get checkpoint summary
        summary = checkpoint_manager.get_scan_summary()
        
        # Display scan summary
        print(f"\n📋 Scan Resume Summary for {domain}")
        print(f"Scan ID: {summary['scan_id']}")
        print(f"Started: {summary['start_time']}")
        print(f"Last update: {summary['last_update']}")
        print(f"Status: {summary['status']}")
        
        # Display phase status
        phase_table = []
        for phase, status in summary['phase_status'].items():
            phase_data = checkpoint_manager.get_phase_data(phase)
            phase_table.append([
                phase.replace('_', ' ').title(),
                status.title(),
                f"{phase_data['progress_percentage']}%",
                phase_data['results_count']
            ])
        
        print("\nPhase Status:")
        print(tabulate(
            phase_table,
            headers=["Phase", "Status", "Progress", "Results"],
            tablefmt="simple"
        ))
        
        # Display statistics
        stats_table = []
        for stat, value in summary['statistics'].items():
            stats_table.append([stat.replace('_', ' ').title(), value])
        
        print("\nCurrent Statistics:")
        print(tabulate(stats_table, headers=["Metric", "Value"], tablefmt="simple"))
        
        # Verify environment
        if not skip_verification:
            tool_manager = ToolManager()
            current_versions = {}
            for tool in tool_manager.required_tools:
                current_versions[tool] = tool_manager.get_tool_version(tool) or "unknown"
            
            is_valid, mismatches = checkpoint_manager.validate_environment(current_versions)
            
            if not is_valid:
                print("\n⚠️ Environment mismatch detected:")
                for mismatch in mismatches:
                    print(f"  - {mismatch}")
                    
                if not no_confirm:
                    if not click.confirm("Continue despite environment mismatch?", default=False):
                        print("Aborting resume operation.")
                        return
        
        # Optimize checkpoint if needed (remove unnecessary data)
        checkpoint_manager.optimize_checkpoint()
        
        # Cleanup old checkpoints to save disk space
        checkpoint_manager.cleanup_old_checkpoints(max_checkpoints=5)
        
        # Make templates path relative to workspace if it's not an absolute path
        templates_path = Path(templates)
        if not templates_path.is_absolute():
            templates_path = workspace_dir / templates_path
        
        templates_path = templates_path.resolve()
        
        # Ask for confirmation
        if not no_confirm:
            if not click.confirm("\nDo you want to resume this scan?", default=True):
                print("Aborting resume operation.")
                return
        
        # Override severities if specified
        severities_list = None
        if severities:
            severities_list = [s.strip() for s in severities.split(",")]
            if not validate_severities(severities_list):
                raise ValueError(f"Invalid severity levels: {severities}")
        
        # Initialize scanner with checkpoint
        scanner = SecurityScanner(
            domain=domain,
            output_dir=domain_output_dir,
            templates_path=templates_path,
            checkpoint=checkpoint_file
        )
        
        # Create progress monitor
        # This part will be updated once we have a progress monitor for resume operations
        # progress_monitor = ResumeProgressMonitor(scanner)
        from autosubnuclei import run_scan_with_progress, ProgressMonitor
        progress_monitor = ProgressMonitor(scanner)
        
        # Run the resumed scan
        print(f"\n🚀 Resuming security scan for {domain}")
        
        import asyncio
        asyncio.run(run_scan_with_progress(
            scanner=scanner,
            severities=severities_list,
            notify=True,
            progress_monitor=progress_monitor
        ))

    except Exception as err:
        logger.error(f"Error resuming scan: {err}")
        print(f"❌ Error: {err}")
        sys.exit(1) 