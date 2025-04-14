#!/usr/bin/env python3

import asyncio
import logging
from pathlib import Path
import sys
import os
import json
import time
import shutil
import requests  # Make sure requests is imported if used directly here
import traceback
from datetime import datetime

import click
from tabulate import tabulate

# Assuming these paths are correct relative to this new file location
# Adjust if necessary based on actual final structure
from .core.scanner import SecurityScanner
from .config.settings import (
    validate_domain,
    validate_severities,
    validate_output_dir,
    DEFAULT_CONFIG
)
from .utils.helpers import setup_logging
from .commands.setup import setup  # Assuming setup command lives here
from .commands.scan import scan_command
from .commands.results import results_command
from .commands.update import update_command
from .utils.tool_manager import ToolManager

# --- Click CLI Group and Commands ---
@click.group()
def cli():
    # Purpose: Define the main entry point group for the CLI commands.
    # Usage: Called implicitly when the script is run.
    """AutoSubNuclei - Automated Security Scanning Pipeline"""
    pass

# Add the imported/existing commands
cli.add_command(scan_command)
cli.add_command(results_command)
cli.add_command(update_command) # Add the imported update command
# Ensure 'setup' is actually a click command object
if hasattr(setup, '__module__') and isinstance(setup, click.Command):
    cli.add_command(setup)
else:
    logger = logging.getLogger(__name__)
    logger.warning("Could not find or add the 'setup' command.")

# The main execution part `if __name__ == "__main__":` should be in the entrypoint script
# Do not include that here. 