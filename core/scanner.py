import subprocess
import logging
from typing import List, Dict, Optional
from pathlib import Path
import tempfile
import shutil
import zipfile
from tqdm import tqdm

from ..utils.helpers import (
    get_latest_release_url,
    validate_file,
    create_requests_session,
    format_discord_message
)
from ..config.settings import (
    GITHUB_API_URL,
    BIN_DIR,
    BINARIES,
    NUCLEI_CONFIG
)

logger = logging.getLogger(__name__)

class SecurityScanner:
    def __init__(self, domain: str, output_dir: Path, templates_path: Path):
        self.domain = domain
        self.output_dir = output_dir
        self.templates_path = templates_path
        self.bin_paths: Dict[str, Path] = {}
        self.session = create_requests_session()

    def download_and_extract(self, url: str, binary_name: str) -> None:
        """Downloads and extracts a binary to the script's bin directory."""
        try:
            BIN_DIR.mkdir(parents=True, exist_ok=True)

            with self.session.get(url, stream=True) as response:
                response.raise_for_status()
                total_size = int(response.headers.get('content-length', 0))

                with tempfile.TemporaryDirectory() as temp_dir:
                    zip_path = Path(temp_dir) / f"{binary_name}.zip"
                    with open(zip_path, 'wb') as f, tqdm(
                        desc=binary_name,
                        total=total_size,
                        unit='iB',
                        unit_scale=True
                    ) as pbar:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)
                            pbar.update(len(chunk))

                    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                        zip_ref.extractall(temp_dir)

                    # Search for binary in extracted files
                    extracted_files = list(Path(temp_dir).rglob('*'))
                    binary_found = False
                    for file in extracted_files:
                        if file.is_file() and (file.name == binary_name or file.name == f"{binary_name}.exe"):
                            file.chmod(0o755)
                            shutil.move(str(file), str(BIN_DIR / file.name))
                            binary_found = True
                            break

                    if not binary_found:
                        raise FileNotFoundError(f"Binary {binary_name} not found in archive")

        except Exception as err:
            logger.error(f"Failed processing {binary_name}: {err}")
            raise

    def download_binaries(self, force: bool = False) -> None:
        """Downloads all required binaries with optional force update."""
        for binary, config in BINARIES.items():
            bin_path = BIN_DIR / binary
            if force or not bin_path.exists():
                logger.info(f"Downloading {binary}...")
                url = get_latest_release_url(binary, GITHUB_API_URL)
                self.download_and_extract(url, binary)
            self.bin_paths[binary] = bin_path

    def run_command(self, command: List[str], timeout: int = 1800) -> str:
        """Runs a shell command and handles errors."""
        try:
            process = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=True,
                timeout=timeout
            )
            return process.stdout
        except subprocess.CalledProcessError as err:
            logger.error(f"Command failed: {err}\nError output: {err.stderr}")
            raise
        except subprocess.TimeoutExpired:
            logger.error(f"Command timed out: {' '.join(command)}")
            raise

    def run_subfinder(self) -> Path:
        """Run subfinder and return output file path."""
        output_file = self.output_dir / "subfinder.txt"
        logger.info("Running subfinder...")
        
        command = [
            str(self.bin_paths["subfinder"]),
            "-d", self.domain,
            "-o", str(output_file)
        ] + BINARIES["subfinder"]["default_args"]
        
        self.run_command(command)
        validate_file(output_file, "Subfinder")
        return output_file

    def run_httpx(self, input_file: Path) -> Path:
        """Run httpx and return output file path."""
        output_file = self.output_dir / "httpx.txt"
        logger.info("Running httpx...")
        
        command = [
            str(self.bin_paths["httpx"]),
            "-l", str(input_file),
            "-o", str(output_file)
        ] + BINARIES["httpx"]["default_args"]
        
        self.run_command(command)
        validate_file(output_file, "Httpx")
        return output_file

    def run_nuclei(self, input_file: Path, severities: List[str]) -> Path:
        """Run nuclei and return output directory path."""
        nuclei_output_dir = self.output_dir / "nuclei"
        nuclei_output_dir.mkdir(parents=True, exist_ok=True)
        logger.info("Running nuclei...")
        
        command = [
            str(self.bin_paths["nuclei"]),
            "-l", str(input_file),
            "-t", str(self.templates_path),
            "-severity", ",".join(severities),
            "-tags", ",".join(NUCLEI_CONFIG["default_tags"]),
            "--rate-limit", str(NUCLEI_CONFIG["rate_limit"]),
            "-me", str(nuclei_output_dir)
        ] + BINARIES["nuclei"]["default_args"]
        
        self.run_command(command)
        return nuclei_output_dir

    def send_notification(self, data: str, title: str, data_type: str = 'text') -> None:
        """Send notification using notify."""
        if "notify" not in self.bin_paths:
            logger.warning("Notify binary not available, skipping notification")
            return

        try:
            if data_type == 'markdown':
                formatted_data = self._format_markdown_data(data)
            else:
                formatted_data = data.strip()

            notification_content = format_discord_message(formatted_data, title)

            with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
                temp_file.write(notification_content)
                temp_file_path = temp_file.name

            notify_command = [
                str(self.bin_paths["notify"]),
                "-data", temp_file_path,
                "-bulk"
            ] + BINARIES["notify"]["default_args"]

            self.run_command(notify_command)
            Path(temp_file_path).unlink()

        except Exception as err:
            logger.error(f"Notification error: {err}")

    def _format_markdown_data(self, data: str) -> str:
        """Format markdown data for notification."""
        formatted_lines = []
        in_table = False
        
        for line in data.split('\n'):
            if '|' in line and '---' in line:
                in_table = True
                continue
            if not in_table or not line.strip():
                continue

            parts = [p.strip() for p in line.split('|') if p.strip()]
            if len(parts) >= 3:
                hostname_ip = parts[0]
                finding = parts[1]
                severity = parts[2]
                if '](' in finding:
                    finding = finding.split('](')[0].replace('[', '').strip()
                formatted_lines.append(f"• {severity.upper()}: {finding} ({hostname_ip})")

        return "\n".join(formatted_lines) if formatted_lines else "No significant findings"

    def scan(self, severities: List[str], notify: bool = True) -> None:
        """Run the complete scanning pipeline."""
        try:
            # Download required binaries
            self.download_binaries()

            # Run subfinder
            subfinder_output = self.run_subfinder()
            if notify:
                self.send_notification(subfinder_output.read_text(), "Subfinder Results")

            # Run httpx
            httpx_output = self.run_httpx(subfinder_output)
            if notify:
                self.send_notification(httpx_output.read_text(), "Httpx Results")

            # Run nuclei
            nuclei_output = self.run_nuclei(httpx_output, severities)
            index_md = nuclei_output / "index.md"
            
            if not index_md.exists():
                raise FileNotFoundError("Nuclei index.md not found in output directory")

            if notify:
                self.send_notification(index_md.read_text(), "Nuclei Results", data_type='markdown')

            logger.info(f"Scan completed successfully. Results saved to: {self.output_dir}")

        except Exception as err:
            logger.error(f"Scan failed: {err}")
            raise 