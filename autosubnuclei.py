#!/usr/bin/env python3

import os
import sys
import shutil
import requests
import zipfile
import tempfile
import subprocess
import argparse
from pathlib import Path
from tqdm import tqdm

GITHUB_API_URL = "https://api.github.com/repos/projectdiscovery/{binary}/releases/latest"
DISCORD_MESSAGE_LIMIT = 2000  # Discord's message character limit

# Get script directory for binary storage
SCRIPT_DIR = Path(__file__).parent.resolve()
BIN_DIR = SCRIPT_DIR / "bin"

def get_amd64_zip_url(release_info):
    """Extracts the download URL for the amd64 zip asset from the release info."""
    for asset in release_info.get("assets", []):
        asset_name = asset["name"].lower()
        if "amd64" in asset_name and asset_name.endswith(".zip"):
            return asset["browser_download_url"]
    raise ValueError(f"No amd64 zip asset found in release {release_info['tag_name']}")

def get_latest_release_url(binary):
    """Fetches the latest release info for a given binary from GitHub."""
    try:
        response = requests.get(GITHUB_API_URL.format(binary=binary))
        response.raise_for_status()
        return get_amd64_zip_url(response.json())
    except requests.exceptions.RequestException as err:
        sys.exit(f"Error fetching release info for {binary}: {err}")

def run_command(command, timeout=1800):
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
        sys.exit(f"Command failed: {err}\nError output: {err.stderr}")
    except subprocess.TimeoutExpired:
        sys.exit(f"Command timed out: {' '.join(command)}")

# ... (keep the create_notify_config and send_notification functions unchanged) ...

def download_and_extract(url, binary_name):
    """Downloads and extracts a binary to the script's bin directory."""
    try:
        BIN_DIR.mkdir(parents=True, exist_ok=True)
        
        with requests.get(url, stream=True) as response:
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
                for file in extracted_files:
                    if file.is_file() and file.name == binary_name:
                        file.chmod(0o755)
                        shutil.move(str(file), str(BIN_DIR / binary_name))
                        return
                
                raise FileNotFoundError(f"Binary {binary_name} not found in archive")

    except Exception as err:
        sys.exit(f"Failed processing {binary_name}: {err}")

def download_binaries(binaries, force=False):
    """Downloads all required binaries with optional force update."""
    for binary, url in binaries.items():
        bin_path = BIN_DIR / binary
        if force or not bin_path.exists():
            print(f"Downloading {binary}...")
            download_and_extract(url, binary)

def validate_file(file_path, step_name):
    """Validates if output file exists and has content."""
    if not file_path.exists():
        sys.exit(f"{step_name} failed to create output file")
    if file_path.stat().st_size == 0:
        sys.exit(f"{step_name} produced empty results")

def main():
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
    parser.add_argument("--severities", default="critical,high,medium,low",
                      help="Comma-separated Nuclei severity levels")
    args = parser.parse_args()

    # Prepare output directories
    domain_output_dir = args.output / args.domain
    domain_output_dir.mkdir(parents=True, exist_ok=True)
    templates_path = Path(args.templates).expanduser()

    # Get binary URLs and download
    binaries = {
        "subfinder": get_latest_release_url("subfinder"),
        "httpx": get_latest_release_url("httpx"),
        "nuclei": get_latest_release_url("nuclei"),
        "notify": get_latest_release_url("notify")
    }
    download_binaries(binaries, args.force)

    # Build paths to binaries
    bin_paths = {name: str(BIN_DIR / name) for name in binaries}

    # Subfinder execution
    sub_output = domain_output_dir / "subfinder.txt"
    print("Running subfinder...")
    run_command([bin_paths["subfinder"], "-silent", "-d", args.domain, "-o", str(sub_output)])
    validate_file(sub_output, "Subfinder")
    if not args.no_notify:
        send_notification(sub_output.read_text(), "Subfinder Results", bin_paths["notify"])

    # Httpx execution
    httpx_output = domain_output_dir / "httpx.txt"
    print("Running httpx...")
    run_command([bin_paths["httpx"], "-silent", "-l", str(sub_output), "-o", str(httpx_output)])
    validate_file(httpx_output, "Httpx")
    if not args.no_notify:
        send_notification(httpx_output.read_text(), "Httpx Results", bin_paths["notify"])

    # Nuclei execution
    nuclei_output_dir = domain_output_dir / "nuclei"
    nuclei_output_dir.mkdir(parents=True, exist_ok=True)
    
    print("Running nuclei...")
    run_command([
        bin_paths["nuclei"],
        "-l", str(httpx_output),
        "-t", str(templates_path),
        "-severity", args.severities,
        "-me", str(nuclei_output_dir)
    ])
    
    # Look for index.md specifically
    index_md = nuclei_output_dir / "index.md"
    if not index_md.exists():
        sys.exit("Nuclei index.md not found in output directory")
    
    if not args.no_notify:
        send_notification(index_md.read_text(), "Nuclei Results", bin_paths["notify"], data_type='markdown')

    print(f"Scan completed successfully. Results saved to: {domain_output_dir}")

if __name__ == "__main__":
    main()
