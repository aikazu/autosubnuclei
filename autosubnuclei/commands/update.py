"""
Implements the 'update' command logic for tools and templates.
"""

import logging
import sys
import shutil
import subprocess
from pathlib import Path

import click

# Assuming utils are accessible
from ..utils.helpers import setup_logging
from ..utils.tool_manager import ToolManager
# Need TemplateManager if we want to integrate checks/updates beyond Nuclei CLI
# from ..core.template_manager import TemplateManager

logger = logging.getLogger(__name__)


def _update_tools(tool_manager: ToolManager, force: bool):
    # Purpose: Handle the logic for checking and updating required tools.
    # Usage: updated, failed = _update_tools(tool_manager_instance, force_update=False)
    print("\n" + "-"*15 + " Tool Updates " + "-"*15)
    print("🔄 Checking for tool updates...")
    logger.info("Updating tools...")
    updated_tools = []
    failed_tools = []

    for tool_name in tool_manager.required_tools:
        try:
            print(f"  Checking {tool_name}...")
            logger.debug(f"Checking update status for {tool_name}")
            current_version = tool_manager.get_tool_version(tool_name)
            logger.info(f"Current {tool_name} version: {current_version}")
            print(f"    Current version: {current_version or 'Not found/Unknown'}")

            needs_update, reason = tool_manager.check_update_needed(tool_name, force)

            if needs_update:
                print(f"    {reason}")
                print(f"  ⬆️ Updating {tool_name}...")
                logger.info(f"Attempting update for {tool_name}. Reason: {reason}")
                tool_manager.update_tool(tool_name)
                new_version = tool_manager.get_tool_version(tool_name)
                print(f"  ✅ {tool_name} updated successfully to version {new_version or 'Unknown'}")
                logger.info(f"{tool_name} updated successfully to {new_version}")
                updated_tools.append(tool_name)
            else:
                print(f"  ✅ {tool_name} is already up to date.")
                logger.info(f"{tool_name} is up to date.")

        except Exception as e:
            logger.error(f"Failed to update {tool_name}: {e}", exc_info=True)
            print(f"  ❌ Failed to update {tool_name}: {str(e)}")
            failed_tools.append(tool_name)

    print("\n🎉 Tool update check completed.")
    if updated_tools:
        print(f"   Updated: {', '.join(updated_tools)}")
    if failed_tools:
        print(f"   Failed: {', '.join(failed_tools)}")
    logger.info(f"Tool update summary - Updated: {updated_tools}, Failed: {failed_tools}")
    return updated_tools, failed_tools # Return results if needed elsewhere

def _run_nuclei_update_cli(nuclei_path: Path, templates_path: Path):
    # Purpose: Execute the Nuclei CLI update command and handle retries.
    # Usage: _run_nuclei_update_cli(Path("tools/nuclei"), Path("tpl"))
    command = [str(nuclei_path), "-ud", str(templates_path), "-update-templates"]
    print(f"  Running Nuclei update command: {' '.join(command)}")
    logger.info(f"Executing nuclei template update: {' '.join(command)}")

    process = subprocess.run(command, capture_output=True, text=True, check=False)

    logger.debug("Nuclei update STDOUT:")
    logger.debug(process.stdout)
    logger.debug("Nuclei update STDERR:")
    logger.debug(process.stderr)

    if process.returncode != 0:
        # Handle common error: Directory not found/issue
        if ("no such file or directory" in process.stderr.lower() or
            "directory not found" in process.stderr.lower()):
            print("   Nuclei reported directory not found/issue. Trying download/update mode (-ut)...")
            command = [str(nuclei_path), "-ud", str(templates_path), "-ut"] # Use -ut flag
            print(f"  Running Nuclei download/update command: {' '.join(command)}")
            logger.info(f"Retrying with nuclei template download/update (-ut): {' '.join(command)}")
            process = subprocess.run(command, capture_output=True, text=True, check=False)
            # Log results of retry attempt
            logger.debug("Nuclei retry STDOUT:")
            logger.debug(process.stdout)
            logger.debug("Nuclei retry STDERR:")
            logger.debug(process.stderr)

            # Raise error if retry also failed
            if process.returncode != 0:
                error_msg = f"Nuclei template download/update (-ut) failed. Error: {process.stderr or process.stdout}"
                logger.error(f"Nuclei retry failed. RC: {process.returncode}. Error: {error_msg}")
                raise RuntimeError(error_msg)
        else:
            # Raise error for other non-zero exit codes
            error_msg = f"Nuclei template update failed. Error: {process.stderr or process.stdout}"
            logger.error(f"Nuclei update failed. RC: {process.returncode}. Error: {error_msg}")
            raise RuntimeError(error_msg)

    # If we reach here, the command (or retry) succeeded (exit code 0)
    logger.info("Nuclei CLI update command executed successfully.")

