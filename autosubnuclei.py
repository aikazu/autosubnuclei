#!/usr/bin/env python3

import sys
import logging

# Import the main CLI group from the cli module
from autosubnuclei.cli import cli
from autosubnuclei.utils.helpers import setup_logging

# Configure basic logging in case commands run into issues before specific setup
try:
    setup_logging() 
    logger = logging.getLogger(__name__)
except Exception as e:
    print(f"Warning: Failed to set up basic logging: {e}")
    logger = None # Ensure logger exists even if setup fails

if __name__ == "__main__":
    try:
        cli()
    except Exception as e:
        # Catch any unhandled exceptions from the CLI
        if logger:
            logger.critical(f"Unhandled exception at entry point: {e}", exc_info=True)
        print(f"❌ An unexpected critical error occurred: {e}", file=sys.stderr)
        print("   Please check logs for more details.", file=sys.stderr)
        sys.exit(1)
