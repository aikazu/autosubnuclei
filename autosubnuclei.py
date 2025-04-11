#!/usr/bin/env python3

import argparse
import logging
from pathlib import Path
import sys
from typing import List

from autosubnuclei.core.scanner import SecurityScanner
from autosubnuclei.config.settings import (
    validate_domain,
    validate_severities,
    validate_output_dir,
    NUCLEI_CONFIG
)
from autosubnuclei.utils.helpers import setup_logging

def parse_arguments():
    parser = argparse.ArgumentParser(description="Automated Security Scanning Pipeline")
    parser.add_argument("domain", help="Target domain to scan")
    parser.add_argument("--templates", default="~/nuclei-templates/",
                      help="Path to nuclei templates")
    parser.add_argument("--output", type=Path, default=Path("output"),
                      help="Output directory for results")
    parser.add_argument("--no-notify", action="store_true",
                      help="Disable notifications")
    parser.add_argument("--force", action="store_true",
                      help="Force re-download of binaries")
    parser.add_argument("--severities", default=",".join(NUCLEI_CONFIG["default_severities"]),
                      help="Comma-separated Nuclei severity levels")
    parser.add_argument("--log-file", type=Path,
                      help="Path to log file")
    return parser.parse_args()

def main():
    args = parse_arguments()

    # Setup logging
    setup_logging(args.log_file)
    logger = logging.getLogger(__name__)

    try:
        # Validate inputs
        if not validate_domain(args.domain):
            raise ValueError(f"Invalid domain format: {args.domain}")

        severities = [s.strip() for s in args.severities.split(",")]
        if not validate_severities(severities):
            raise ValueError(f"Invalid severity levels: {args.severities}")

        templates_path = Path(args.templates).expanduser()
        if not templates_path.exists():
            raise FileNotFoundError(f"Nuclei templates directory not found: {templates_path}")

        # Prepare output directory
        domain_output_dir = args.output / args.domain
        if not validate_output_dir(domain_output_dir):
            raise ValueError(f"Failed to create output directory: {domain_output_dir}")

        # Initialize and run scanner
        scanner = SecurityScanner(
            domain=args.domain,
            output_dir=domain_output_dir,
            templates_path=templates_path
        )
        
        scanner.scan(
            severities=severities,
            notify=not args.no_notify
        )

    except Exception as err:
        logger.error(f"Fatal error: {err}")
        sys.exit(1)

if __name__ == "__main__":
    main()
