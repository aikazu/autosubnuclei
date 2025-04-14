"""
Manages Nuclei templates, including downloading, extracting, and version checking.
"""

import logging
import os
import shutil
import tempfile
import zipfile
import time # Import time
from pathlib import Path
from typing import Optional
from datetime import datetime

import requests
import json # Import json

# Assuming helpers are available in utils
from ..utils.helpers import create_requests_session, download_file

logger = logging.getLogger(__name__)

class TemplateManager:
    # Purpose: Handle operations related to Nuclei templates directory.
    # Usage: tm = TemplateManager(Path("./nuclei-templates"))

    DEFAULT_TEMPLATES_DIR_NAME = "nuclei-templates"
    VERSION_FILE_NAME = ".version" # Using .version as used in SecurityScanner previously
    REPO_URL = "https://github.com/projectdiscovery/nuclei-templates/archive/refs/heads/master.zip"
    # COMMIT_API_URL = "https://api.github.com/repos/projectdiscovery/nuclei-templates/commits/master" # No longer used

    def __init__(self, templates_path: Path):
        # Purpose: Initialize the TemplateManager with the target path for templates.
        # Usage: tm = TemplateManager(Path("path/to/templates"))
        self.templates_path = templates_path.resolve() # Ensure absolute path

    def ensure_templates_exist(self) -> None:
        # Purpose: Check if templates exist and download them if necessary.
        #          Checks for the directory itself, not just the version file.
        # Usage: tm.ensure_templates_exist()
        # Check if the directory exists and contains YAML files
        if not self.templates_path.is_dir() or not any(self.templates_path.glob('**/*.yaml')):
            print(f"[INFO] Nuclei templates not found or incomplete at {self.templates_path}. Attempting download...")
            logger.info(f"Nuclei templates directory not found or empty at {self.templates_path}. Triggering download.")
            self.download_and_setup_templates()
        else:
            print(f"[INFO] Nuclei templates found at {self.templates_path}.")
            logger.info(f"Using existing Nuclei templates at {self.templates_path}")
            # Optionally add a check here for staleness based on timestamp in .version

    def download_and_setup_templates(self) -> None:
        # Purpose: Orchestrate the download and setup of Nuclei templates without API check.
        # Usage: tm.download_and_setup_templates()
        try:
            # Removed the check for latest commit hash
            print("[INFO] Starting template download process...")
            self._download_and_extract_templates() # Pass no hash
            print("[SUCCESS] Nuclei templates downloaded and set up successfully.")

        except Exception as e:
            logger.error(f"Failed to download/setup templates: {str(e)}", exc_info=True)
            print(f"[ERROR] Failed during template download/setup: {e}")
            raise

    def _download_and_extract_templates(self) -> None: # Removed commit_hash argument
        # Purpose: Download the template archive, extract it, and finalize the setup.
        # Usage: Called internally.
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.zip', prefix='nuclei-templates-') as temp_file:
                temp_path = temp_file.name
            logger.debug(f"Downloading template archive from {self.REPO_URL} to {temp_path}")
            print("[INFO] Downloading template archive (this may take a few moments)...")
            session = create_requests_session()
            download_file(self.REPO_URL, Path(temp_path), session=session)

            print("[INFO] Extracting template archive...")
            # Pass None for commit_hash as it's no longer used for versioning here
            self._extract_and_finalize_templates(temp_path, None)

        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    logger.debug(f"Removing temporary download file: {temp_path}")
                    os.unlink(temp_path)
                except OSError as e:
                    logger.warning(f"Could not remove temporary template download file {temp_path}: {e}")

    def _extract_and_finalize_templates(self, zip_path: str, commit_hash: Optional[str]) -> None: # Keep commit_hash arg for now, but it will be None
        # Purpose: Extract the downloaded zip archive and move templates to the target path.
        # Usage: Called internally.
        with tempfile.TemporaryDirectory(prefix="nuclei-extract-") as temp_dir:
            logger.debug(f"Extracting archive {zip_path} to temporary directory {temp_dir}")
            try:
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(temp_dir)
            except zipfile.BadZipFile as e:
                logger.error(f"Downloaded template file is not a valid zip archive: {zip_path} - {e}")
                raise RuntimeError("Downloaded template archive is corrupted or incomplete.") from e
            except Exception as e:
                logger.error(f"Failed to extract template archive {zip_path}: {e}", exc_info=True)
                raise RuntimeError(f"Failed to extract template archive: {e}") from e

            extracted_dir = Path(temp_dir) / "nuclei-templates-master"
            if not extracted_dir.exists() or not extracted_dir.is_dir():
                logger.error(f"Could not find expected directory 'nuclei-templates-master' inside extracted archive at {temp_dir}")
                raise FileNotFoundError("Could not find 'nuclei-templates-master' directory in the downloaded archive.")

            try:
                target_path = self.templates_path
                target_path.parent.mkdir(parents=True, exist_ok=True)
                if target_path.is_file():
                    logger.warning(f"Target template path {target_path} exists as a file, removing it.")
                    target_path.unlink()
                if target_path.exists():
                    print(f"[INFO] Removing existing templates directory at {target_path} for clean update...")
                    logger.info(f"Removing existing templates directory: {target_path}")
                    shutil.rmtree(target_path)

                print(f"[INFO] Moving template files to final destination: {target_path}...")
                logger.info(f"Moving extracted templates from {extracted_dir} to {target_path}...")
                shutil.move(str(extracted_dir), str(target_path))

            except Exception as e:
                 logger.error(f"Failed to move templates from {extracted_dir} to {target_path}: {e}", exc_info=True)
                 raise RuntimeError(f"Failed to finalize template installation: {e}") from e

            # Save download timestamp instead of commit hash
            self._save_template_version_timestamp()

            logger.info(f"Templates successfully finalized at {target_path}")

    def _save_template_version_timestamp(self) -> None:
        # Purpose: Save the download timestamp to the version file.
        # Usage: Called internally after successful extraction/move.
        version_file = self.templates_path / self.VERSION_FILE_NAME
        download_time = time.time()
        logger.debug(f"Saving template download timestamp {download_time} to {version_file}")
        try:
            with open(version_file, "w") as f:
                # Store as ISO format string for readability
                f.write(datetime.fromtimestamp(download_time).isoformat())
            logger.info(f"Saved template download timestamp.")
        except IOError as e:
            logger.warning(f"Could not save version info to {version_file}: {e}") 