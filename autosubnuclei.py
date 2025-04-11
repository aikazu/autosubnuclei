#!/usr/bin/env python3

import argparse
import logging
from pathlib import Path
import sys
from typing import List

import click

from autosubnuclei.core.scanner import SecurityScanner
from autosubnuclei.config.settings import (
    validate_domain,
    validate_severities,
    validate_output_dir,
    NUCLEI_CONFIG
)
from autosubnuclei.utils.helpers import setup_logging
from autosubnuclei.commands.setup import setup

@click.group()
def cli():
    """AutoSubNuclei - Automated Security Scanning Pipeline"""
    pass

@cli.command()
@click.argument('domain')
@click.option('--templates', default="~/nuclei-templates/",
              help="Path to nuclei templates")
@click.option('--output', type=click.Path(), default="output",
              help="Output directory for results")
@click.option('--no-notify', is_flag=True,
              help="Disable notifications")
@click.option('--severities', default=",".join(NUCLEI_CONFIG["default_severities"]),
              help="Comma-separated Nuclei severity levels")
@click.option('--log-file', type=click.Path(),
              help="Path to log file")
def scan(domain, templates, output, no_notify, severities, log_file):
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

        templates_path = Path(templates).expanduser()
        if not templates_path.exists():
            raise FileNotFoundError(f"Nuclei templates directory not found: {templates_path}")

        # Prepare output directory
        domain_output_dir = Path(output) / domain
        if not validate_output_dir(domain_output_dir):
            raise ValueError(f"Failed to create output directory: {domain_output_dir}")

        # Initialize and run scanner
        scanner = SecurityScanner(
            domain=domain,
            output_dir=domain_output_dir,
            templates_path=templates_path
        )
        
        scanner.scan(
            severities=severities_list,
            notify=not no_notify
        )

    except Exception as err:
        logger.error(f"Fatal error: {err}")
        sys.exit(1)

# Add commands
cli.add_command(scan)
cli.add_command(setup)

if __name__ == "__main__":
    cli()
