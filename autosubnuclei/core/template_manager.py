"""
Manages Nuclei templates, including downloading, extracting, and version checking.
"""

import logging
import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Optional

import requests

# Assuming helpers are available in utils
from ..utils.helpers import create_requests_session, download_file

logger = logging.getLogger(__name__)

class TemplateManager:
    # Purpose: Handle operations related to Nuclei templates directory.
    # Usage: tm = TemplateManager(Path("./nuclei-templates"))

    DEFAULT_TEMPLATES_DIR_NAME = "nuclei-templates"
    VERSION_FILE_NAME = ".version" # Using .version as used in SecurityScanner previously
    REPO_URL = "https://github.com/projectdiscovery/nuclei-templates/archive/refs/heads/master.zip"
    COMMIT_API_URL = "https://api.github.com/repos/projectdiscovery/nuclei-templates/commits/master"

    def __init__(self, templates_path: Path):
        # Purpose: Initialize the TemplateManager with the target path for templates.
        # Usage: tm = TemplateManager(Path("path/to/templates"))
        self.templates_path = templates_path.resolve() # Ensure absolute path

    def ensure_templates_exist(self) -> None:
        # Purpose: Check if templates exist and download them if necessary.
        # Usage: tm.ensure_templates_exist()
        version_file = self.templates_path / self.VERSION_FILE_NAME
        if not version_file.exists(): # Simple check for existence via version file
            print(f"[INFO] Nuclei templates not found or incomplete at {self.templates_path}. Attempting download...")
            logger.info(f"Nuclei templates version file not found at {version_file}. Triggering download.")
            self.download_and_setup_templates()
        else:
            print(f"[INFO] Nuclei templates found at {self.templates_path} (based on presence of {self.VERSION_FILE_NAME}).")
            logger.info(f"Using existing Nuclei templates at {self.templates_path}")

    def download_and_setup_templates(self) -> None:
        # Purpose: Orchestrate the download and setup of Nuclei templates.
        # Usage: tm.download_and_setup_templates()
        try:
            print("[INFO] Checking latest Nuclei templates from GitHub...")
            commit_hash = self._get_latest_template_commit()

            print("[INFO] Starting template download process...")
            self._download_and_extract_templates(commit_hash)
            print("[SUCCESS] Nuclei templates downloaded and set up successfully.")

        except Exception as e:
            logger.error(f"Failed to download/setup templates: {str(e)}", exc_info=True)
            print(f"[ERROR] Failed during template download/setup: {e}")
            # Re-raise as a specific error type if needed, or let the original exception propagate
            raise

    def _get_latest_template_commit(self) -> Optional[str]:
        # Purpose: Fetch the latest commit hash for nuclei-templates from GitHub API.
        # Usage: commit_hash = self._get_latest_template_commit()
        try:
            logger.debug(f"Fetching latest commit info from {self.COMMIT_API_URL}")
            response = requests.get(self.COMMIT_API_URL, timeout=15) # Increased timeout
            response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
            commit_hash = response.json()["sha"]
            logger.info(f"Latest templates commit from GitHub: {commit_hash[:7]}")
            return commit_hash
        except requests.exceptions.Timeout:
            logger.warning("Timeout connecting to GitHub API for commit info.")
            return None
        except requests.exceptions.RequestException as e:
            logger.warning(f"Could not get latest commit info from GitHub API: {e}")
            return None
        except (KeyError, json.JSONDecodeError) as e:
            logger.warning(f"Error processing GitHub API response for commit info: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting commit info: {e}", exc_info=True)
            return None # Don't block download if commit check fails

    def _download_and_extract_templates(self, commit_hash: Optional[str]) -> None:
        # Purpose: Download the template archive, extract it, and finalize the setup.
        # Usage: Called internally.
        temp_path = None
        try:
            # Download zip to a temporary file
            # Use mkstemp for better security/atomicity if possible, but NamedTemporaryFile is often simpler
            with tempfile.NamedTemporaryFile(delete=False, suffix='.zip', prefix='nuclei-templates-') as temp_file:
                temp_path = temp_file.name
            logger.debug(f"Downloading template archive from {self.REPO_URL} to {temp_path}")
            print("[INFO] Downloading template archive (this may take a few moments)...")
            session = create_requests_session() # Assumes this helper exists and is appropriate
            download_file(self.REPO_URL, Path(temp_path), description="Downloading templates") # Assumes helper handles progress

            # Extract and finalize
            print("[INFO] Extracting template archive...")
            self._extract_and_finalize_templates(temp_path, commit_hash)

        finally:
            # Clean up the temporary zip file
            if temp_path and os.path.exists(temp_path):
                try:
                    logger.debug(f"Removing temporary download file: {temp_path}")
                    os.unlink(temp_path)
                except OSError as e:
                    logger.warning(f"Could not remove temporary template download file {temp_path}: {e}")

    def _extract_and_finalize_templates(self, zip_path: str, commit_hash: Optional[str]) -> None:
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

            # Assume the main content is in a subdirectory named 'nuclei-templates-master'
            extracted_dir = Path(temp_dir) / "nuclei-templates-master"
            if not extracted_dir.exists() or not extracted_dir.is_dir():
                # Log contents of temp_dir for debugging if needed
                logger.error(f"Could not find expected directory 'nuclei-templates-master' inside extracted archive at {temp_dir}")
                raise FileNotFoundError("Could not find 'nuclei-templates-master' directory in the downloaded archive.")

            try:
                # Prepare target directory (ensure parent exists, clear old target)
                target_path = self.templates_path
                target_path.parent.mkdir(parents=True, exist_ok=True)
                if target_path.is_file(): # Remove if it's somehow a file
                    logger.warning(f"Target template path {target_path} exists as a file, removing it.")
                    target_path.unlink()
                if target_path.exists(): # Remove existing directory for clean update
                    print(f"[INFO] Removing existing templates directory at {target_path} for clean update...")
                    logger.info(f"Removing existing templates directory: {target_path}")
                    shutil.rmtree(target_path)

                # Move extracted templates to final destination
                print(f"[INFO] Moving template files to final destination: {target_path}...")
                logger.info(f"Moving extracted templates from {extracted_dir} to {target_path}...")
                # shutil.move is generally preferred over copytree for this pattern
                shutil.move(str(extracted_dir), str(target_path))

            except Exception as e:
                 logger.error(f"Failed to move templates from {extracted_dir} to {target_path}: {e}", exc_info=True)
                 raise RuntimeError(f"Failed to finalize template installation: {e}") from e

            # Save version information if available
            self._save_template_version(commit_hash)

            logger.info(f"Templates successfully finalized at {target_path}")

    def _save_template_version(self, commit_hash: Optional[str]) -> None:
        # Purpose: Save the commit hash to the version file within the templates directory.
        # Usage: Called internally after successful extraction/move.
        if commit_hash:
            version_file = self.templates_path / self.VERSION_FILE_NAME
            logger.debug(f"Saving template version {commit_hash[:7]} to {version_file}")
            try:
                with open(version_file, "w") as f:
                    f.write(commit_hash)
                logger.info(f"Saved template version info: {commit_hash[:7]}")
            except IOError as e:
                logger.warning(f"Could not save version info to {version_file}: {e}")
        else:
            logger.warning("No commit hash available to save template version.") 