def _verify_template_update(templates_path: Path, version_file: Path):
    # Purpose: Check if templates seem valid after update and handle version file.
    # Usage: _verify_template_update(Path("tpl"), Path("tpl/.version"))
    if not list(templates_path.glob('**/*.yaml')): # Check for any YAML files recursively
        logger.warning(f"Template directory {templates_path} appears empty or lacks YAML files after update attempt.")
        print(f"[WARN] Template directory {templates_path} seems empty after update.")
    else:
         print("  ✅ Nuclei templates updated successfully (via Nuclei CLI).")
         logger.info("Nuclei templates updated successfully (via Nuclei CLI).")
         # Remove old version file after successful Nuclei-managed update, as Nuclei manages its own state
         if version_file.exists():
             try:
                 version_file.unlink()
                 logger.info(f"Removed old version file: {version_file}")
             except OSError as e:
                 logger.warning(f"Could not remove old version file {version_file}: {e}")

def _update_templates(tool_manager: ToolManager, templates_dir_str: str, force: bool):
    # Purpose: Handle the logic for checking and updating Nuclei templates using Nuclei CLI.
    # Usage: _update_templates(tool_manager, "./nuclei-templates", force_update=False)
    print("\n" + "-"*13 + " Template Updates " + "-"*13)
    print("\n🔄 Checking for Nuclei template updates...")
    logger.info("Updating Nuclei templates...")

    templates_path = Path(templates_dir_str)
    if not templates_path.is_absolute():
        templates_path = Path.cwd() / templates_path
    templates_path = templates_path.resolve()
    logger.debug(f"Target templates directory: {templates_path}")
    print(f"  Using template path: {templates_path}")

    # Define version file path (used for checking and cleanup)
    version_file = templates_path / ".version"

    try:
        nuclei_path = tool_manager.get_tool_path("nuclei")
        if not nuclei_path:
             raise FileNotFoundError("Nuclei binary not found. Cannot update templates. Run setup or update --tools first.")

        # Check local version file info (optional display)
        if version_file.exists() and not force:
            try:
                with open(version_file, "r") as f:
                    current_hash = f.read().strip()
                print(f"    Current template version (from .version file): {current_hash[:7] if current_hash else 'Unknown'}")
                logger.info(f"Current template hash from file: {current_hash}")
            except Exception as e:
                 logger.warning(f"Could not read template version file {version_file}: {e}")
                 print(f"    Could not read local version file: {e}")

        # Force update: remove existing directory
        if force and templates_path.exists():
            print("  --force specified: Removing existing templates directory...")
            logger.info(f"Forcing template update by removing {templates_path}")
            try:
               shutil.rmtree(templates_path)
               print(f"    Removed {templates_path}")
            except Exception as e:
                logger.error(f"Failed to remove templates directory for force update: {e}", exc_info=True)
                raise RuntimeError(f"Failed to remove templates directory {templates_path} for force update: {e}") from e

        # Ensure target directory exists before running Nuclei
        templates_path.mkdir(parents=True, exist_ok=True)

        # Run the Nuclei update command
        _run_nuclei_update_cli(nuclei_path, templates_path)

        # Verify the results
        _verify_template_update(templates_path, version_file)

    except FileNotFoundError as e:
         logger.error(f"Template update failed: {e}", exc_info=False) # No need for full trace here
         print(f"  ❌ Error: {e}")
         print("     Please ensure Nuclei is installed and accessible (try running 'update --tools').")
    except RuntimeError as e:
         logger.error(f"Template update failed: {e}", exc_info=False)
         print(f"  ❌ Error during template update: {e}")
    except Exception as e:
         logger.error(f"Unexpected error during template update: {e}", exc_info=True)
         print(f"  ❌ An unexpected error occurred during template update: {e}")
    finally:
        # Always print completion message, even if errors occurred in helpers
        print("\n🎉 Template update check completed.")


@click.command(name='update')
@click.option('--tools', is_flag=True, help="Update security tools (Subfinder, Nuclei, httpx).")
@click.option('--templates', is_flag=True, help="Update Nuclei templates.")
@click.option('--all', 'update_all', is_flag=True, default=False, help="Update both tools and templates.")
@click.option('--templates-dir', default="./nuclei-templates/", show_default=True,
              help="Path to Nuclei templates directory.")
@click.option('--force', is_flag=True, default=False, help="Force update even if up-to-date.")
def update_command(tools, templates, update_all, templates_dir, force):
    # Purpose: Handle the 'update' command, checking and updating external tools and nuclei templates.
    # Usage: Invoked via `python autosubnuclei.py update [options]`
    """Update external tools and Nuclei templates."""
    setup_logging() # Setup basic logging for this command
    logger = logging.getLogger(__name__) # Re-init logger
    logger.info("Starting update command...")

    if not any([tools, templates, update_all]):
        if click.confirm("No specific component selected. Update all (tools and templates)?", default=True):
            update_all = True
        else:
            print("Aborting update.")
            return

    if update_all:
        logger.debug("Updating all components.")
        tools = templates = True

    tool_manager = ToolManager()

    try:
        if tools:
            _update_tools(tool_manager, force)

        if templates:
            _update_templates(tool_manager, templates_dir, force)

        print("\n" + "-"*40)
        print("✅ Update process finished.")

    except Exception as e:
        # Catch any unexpected errors from the helper functions
        logger.critical(f"Fatal error during update process: {e}", exc_info=True)
        print(f"\n❌ An unexpected error occurred during the update: {e}")
        sys.exit(1) 